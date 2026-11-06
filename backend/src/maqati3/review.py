"""The review editor: what a person may do to a transcript, and what they may not.

One language of one entry is the unit of work. A person *takes* it (it becomes
`in_progress` with their name on it), edits its rows, hands it on (`awaiting_review`) and
somebody approves it. The rules below hold wherever the editor is reached from:

* **Rows are edited, never added, removed or moved.** That is what keeps every timestamp
  valid, so there is no operation here that does any of the three.
* **No log row, no edit.** Every change writes to the append-only `revision_log` in the
  same transaction.
* **Only along the state machine** (`maqati3.register.states`), plus the two rules that
  machine does not know: a draft is made by a worker and never by a click, and no
  translation is worked on before the Arabic is approved.
* **Nobody works on a language someone else has taken.** How long a claim lasts and how
  one is taken over is still open (issue #24), so for now there is no takeover at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from maqati3.domain import Lang, ReviewState
from maqati3.translation import ArabicNotApproved


class NotInProgress(ValueError):
    """The language is not being worked on, so its text may not be changed."""


class ClaimedByOther(ValueError):
    """Someone else has taken this language."""


class UnknownRow(LookupError):
    """No such row, or no text in that language for it. Editing never creates one."""


class EmptyText(ValueError):
    """A row is never emptied: an empty row is a deleted row that still holds its second."""


@dataclass(frozen=True, slots=True)
class ReviewRow:
    """One moment: where it is in the recording and what was said in each language."""

    idx: int
    t_start_ms: int
    t_end_ms: int | None
    texts: dict[Lang, str]


@dataclass(frozen=True, slots=True)
class LanguageState:
    state: ReviewState
    #: Who has taken it; None while nobody has.
    assignee: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewView:
    entry_id: str
    rows: list[ReviewRow]
    states: dict[Lang, LanguageState] = field(default_factory=dict)


class Review(Protocol):
    """The editor's work. Every change is logged with who made it."""

    def view(self, entry_id: str) -> ReviewView | None:
        """The rows and the state of every language, or None for an unknown entry."""
        ...

    def edit_text(self, entry_id: str, idx: int, lang: Lang, text: str, actor: str) -> None:
        """Replace one row's text in one language.

        Raises `UnknownEntry`, `NotInProgress`, `ClaimedByOther`, `UnknownRow` or
        `EmptyText`, and in every one of those cases changes nothing.
        """
        ...

    def move(self, entry_id: str, lang: Lang, to: ReviewState, actor: str) -> ReviewState:
        """Move a language one step along the state machine; the new state.

        Raises `UnknownEntry`, `InvalidTransition`, `ClaimedByOther` or
        `ArabicNotApproved`, and in every one of those cases changes nothing.
        """
        ...


__all__ = [
    "ArabicNotApproved",
    "ClaimedByOther",
    "EmptyText",
    "LanguageState",
    "NotInProgress",
    "Review",
    "ReviewRow",
    "ReviewView",
    "UnknownRow",
]
