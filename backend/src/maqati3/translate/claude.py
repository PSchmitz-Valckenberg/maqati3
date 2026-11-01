"""Draft translations with Claude Haiku.

Chosen in `docs/ARCHITECTURE.md`: the cheapest model that handles Arabic well, because
every line it writes is read and corrected by a person anyway — the draft exists to save
typing, not to be trusted.

Two things make the row-count rule answerable instead of hopeful. The reply is
constrained to a JSON array by the API's structured output, so there is always a
countable list rather than prose to parse; and every line goes up numbered, so a line
the model would otherwise have quietly folded into its neighbour has a number that goes
missing. The count is then checked, and a mismatch raises rather than being repaired.

**Not the Batch API**, although `CLAUDE.md` names it. Batch halves the price, and the
whole corpus costs about nine euros to draft, so the saving is some four euros against a
job that would have to submit, store a batch id, and come back hours later — a second
shape of job, and a second thing to operate, for less than a coffee. If the corpus ever
grows by two orders of magnitude, this is the first place to look again.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from maqati3.domain import Lang
from maqati3.translate import (
    LineCountMismatch,
    TranslationError,
    TranslationNotConfigured,
)

#: Haiku: the draft model. A person corrects every line, so capability buys little here
#: and cost buys a lot -- the whole corpus is drafted for single-digit euros.
DEFAULT_MODEL = "claude-haiku-5-5"

#: Lines per request. Small enough that the model can hold the count, that a retry is
#: cheap, and that one bad chunk does not cost a whole lecture.
CHUNK_LINES = 40

#: Generous for 40 short lines; a cut-off reply would fail the count check anyway.
MAX_TOKENS = 8000

LANGUAGE_NAMES = {Lang.AR: "Arabic", Lang.EN: "English", Lang.DE: "German"}

#: The reply shape. With this the model cannot answer with prose, an apology or a
#: numbered list of its own invention: there is always a countable array.
SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {"lines": {"type": "array", "items": {"type": "string"}}},
        "required": ["lines"],
        "additionalProperties": False,
    },
}


def system_prompt(source: Lang, target: Lang) -> str:
    """What the model is told. Every sentence here is load-bearing; see the comments."""
    return f"""You translate the transcript of a scholar's recorded answer from \
{LANGUAGE_NAMES[source]} into {LANGUAGE_NAMES[target]}.

Return exactly one translation for each numbered line you are given, in the same order,
as a JSON array under "lines". This is absolute: the lines are moments in a recording,
and line 42 of your answer is shown at the second line 42 was spoken. Never merge two
lines into one sentence, never split one line into two, never add a line and never drop
one. If a line is empty, return an empty string for it. If a sentence runs across two
lines, translate the part that belongs to each line, even where that reads awkwardly on
its own: a person will smooth it afterwards, and they cannot put back a line you removed.

Keep the ruling exactly as strong or as weak as it is. Do not soften, strengthen or
tidy. Where a line uses a term of Islamic law -- harām, makrūh, wājib, mustaḥabb, mubāḥ,
sunna, bidʿa, lā yanbaghī, al-aḥwaṭ -- keep that term, transliterated, rather than
replacing it with an everyday word: "makrūh" is not "not very good", and "lā yanbaghī"
is not "is forbidden".

Translate only what is there. Do not explain, do not add a note, do not complete a
sentence the speaker left unfinished. Where the {LANGUAGE_NAMES[source]} is unclear,
translate it as unclearly as it stands rather than guessing what was meant.

This is a draft that a person will check line by line."""


class ClaudeTranslator:
    """`translate.Translator` against the Claude Messages API."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_MODEL,
        client: Any | None = None,
        chunk_lines: int = CHUNK_LINES,
    ) -> None:
        if not api_key.strip():
            # At startup, not at the first click: a server that cannot translate says so.
            raise TranslationNotConfigured("ANTHROPIC_API_KEY is empty")
        self._model = model
        self._chunk_lines = max(1, chunk_lines)
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
        # Deliberately untyped: a fake with the same two attributes stands in for the
        # SDK in every test, and the SDK's own TypedDicts do not accept plain dicts.
        self._client: Any = client

    def translate(
        self, lines: Sequence[str], *, source: Lang, target: Lang
    ) -> tuple[str, ...]:
        drafted: list[str] = []
        for start in range(0, len(lines), self._chunk_lines):
            chunk = list(lines[start : start + self._chunk_lines])
            drafted.extend(self._chunk(chunk, source=source, target=target, offset=start))
        return tuple(drafted)

    def _chunk(
        self, lines: list[str], *, source: Lang, target: Lang, offset: int
    ) -> list[str]:
        numbered = "\n".join(f"{n}. {line}" for n, line in enumerate(lines, start=offset + 1))
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system_prompt(source, target),
                # Mechanical work on short text: thinking would cost tokens and change
                # nothing. `low` effort is what this model's disabled-thinking mode allows.
                thinking={"type": "disabled"},
                output_config={"effort": "low", "format": SCHEMA},
                messages=[{"role": "user", "content": numbered}],
            )
        except Exception as exc:  # the SDK's own errors, and anything a fake raises
            raise TranslationError(f"the model could not be asked: {exc}") from exc
        drafted = _lines_of(response)
        if len(drafted) != len(lines):
            raise LineCountMismatch(
                f"lines {offset + 1}-{offset + len(lines)}: asked for {len(lines)} lines, "
                f"got {len(drafted)}"
            )
        return drafted


def _lines_of(response: Any) -> list[str]:
    """The array out of the reply. Anything else is a failure, never a partial answer."""
    try:
        text = next(block.text for block in response.content if block.type == "text")
        payload = json.loads(text)
        lines = payload["lines"]
    except (AttributeError, StopIteration, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise TranslationError(f"the model did not answer in the agreed shape: {exc}") from exc
    if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
        raise TranslationError("the model's lines were not a list of strings")
    return list(lines)


__all__ = ["CHUNK_LINES", "DEFAULT_MODEL", "ClaudeTranslator", "system_prompt"]
