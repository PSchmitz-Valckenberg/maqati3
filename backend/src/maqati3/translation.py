"""One run of draft translations: what it may do, and what it must refuse.

The transcription rules apply here too — ask once, never overwrite, fail closed, and
the same daily budget, because both spend money on the same recording and an admin
should have one number to understand rather than two. Those pieces are imported from
`transcription` rather than restated.

What is new is the unit of work: **one language of one entry**. A job drafts English or
German, never both, so a German failure does not redo the English that already arrived,
and a reviewer who has started on one language keeps it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from maqati3.domain import Lang
from maqati3.transcription import (
    AlreadyQueued,
    DailyLimitReached,
    UnknownEntry,
)

#: The `job.kind` of a draft translation. The worker claims these beside `transcribe`.
TRANSLATE_JOB_KIND = "translate"

#: What is drafted, and in what order the dashboard offers it. Arabic is never a target:
#: it is the source, and it is written by a human or by the transcriber.
TARGET_LANGUAGES = (Lang.EN, Lang.DE)


class NothingToTranslate(ValueError):
    """There is no Arabic yet. A model asked to translate nothing is paid for nothing."""


class AlreadyTranslated(ValueError):
    """This language already has text, or someone is working on it.

    Raised when a draft is asked for and again when one tries to land. The second case
    is the one that matters: by then the money is spent, and overwriting a reviewer's
    English because our draft arrived late would be the expensive mistake.
    """


class Translations(Protocol):
    """Where a finished draft goes, as the worker sees it."""

    def source_lines(self, entry_id: str, lang: Lang) -> tuple[str, ...]:
        """The entry's lines in `lang`, ordered by row. Empty if there are none."""
        ...

    def store(self, entry_id: str, target: Lang, lines: Sequence[str]) -> int:
        """Write the draft and put the language in front of a reviewer; rows written.

        Raises `AlreadyTranslated` or `translate.LineCountMismatch`, and in both cases
        writes nothing at all.
        """
        ...


__all__ = [
    "TARGET_LANGUAGES",
    "TRANSLATE_JOB_KIND",
    "AlreadyQueued",
    "AlreadyTranslated",
    "DailyLimitReached",
    "NothingToTranslate",
    "Translations",
    "UnknownEntry",
]
