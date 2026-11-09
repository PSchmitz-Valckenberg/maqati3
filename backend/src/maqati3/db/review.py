"""`review.Review` over Postgres.

Both writes are one transaction with the entry locked, and each ends with a row in
`revision_log`: if the log insert fails, the edit is rolled back with it. Nothing here
inserts or deletes a `segment` or a `segment_text` -- an edit is an UPDATE of a row that
already exists.
"""

from __future__ import annotations

import json

from maqati3.db.sql import Executor
from maqati3.domain import Lang, ReviewState, SpanRole
from maqati3.register.states import InvalidTransition, advance, can_start_translation
from maqati3.review import (
    ClaimedByOther,
    EmptyText,
    LanguageState,
    NotInProgress,
    ReviewRow,
    ReviewView,
    RoleNotSet,
    UnknownRow,
)
from maqati3.transcription import UnknownEntry
from maqati3.translation import ArabicNotApproved

_ENTRY_EXISTS = "SELECT 1 FROM entry WHERE id = %s"
_LOCK_ENTRY = "SELECT 1 FROM entry WHERE id = %s FOR UPDATE"

_ROWS = """
SELECT s.idx, s.t_start_ms, s.t_end_ms, t.lang, t.text_raw, s.span_role, s.citable
  FROM segment s LEFT JOIN segment_text t ON t.segment_id = s.id
 WHERE s.entry_id = %s ORDER BY s.idx
"""
_STATES = "SELECT lang, state, assignee FROM entry_language WHERE entry_id = %s"
_STATE = "SELECT state, assignee FROM entry_language WHERE entry_id = %s AND lang = %s FOR UPDATE"

_CURRENT_TEXT = """
SELECT t.segment_id, t.text_raw
  FROM segment s JOIN segment_text t ON t.segment_id = s.id
 WHERE s.entry_id = %s AND s.idx = %s AND t.lang = %s
"""
# text_norm is what gets searched; a stale one would index words nobody wrote any more.
_UPDATE_TEXT = """
UPDATE segment_text SET text_raw = %s, text_norm = NULL, provenance = 'human'
 WHERE segment_id = %s AND lang = %s
"""
_UPDATE_STATE = """
UPDATE entry_language SET state = %s, assignee = %s, updated_at = now()
 WHERE entry_id = %s AND lang = %s
"""
_ROW_FLAGS = "SELECT id, span_role, citable FROM segment WHERE entry_id = %s AND idx = %s"
_SET_ROLE = "UPDATE segment SET span_role = %s, citable = %s WHERE id = %s"
_SET_CITABLE = "UPDATE segment SET citable = %s WHERE id = %s"
_LOG = """
INSERT INTO revision_log (entity, entity_id, action, actor, detail)
VALUES (%s, %s, %s, %s, %s::jsonb)
"""


class PgReview:
    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    def view(self, entry_id: str) -> ReviewView | None:
        if not self._executor.fetchall(_ENTRY_EXISTS, (entry_id,)):
            return None
        rows: dict[int, ReviewRow] = {}
        for idx, start, end, lang, text, role, citable in self._executor.fetchall(
            _ROWS, (entry_id,)
        ):
            row = rows.setdefault(
                int(str(idx)),
                ReviewRow(
                    idx=int(str(idx)),
                    t_start_ms=int(str(start)),
                    t_end_ms=None if end is None else int(str(end)),
                    texts={},
                    span_role=SpanRole(str(role)),
                    citable=bool(citable),
                ),
            )
            if lang is not None:
                row.texts[Lang(str(lang))] = str(text)
        states = {
            Lang(str(lang)): LanguageState(
                ReviewState(str(state)), None if who is None else str(who)
            )
            for lang, state, who in self._executor.fetchall(_STATES, (entry_id,))
        }
        return ReviewView(entry_id=entry_id, rows=list(rows.values()), states=states)

    def edit_text(self, entry_id: str, idx: int, lang: Lang, text: str, actor: str) -> None:
        text = text.strip()
        with self._executor.transaction():
            self._lock(entry_id)
            state, assignee = self._state(entry_id, lang)
            if state is not ReviewState.IN_PROGRESS:
                raise NotInProgress(f"{entry_id} {lang.value} is {state.value}")
            if assignee != actor:
                raise ClaimedByOther(f"{entry_id} {lang.value} is taken by {assignee}")
            found = self._executor.fetchall(_CURRENT_TEXT, (entry_id, idx, lang.value))
            if not found:
                raise UnknownRow(f"{entry_id} row {idx} has no {lang.value} text")
            if not text:
                raise EmptyText(f"{entry_id} row {idx}")
            segment_id, before = found[0][0], str(found[0][1])
            if before == text:
                return
            self._executor.execute(_UPDATE_TEXT, (text, segment_id, lang.value))
            self._executor.execute(
                _LOG,
                (
                    "segment_text",
                    f"{entry_id}:{idx}:{lang.value}",
                    "edit",
                    actor,
                    json.dumps({"before": before, "after": text}),
                ),
            )

    def set_role(self, entry_id: str, idx: int, role: SpanRole, actor: str) -> None:
        with self._executor.transaction():
            segment_id, before, citable = self._row_for_judgement(entry_id, idx, actor)
            if before is role:
                return
            # The second was confirmed for another judgement; this one needs its own.
            self._executor.execute(_SET_ROLE, (role.value, False, segment_id))
            self._executor.execute(
                _LOG,
                (
                    "segment",
                    f"{entry_id}:{idx}",
                    "span_role",
                    actor,
                    json.dumps(
                        {
                            "before": before.value,
                            "after": role.value,
                            "citable_withdrawn": citable,
                        }
                    ),
                ),
            )

    def confirm_timestamp(self, entry_id: str, idx: int, confirmed: bool, actor: str) -> None:
        with self._executor.transaction():
            segment_id, role, citable = self._row_for_judgement(entry_id, idx, actor)
            if confirmed and role is SpanRole.UNCLEAR:
                raise RoleNotSet(f"{entry_id} row {idx}")
            if citable is confirmed:
                return
            self._executor.execute(_SET_CITABLE, (confirmed, segment_id))
            self._executor.execute(
                _LOG,
                (
                    "segment",
                    f"{entry_id}:{idx}",
                    "citable",
                    actor,
                    json.dumps({"before": citable, "after": confirmed}),
                ),
            )

    def move(self, entry_id: str, lang: Lang, to: ReviewState, actor: str) -> ReviewState:
        with self._executor.transaction():
            self._lock(entry_id)
            current, assignee = self._state(entry_id, lang)
            # Only a worker that has written the rows may declare a language drafted.
            if to is ReviewState.DRAFT_READY:
                raise InvalidTransition(f"{current.value} -> {to.value} is not done by hand")
            new = advance(current, to)
            if current is ReviewState.IN_PROGRESS and assignee != actor:
                raise ClaimedByOther(f"{entry_id} {lang.value} is taken by {assignee}")
            if lang is not Lang.AR and not can_start_translation(self._arabic(entry_id)):
                raise ArabicNotApproved(entry_id)
            who = actor if new is ReviewState.IN_PROGRESS else assignee
            self._executor.execute(_UPDATE_STATE, (new.value, who, entry_id, lang.value))
            self._executor.execute(
                _LOG,
                (
                    "entry_language",
                    f"{entry_id}:{lang.value}",
                    "state",
                    actor,
                    json.dumps({"from": current.value, "to": new.value}),
                ),
            )
        return new

    # ------------------------------------------------------------------ helpers

    def _row_for_judgement(
        self, entry_id: str, idx: int, actor: str
    ) -> tuple[object, SpanRole, bool]:
        """Lock the entry and return the row, after the same gate an edit passes: the
        Arabic is being worked on, by `actor`. Who speaks is judged on what was said."""
        self._lock(entry_id)
        state, assignee = self._state(entry_id, Lang.AR)
        if state is not ReviewState.IN_PROGRESS:
            raise NotInProgress(f"{entry_id} ar is {state.value}")
        if assignee != actor:
            raise ClaimedByOther(f"{entry_id} ar is taken by {assignee}")
        found = self._executor.fetchall(_ROW_FLAGS, (entry_id, idx))
        if not found:
            raise UnknownRow(f"{entry_id} has no row {idx}")
        return found[0][0], SpanRole(str(found[0][1])), bool(found[0][2])

    def _lock(self, entry_id: str) -> None:
        if not self._executor.fetchall(_LOCK_ENTRY, (entry_id,)):
            raise UnknownEntry(entry_id)

    def _state(self, entry_id: str, lang: Lang) -> tuple[ReviewState, str | None]:
        rows = self._executor.fetchall(_STATE, (entry_id, lang.value))
        if not rows:
            return ReviewState.NOT_STARTED, None
        return ReviewState(str(rows[0][0])), (None if rows[0][1] is None else str(rows[0][1]))

    def _arabic(self, entry_id: str) -> ReviewState:
        return self._state(entry_id, Lang.AR)[0]


__all__ = ["PgReview"]
