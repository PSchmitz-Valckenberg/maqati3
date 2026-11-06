"""An entry's descriptive metadata: a title, the question that was asked, keywords.

A model drafts them from the **approved** Arabic and a person corrects and confirms them.
Three rules hold, each with a test for the blocked case:

* **Not before the Arabic is approved.** A title made from a transcript nobody has
  checked is a wrong title with an authoritative look.
* **Never over a person's words, never twice.** One draft per entry; a draft that arrives
  after someone has typed their own is dropped.
* **Every change is logged** in `revision_log`, with before and after.

What a draft may not contain is held in the prompt (`metadata_claude`) and, more
importantly, in what is *not* here: there is no `hukm` field. A ruling of the archive's
own is the one thing the system must never produce, so a model is never asked for one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from maqati3.transcription import UnknownEntry
from maqati3.translation import ArabicNotApproved

#: Enough to find an entry by, few enough to read at a glance.
MAX_KEYWORDS = 8


class MetadataState(StrEnum):
    NONE = "none"
    DRAFT = "draft"
    CONFIRMED = "confirmed"


class MetadataError(Exception):
    """No usable draft came back. Nothing is stored."""


class MetadataNotConfigured(MetadataError):
    """No API key. The button is not offered at all."""


class AlreadyDrafted(ValueError):
    """The entry already has metadata, drafted or written by a person."""


class EmptyTitle(ValueError):
    """An entry is never left without a title."""


@dataclass(frozen=True, slots=True)
class MetadataDraft:
    title: str
    question: str
    keywords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EntryMetadata:
    title: str
    question: str
    keywords: tuple[str, ...]
    state: MetadataState


def tidy_keywords(keywords: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Lowercase, trimmed, no empties, no duplicates, in the order given, capped."""
    seen: list[str] = []
    for keyword in keywords:
        word = keyword.strip().lower()
        if word and word not in seen:
            seen.append(word)
    return tuple(seen[:MAX_KEYWORDS])


class MetadataDrafter(Protocol):
    def draft(self, lines: tuple[str, ...]) -> MetadataDraft:
        """Raises `MetadataError` for anything that leaves no usable draft."""
        ...


class Metadata(Protocol):
    def get(self, entry_id: str) -> EntryMetadata | None: ...

    def lines_to_draft_from(self, entry_id: str) -> tuple[str, ...]:
        """The approved Arabic, in row order.

        Raises `UnknownEntry`, `ArabicNotApproved` or `AlreadyDrafted`: nothing is sent
        to a model in any of those cases.
        """
        ...

    def store_draft(self, entry_id: str, draft: MetadataDraft, actor: str) -> None:
        """Raises `UnknownEntry` or `AlreadyDrafted`, and in both cases stores nothing."""
        ...

    def save(
        self, entry_id: str, title: str, question: str, keywords: tuple[str, ...], actor: str
    ) -> None:
        """A person's words; the state becomes `confirmed`. Raises `UnknownEntry` or
        `EmptyTitle`."""
        ...


__all__ = [
    "MAX_KEYWORDS",
    "AlreadyDrafted",
    "ArabicNotApproved",
    "EmptyTitle",
    "EntryMetadata",
    "Metadata",
    "MetadataDraft",
    "MetadataDrafter",
    "MetadataError",
    "MetadataNotConfigured",
    "MetadataState",
    "UnknownEntry",
    "tidy_keywords",
]
