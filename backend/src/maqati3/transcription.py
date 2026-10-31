"""One transcription run: what it may do, and what it must refuse.

The pieces live apart on purpose — the provider in `asr/`, the rows in
`db/transcripts.py`, the button in `api/admin.py` — so the rules that hold across all
of them are written down once, here.

Two of them are gates in the sense `WORKFLOW.md` means:

* **Ask once.** A run is paid for per audio hour and writes a whole timeline. A second
  job for the same entry would be a second bill and a second writer, so a request is
  refused while one is queued and refused outright once there is anything to overwrite.
  A run that gave up leaves nothing behind, so after that a request is allowed again.
* **Never overwrite.** What is already stored may be a reviewer's corrected text. The
  worker writes where there is nothing, or it writes nothing at all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from maqati3.asr import AsrTranscript

#: The `job.kind` of a transcription. One worker process claims these.
JOB_KIND = "transcribe"


class UnknownEntry(LookupError):
    """No entry with that id. Nothing is queued."""


class AlreadyTranscribed(ValueError):
    """There is already a transcript, or someone is working on one.

    Raised both when a transcription is asked for and when a finished run tries to
    store its result — the second case is the one that matters, because by then the
    money is spent and overwriting would look like the cheap option.
    """


class AlreadyQueued(ValueError):
    """A run for this entry is queued or running. The second click buys nothing."""


class EmptyTranscript(ValueError):
    """The run produced no words at all.

    Not a success with zero rows: that would hand a reviewer an empty table and close
    the entry to another attempt. The entry stays untouched and can be tried again.
    """


class Transcripts(Protocol):
    """Where a finished run puts its result, as the worker sees it."""

    def media_path(self, entry_id: str) -> Path | None:
        """The audio to transcribe: the staged file the entry was registered from."""
        ...

    def store(self, entry_id: str, transcript: AsrTranscript) -> int:
        """Write the draft and put the language in front of a reviewer; rows written.

        Raises `AlreadyTranscribed` or `EmptyTranscript`, and in both cases writes
        nothing at all.
        """
        ...


__all__ = [
    "JOB_KIND",
    "AlreadyQueued",
    "AlreadyTranscribed",
    "EmptyTranscript",
    "Transcripts",
    "UnknownEntry",
]
