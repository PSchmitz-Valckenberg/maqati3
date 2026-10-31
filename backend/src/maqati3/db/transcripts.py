"""`transcription.Transcripts` over Postgres: the audio in, the draft rows out.

`store` is one transaction. It locks the entry, refuses if a single segment is already
there, and only then writes — so two workers that both finished the same job cannot
interleave their timelines, and a reviewer's corrections are never overwritten by a
straggler whose lease had lapsed.
"""

from __future__ import annotations

from pathlib import Path

from maqati3.asr import AsrTranscript
from maqati3.db.sql import Executor
from maqati3.transcription import AlreadyTranscribed, EmptyTranscript, UnknownEntry

#: The file a registered entry came from. Still the staged upload: nothing moves it
#: until an entry is published, and the admin dashboard plays the same file.
_MEDIA = """
SELECT staged_path FROM submission WHERE entry_id = %s AND state = 'registered'
"""

_LOCK_ENTRY = "SELECT 1 FROM entry WHERE id = %s FOR UPDATE"
_HAS_SEGMENTS = "SELECT 1 FROM segment WHERE entry_id = %s LIMIT 1"

#: span_role and citable are left to their column defaults, 'unclear' and false. Both
#: are statements about human review, and this row has had none.
_NEW_SEGMENT = """
INSERT INTO segment (entry_id, idx, t_start_ms, t_end_ms) VALUES (%s, %s, %s, %s)
RETURNING id
"""
_NEW_TEXT = """
INSERT INTO segment_text (segment_id, lang, text_raw, provenance)
VALUES (%s, %s, %s, 'asr')
"""
_DRAFT_READY = """
INSERT INTO entry_language (entry_id, lang, state) VALUES (%s, %s, 'draft_ready')
ON CONFLICT (entry_id, lang) DO UPDATE SET state = 'draft_ready', updated_at = now()
"""


class PgTranscripts:
    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    def media_path(self, entry_id: str) -> Path | None:
        rows = self._executor.fetchall(_MEDIA, (entry_id,))
        return Path(str(rows[0][0])) if rows else None

    def store(self, entry_id: str, transcript: AsrTranscript) -> int:
        if not transcript.lines:
            raise EmptyTranscript(entry_id)
        lang = transcript.lang.value
        with self._executor.transaction():
            if not self._executor.fetchall(_LOCK_ENTRY, (entry_id,)):
                raise UnknownEntry(entry_id)
            if self._executor.fetchall(_HAS_SEGMENTS, (entry_id,)):
                raise AlreadyTranscribed(entry_id)
            for idx, line in enumerate(transcript.lines):
                rows = self._executor.fetchall(
                    _NEW_SEGMENT, (entry_id, idx, line.t_start_ms, line.t_end_ms)
                )
                self._executor.execute(_NEW_TEXT, (rows[0][0], lang, line.text))
            self._executor.execute(_DRAFT_READY, (entry_id, lang))
        return len(transcript.lines)


__all__ = ["PgTranscripts"]
