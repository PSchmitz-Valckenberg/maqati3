"""`translation.Translations` over Postgres.

`store` is one transaction, with the entry locked. It refuses if the language already
has a single line, refuses if the draft has a different number of lines than the
timeline it is attaching to, and only then writes — so a straggler whose lease had
lapsed cannot overwrite a reviewer's work, and a miscounted draft cannot shift every
later line onto the wrong second.
"""

from __future__ import annotations

from collections.abc import Sequence

from maqati3.db.sql import Executor
from maqati3.domain import Lang
from maqati3.translate import LineCountMismatch
from maqati3.translation import AlreadyTranslated, UnknownEntry

_LOCK_ENTRY = "SELECT 1 FROM entry WHERE id = %s FOR UPDATE"

_SOURCE_LINES = """
SELECT t.text_raw FROM segment s JOIN segment_text t ON t.segment_id = s.id
 WHERE s.entry_id = %s AND t.lang = %s ORDER BY s.idx
"""

#: The timeline the draft attaches to. One row per moment, in order: the draft's line
#: N belongs to segment N, which is what makes a deep link in German land where the
#: Arabic was spoken.
_SEGMENT_IDS = "SELECT id FROM segment WHERE entry_id = %s ORDER BY idx"

_HAS_TEXT = """
SELECT 1 FROM segment s JOIN segment_text t ON t.segment_id = s.id
 WHERE s.entry_id = %s AND t.lang = %s LIMIT 1
"""
#: A language a person has started on is not empty either, whatever the text table says.
_LANGUAGE_STATE = "SELECT state FROM entry_language WHERE entry_id = %s AND lang = %s"

_NEW_TEXT = """
INSERT INTO segment_text (segment_id, lang, text_raw, provenance)
VALUES (%s, %s, %s, 'machine_translation')
"""
_DRAFT_READY = """
INSERT INTO entry_language (entry_id, lang, state) VALUES (%s, %s, 'draft_ready')
ON CONFLICT (entry_id, lang) DO UPDATE SET state = 'draft_ready', updated_at = now()
"""


class PgTranslations:
    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    def source_lines(self, entry_id: str, lang: Lang) -> tuple[str, ...]:
        rows = self._executor.fetchall(_SOURCE_LINES, (entry_id, lang.value))
        return tuple(str(row[0]) for row in rows)

    def store(self, entry_id: str, target: Lang, lines: Sequence[str]) -> int:
        with self._executor.transaction():
            if not self._executor.fetchall(_LOCK_ENTRY, (entry_id,)):
                raise UnknownEntry(entry_id)
            if self._executor.fetchall(_HAS_TEXT, (entry_id, target.value)):
                raise AlreadyTranslated(f"{entry_id} already has {target.value}")
            segments = [row[0] for row in self._executor.fetchall(_SEGMENT_IDS, (entry_id,))]
            if len(segments) != len(lines):
                raise LineCountMismatch(
                    f"{entry_id}: {len(segments)} rows of Arabic, {len(lines)} of "
                    f"{target.value}"
                )
            for segment_id, line in zip(segments, lines, strict=True):
                self._executor.execute(_NEW_TEXT, (segment_id, target.value, line))
            self._executor.execute(_DRAFT_READY, (entry_id, target.value))
        return len(lines)

    def untouched_languages(self, entry_id: str, targets: Sequence[Lang]) -> list[Lang]:
        """Of `targets`, the ones with no text and nobody working on them yet."""
        free = []
        for target in targets:
            if self._executor.fetchall(_HAS_TEXT, (entry_id, target.value)):
                continue
            state = self._executor.fetchall(_LANGUAGE_STATE, (entry_id, target.value))
            if state and str(state[0][0]) != "not_started":
                continue
            free.append(target)
        return free


__all__ = ["PgTranslations"]
