"""The boundary to the speech-to-text provider.

The archive does not depend on Soniox; it depends on these four types. The provider's
own client lives in `asr.soniox`, the grouping of its word tokens into transcript rows
in `asr.lines`, and the worker that stores the result knows neither.

What comes out of here is a *draft*. Every row it produces is written with
`span_role = 'unclear'` and `citable = false`: no human has confirmed whose words they
are or that the second is right, and on old cassette material the word error rate is
20-40 %. Those two defaults are what keeps an unreviewed machine transcript out of
every citation (CLAUDE.md, "Integrity is structural").
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from maqati3.domain import Lang


class AsrError(Exception):
    """The provider could not produce a transcript. The job retries; nothing is stored."""


class AsrNotConfigured(AsrError):
    """No API key. The button that would spend money is not offered at all."""


@dataclass(frozen=True, slots=True)
class AsrToken:
    """One word as the provider timed it. Milliseconds from the start of the recording."""

    text: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True, slots=True)
class AsrLine:
    """One moment of the recording: what becomes a single `segment` row."""

    t_start_ms: int
    t_end_ms: int
    text: str


@dataclass(frozen=True, slots=True)
class AsrTranscript:
    lang: Lang
    lines: tuple[AsrLine, ...]
    #: What the provider charged us for, as it reported it. Logged, not displayed.
    audio_ms: int | None = None


class Transcriber(Protocol):
    """One recording in, one draft transcript out. Everything else is the job's business."""

    def transcribe(self, path: Path, *, lang: Lang) -> AsrTranscript:
        """Raises `AsrError` for anything that leaves no transcript."""
        ...


__all__ = [
    "AsrError",
    "AsrLine",
    "AsrNotConfigured",
    "AsrToken",
    "AsrTranscript",
    "Transcriber",
]
