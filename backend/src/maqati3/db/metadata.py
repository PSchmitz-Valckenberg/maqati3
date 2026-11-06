"""`metadata.Metadata` over Postgres.

Every write is one transaction with the entry locked and ends with a `revision_log` row.
`store_draft` writes only where `metadata_state` is still 'none', so a draft that arrives
late cannot replace a person's words.
"""

from __future__ import annotations

import json

from maqati3.db.sql import Executor
from maqati3.domain import ReviewState
from maqati3.metadata import (
    AlreadyDrafted,
    ArabicNotApproved,
    EmptyTitle,
    EntryMetadata,
    MetadataDraft,
    MetadataState,
    tidy_keywords,
)
from maqati3.transcription import UnknownEntry

_LOCK = "SELECT metadata_state FROM entry WHERE id = %s FOR UPDATE"
_GET = "SELECT title_en, question_en, keywords, metadata_state FROM entry WHERE id = %s"
_ARABIC_STATE = "SELECT state FROM entry_language WHERE entry_id = %s AND lang = 'ar'"
_ARABIC_LINES = """
SELECT t.text_raw FROM segment s JOIN segment_text t ON t.segment_id = s.id
 WHERE s.entry_id = %s AND t.lang = 'ar' ORDER BY s.idx
"""
_WRITE = """
UPDATE entry SET title_en = %s, question_en = %s, keywords = %s, metadata_state = %s,
                 updated_at = now()
 WHERE id = %s
"""
_LOG = """
INSERT INTO revision_log (entity, entity_id, action, actor, detail)
VALUES ('entry', %s, %s, %s, %s::jsonb)
"""


def _fields(row: tuple[object, ...]) -> dict[str, object]:
    keywords = row[2] if isinstance(row[2], list) else []
    return {
        "title": None if row[0] is None else str(row[0]),
        "question": None if row[1] is None else str(row[1]),
        "keywords": [str(k) for k in keywords],
    }


class PgMetadata:
    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    def get(self, entry_id: str) -> EntryMetadata | None:
        rows = self._executor.fetchall(_GET, (entry_id,))
        if not rows:
            return None
        fields = _fields(rows[0])
        return EntryMetadata(
            title=str(fields["title"] or ""),
            question=str(fields["question"] or ""),
            keywords=tuple(str(k) for k in fields["keywords"]),  # type: ignore[attr-defined]
            state=MetadataState(str(rows[0][3])),
        )

    def lines_to_draft_from(self, entry_id: str) -> tuple[str, ...]:
        state = self._executor.fetchall(_LOCK.replace(" FOR UPDATE", ""), (entry_id,))
        if not state:
            raise UnknownEntry(entry_id)
        arabic = self._executor.fetchall(_ARABIC_STATE, (entry_id,))
        if not arabic or str(arabic[0][0]) != ReviewState.APPROVED.value:
            raise ArabicNotApproved(entry_id)
        if str(state[0][0]) != MetadataState.NONE.value:
            raise AlreadyDrafted(entry_id)
        return tuple(str(r[0]) for r in self._executor.fetchall(_ARABIC_LINES, (entry_id,)))

    def store_draft(self, entry_id: str, draft: MetadataDraft, actor: str) -> None:
        with self._executor.transaction():
            locked = self._executor.fetchall(_LOCK, (entry_id,))
            if not locked:
                raise UnknownEntry(entry_id)
            if str(locked[0][0]) != MetadataState.NONE.value:
                raise AlreadyDrafted(entry_id)
            keywords = list(tidy_keywords(draft.keywords))
            self._executor.execute(
                _WRITE,
                (draft.title, draft.question, keywords, MetadataState.DRAFT.value, entry_id),
            )
            self._executor.execute(
                _LOG,
                (
                    entry_id,
                    "metadata_draft",
                    actor,
                    json.dumps(
                        {"after": {"title": draft.title, "question": draft.question,
                                   "keywords": keywords}}
                    ),
                ),
            )

    def save(
        self, entry_id: str, title: str, question: str, keywords: tuple[str, ...], actor: str
    ) -> None:
        title, question = title.strip(), question.strip()
        with self._executor.transaction():
            if not self._executor.fetchall(_LOCK, (entry_id,)):
                raise UnknownEntry(entry_id)
            if not title:
                raise EmptyTitle(entry_id)
            before = _fields(self._executor.fetchall(_GET, (entry_id,))[0])
            tidy = list(tidy_keywords(keywords))
            self._executor.execute(
                _WRITE, (title, question, tidy, MetadataState.CONFIRMED.value, entry_id)
            )
            self._executor.execute(
                _LOG,
                (
                    entry_id,
                    "metadata_edit",
                    actor,
                    json.dumps(
                        {"before": before,
                         "after": {"title": title, "question": question, "keywords": tidy}}
                    ),
                ),
            )


__all__ = ["PgMetadata"]
