"""Soniox, the speech-to-text provider chosen in `docs/ARCHITECTURE.md` (~$0.10/hour).

Three calls and a wait: the file goes up, a transcription is created against it, and we
poll until it is finished. Then both are deleted again — the recordings in this archive
were sent to us by contributors, and they have no business sitting in a third party's
storage once the transcript is ours.

**Nothing here has run against the real service**: the project has no API key yet, so
the shapes below come from the documentation (docs.soniox.com, async transcription) and
the tests pin them against a fake transport. The first run with a real key is the one
that will find whatever is wrong with them; that run belongs in `docs/PIPELINE.md`'s
bake-off, on real material, before any of it is trusted.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from maqati3.asr import AsrError, AsrNotConfigured, AsrToken, AsrTranscript
from maqati3.asr.lines import group_tokens
from maqati3.domain import Lang

log = logging.getLogger("maqati3")

BASE_URL = "https://api.soniox.com"

#: The current async model. `stt-async-v4` is an alias for it.
DEFAULT_MODEL = "stt-async-v5"

#: Between polls. The service answers in well under a minute for the short clips this
#: archive is made of.
POLL_INTERVAL_S = 2.0

#: At the interval above, about half an hour. A run still unfinished by then is not
#: coming back, and the worker must not hold its lease for ever waiting for it.
MAX_POLLS = 900

#: Uploading an 80 MB phone video over a slow link takes a while; a transcription that
#: hangs is caught by MAX_POLLS, not by this.
REQUEST_TIMEOUT_S = 300.0


class SonioxTranscriber:
    """`asr.Transcriber` against Soniox's REST API."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_MODEL,
        base_url: str = BASE_URL,
        client: httpx.Client | None = None,
        max_polls: int = MAX_POLLS,
        poll_interval_s: float = POLL_INTERVAL_S,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key.strip():
            # At startup, not at the first click: a server that cannot transcribe says so.
            raise AsrNotConfigured("SONIOX_API_KEY is empty")
        self._key = api_key
        self._model = model
        self._max_polls = max_polls
        self._poll_interval_s = poll_interval_s
        self._sleep = sleep
        self._client = client or httpx.Client(base_url=base_url, timeout=REQUEST_TIMEOUT_S)

    # ------------------------------------------------------------- the one method

    def transcribe(self, path: Path, *, lang: Lang) -> AsrTranscript:
        file_id = self._upload(path)
        transcription_id: str | None = None
        try:
            transcription_id = self._create(file_id, lang)
            self._await_completion(transcription_id)
            tokens = self._tokens(transcription_id)
        finally:
            self._clean_up(file_id, transcription_id)
        return AsrTranscript(lang=lang, lines=group_tokens(tokens))

    # ------------------------------------------------------------- the four calls

    def _upload(self, path: Path) -> str:
        with path.open("rb") as stream:
            body = self._json("POST", "/v1/files", files={"file": (path.name, stream)})
        return str(body["id"])

    def _create(self, file_id: str, lang: Lang) -> str:
        body = self._json(
            "POST",
            "/v1/transcriptions",
            json={"model": self._model, "file_id": file_id, "language_hints": [lang.value]},
        )
        return str(body["id"])

    def _await_completion(self, transcription_id: str) -> None:
        for poll in range(self._max_polls):
            if poll:
                self._sleep(self._poll_interval_s)
            body = self._json("GET", f"/v1/transcriptions/{transcription_id}")
            status = str(body.get("status", ""))
            if status == "completed":
                return
            if status == "error":
                raise AsrError(str(body.get("error_message") or "the provider reported an error"))
        raise AsrError(
            f"transcription {transcription_id} was still unfinished after {self._max_polls} polls"
        )

    def _tokens(self, transcription_id: str) -> list[AsrToken]:
        body = self._json("GET", f"/v1/transcriptions/{transcription_id}/transcript")
        raw = body.get("tokens")
        if not isinstance(raw, list):
            raise AsrError("the transcript had no tokens")
        return [_token(item) for item in raw if isinstance(item, dict)]

    def _clean_up(self, file_id: str, transcription_id: str | None) -> None:
        """Best effort, and never the reason a transcript is lost."""
        for route in filter(
            None,
            (
                f"/v1/transcriptions/{transcription_id}" if transcription_id else None,
                f"/v1/files/{file_id}",
            ),
        ):
            try:
                self._client.request("DELETE", route, headers=self._headers)
            except httpx.HTTPError as exc:
                log.warning("could not delete %s from the provider: %s", route, exc)

    # ------------------------------------------------------------- plumbing

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}"}

    def _json(self, method: str, route: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._client.request(method, route, headers=self._headers, **kwargs)
        except httpx.HTTPError as exc:
            raise AsrError(f"{method} {route} failed: {exc}") from exc
        if response.status_code >= 400:
            raise AsrError(f"{method} {route} answered {response.status_code}: {response.text}")
        body = response.json()
        if not isinstance(body, dict):
            raise AsrError(f"{method} {route} did not answer with an object")
        return body


def _token(item: dict[str, Any]) -> AsrToken:
    """One token, tolerant of the two timing shapes the provider has used.

    The current API gives `start_ms` and `end_ms`; the older one gave a duration. A
    missing end is not an error: `group_tokens` only needs it for the row's end, and a
    row whose end is its start is clamped by the player's renderer.
    """
    start = int(item.get("start_ms") or 0)
    end = item.get("end_ms")
    if end is None and item.get("duration_ms") is not None:
        end = start + int(item["duration_ms"])
    return AsrToken(text=str(item.get("text") or ""), start_ms=start, end_ms=int(end or start))


__all__ = ["BASE_URL", "DEFAULT_MODEL", "MAX_POLLS", "SonioxTranscriber"]
