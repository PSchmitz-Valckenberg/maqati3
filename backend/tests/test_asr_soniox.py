"""The Soniox client, against a fake transport. Never against the network.

The archive has no key yet, so nothing here has run against the real service: these
tests pin the request shapes the documentation describes and, more importantly, what
the client does when the service does not answer with a transcript.

One rule is not about Soniox at all: the recording is deleted from their servers when
we are done with it. These are recordings of scholars that contributors sent us; they
have no business sitting in a third party's storage after the transcript is ours.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from maqati3.asr import AsrError, AsrNotConfigured
from maqati3.asr.soniox import SonioxTranscriber
from maqati3.domain import Lang

KEY = "sk-test-key"


class FakeSoniox:
    """The documented endpoints, with whatever answers a test needs."""

    def __init__(
        self,
        *,
        statuses: list[str] | None = None,
        tokens: list[dict[str, object]] | None = None,
        fail_on: str | None = None,
        error_message: str = "the audio could not be decoded",
    ) -> None:
        self.statuses = statuses or ["completed"]
        self.tokens = tokens if tokens is not None else [
            {"text": "هذا", "start_ms": 0, "end_ms": 400},
            {"text": "جائز.", "start_ms": 400, "end_ms": 900},
        ]
        self.fail_on = fail_on
        self.error_message = error_message
        self.requests: list[tuple[str, str]] = []
        self.bodies: list[dict[str, object]] = []
        self.uploaded: bytes = b""

    def handle(self, request: httpx.Request) -> httpx.Response:
        route = f"{request.method} {request.url.path}"
        self.requests.append((request.method, request.url.path))
        if self.fail_on and route.startswith(self.fail_on):
            return httpx.Response(500, json={"message": "upstream exploded"})
        if request.headers.get("authorization") != f"Bearer {KEY}":
            return httpx.Response(401, json={"message": "no key"})
        if route == "POST /v1/files":
            self.uploaded = request.content
            return httpx.Response(200, json={"id": "file-1"})
        if route == "POST /v1/transcriptions":
            import json

            self.bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "tr-1"})
        if route == "GET /v1/transcriptions/tr-1":
            status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            body: dict[str, object] = {"status": status}
            if status == "error":
                body["error_message"] = self.error_message
            return httpx.Response(200, json=body)
        if route == "GET /v1/transcriptions/tr-1/transcript":
            return httpx.Response(200, json={"tokens": self.tokens})
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404, json={"message": f"no route {route}"})


def transcriber(fake: FakeSoniox, **kwargs: object) -> SonioxTranscriber:
    client = httpx.Client(
        transport=httpx.MockTransport(fake.handle), base_url="https://api.soniox.test"
    )
    return SonioxTranscriber(
        KEY, client=client, sleep=lambda _seconds: None, **kwargs  # type: ignore[arg-type]
    )


@pytest.fixture
def recording(tmp_path: Path) -> Path:
    path = tmp_path / "fatwa.m4a"
    path.write_bytes(b"not really audio, but bytes")
    return path


# ------------------------------------------------------------------ no key, no client


def test_a_transcriber_without_a_key_refuses_to_exist() -> None:
    # Fails where it is built, not on the first recording an admin clicks: a server that
    # cannot transcribe should say so at startup.
    with pytest.raises(AsrNotConfigured):
        SonioxTranscriber("")


# ------------------------------------------------------------------ nothing comes back


def test_a_failed_upload_is_an_asr_error(recording: Path) -> None:
    fake = FakeSoniox(fail_on="POST /v1/files")

    with pytest.raises(AsrError):
        transcriber(fake).transcribe(recording, lang=Lang.AR)


def test_a_run_the_service_gave_up_on_says_why(recording: Path) -> None:
    fake = FakeSoniox(statuses=["processing", "error"])

    with pytest.raises(AsrError) as excinfo:
        transcriber(fake).transcribe(recording, lang=Lang.AR)

    assert "could not be decoded" in str(excinfo.value)


def test_a_run_that_never_finishes_is_given_up_on(recording: Path) -> None:
    # Without this the worker holds its lease for ever on a job that will never end.
    fake = FakeSoniox(statuses=["processing"])

    with pytest.raises(AsrError):
        transcriber(fake, max_polls=3).transcribe(recording, lang=Lang.AR)


def test_the_recording_is_deleted_from_the_service_even_when_the_run_failed(
    recording: Path,
) -> None:
    fake = FakeSoniox(statuses=["error"])

    with pytest.raises(AsrError):
        transcriber(fake).transcribe(recording, lang=Lang.AR)

    assert ("DELETE", "/v1/files/file-1") in fake.requests


# ------------------------------------------------------------------ a transcript


def test_the_recording_goes_up_and_the_words_come_back_as_lines(recording: Path) -> None:
    fake = FakeSoniox(statuses=["queued", "processing", "completed"])

    result = transcriber(fake).transcribe(recording, lang=Lang.AR)

    assert recording.read_bytes() in fake.uploaded
    assert fake.bodies == [
        {"model": "stt-async-v5", "file_id": "file-1", "language_hints": ["ar"]}
    ]
    assert [(line.t_start_ms, line.t_end_ms, line.text) for line in result.lines] == [
        (0, 900, "هذا جائز.")
    ]
    assert result.lang is Lang.AR


def test_nothing_of_ours_is_left_on_their_servers(recording: Path) -> None:
    fake = FakeSoniox()

    transcriber(fake).transcribe(recording, lang=Lang.AR)

    assert ("DELETE", "/v1/transcriptions/tr-1") in fake.requests
    assert ("DELETE", "/v1/files/file-1") in fake.requests


def test_a_recording_with_no_words_comes_back_empty_rather_than_invented(
    recording: Path,
) -> None:
    fake = FakeSoniox(tokens=[])

    result = transcriber(fake).transcribe(recording, lang=Lang.AR)

    assert result.lines == ()
