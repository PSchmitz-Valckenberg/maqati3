"""The worker that runs one claimed transcription job.

Against a real queue (Postgres) with a fake provider: what the worker must get right is
what it does with the job row when a run goes wrong, and that is a property of the
queue, not of Soniox.

The rule behind most of these: a run that produced nothing must leave the entry exactly
as it was, so an admin can ask again. A run whose result arrived too late must throw its
result away rather than overwrite what is there.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from maqati3.worker import Skipped, Stored, work_once

from maqati3.asr import AsrError, AsrLine, AsrTranscript
from maqati3.db.queue import Dead, Retry
from maqati3.domain import Lang
from maqati3.transcription import AlreadyTranscribed, EmptyTranscript

REPO_MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations"
SCHEMA = "maqati3_workertest"

requires_database = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="integration test: set DATABASE_URL to a Postgres with pgvector",
)

ENTRY = "ibn-uthaymin-000421"
AUDIO = Path("/staging/recording.m4a")

DRAFT = AsrTranscript(
    lang=Lang.AR, lines=(AsrLine(t_start_ms=0, t_end_ms=2400, text="هذا جائز."),)
)


@contextmanager
def queue_schema() -> Iterator[tuple[Any, Any]]:
    import psycopg

    from maqati3.db.migrate import migrate
    from maqati3.db.sql import PsycopgExecutor

    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as connection:
        connection.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
        connection.execute(f"CREATE SCHEMA {SCHEMA}")
        try:
            connection.execute(f"SET search_path TO {SCHEMA}, public")
            executor = PsycopgExecutor(connection)
            migrate(executor, REPO_MIGRATIONS)
            yield connection, executor
        finally:
            connection.execute("SET search_path TO public")
            connection.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


def enqueue(connection: Any, entry_id: str = ENTRY) -> int:
    row = connection.execute(
        "INSERT INTO job (kind, payload) VALUES ('transcribe', %s::jsonb) RETURNING id",
        (f'{{"entry_id": "{entry_id}", "lang": "ar"}}',),
    ).fetchone()
    return int(row[0])


def job_row(connection: Any, job_id: int) -> tuple[str, str | None]:
    state, error = connection.execute(
        "SELECT state, last_error FROM job WHERE id = %s", (job_id,)
    ).fetchone()
    return str(state), None if error is None else str(error)


class FakeTranscriber:
    """Answers with one prepared transcript, or raises. Records every call."""

    def __init__(self, result: AsrTranscript | Exception = DRAFT) -> None:
        self._result = result
        self.calls: list[tuple[Path, Lang]] = []

    def transcribe(self, path: Path, *, lang: Lang) -> AsrTranscript:
        self.calls.append((path, lang))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class FakeTranscripts:
    def __init__(self, media: Path | None = AUDIO, on_store: Exception | None = None) -> None:
        self._media = media
        self._on_store = on_store
        self.stored: list[tuple[str, AsrTranscript]] = []

    def media_path(self, entry_id: str) -> Path | None:
        return self._media

    def store(self, entry_id: str, transcript: AsrTranscript) -> int:
        if self._on_store is not None:
            raise self._on_store
        self.stored.append((entry_id, transcript))
        return len(transcript.lines)


def run(executor: Any, transcriber: Any, transcripts: Any) -> Any:
    return work_once(executor, transcriber=transcriber, transcripts=transcripts)


@requires_database
def test_integration_an_empty_queue_never_calls_the_provider() -> None:
    with queue_schema() as (_, executor):
        transcriber = FakeTranscriber()

        assert run(executor, transcriber, FakeTranscripts()) is None
        assert transcriber.calls == []


@requires_database
def test_integration_a_missing_audio_file_is_not_sent_to_the_provider() -> None:
    with queue_schema() as (connection, executor):
        job_id = enqueue(connection)
        transcriber = FakeTranscriber()

        outcome = run(executor, transcriber, FakeTranscripts(media=None))

        assert isinstance(outcome, Retry)
        assert transcriber.calls == []
        assert job_row(connection, job_id)[0] == "pending"


@requires_database
def test_integration_a_provider_failure_stores_nothing_and_is_tried_again() -> None:
    with queue_schema() as (connection, executor):
        job_id = enqueue(connection)
        transcripts = FakeTranscripts()

        outcome = run(executor, FakeTranscriber(AsrError("upstream said 503")), transcripts)

        assert isinstance(outcome, Retry)
        assert transcripts.stored == []
        state, error = job_row(connection, job_id)
        assert state == "pending"
        assert error is not None and "503" in error


@requires_database
def test_integration_a_result_that_arrived_too_late_is_dropped_not_written() -> None:
    # Someone else's run won, or a reviewer typed the transcript in the meantime. The
    # money is spent either way; overwriting their work would be the real loss.
    with queue_schema() as (connection, executor):
        job_id = enqueue(connection)

        transcripts = FakeTranscripts(on_store=AlreadyTranscribed(ENTRY))

        outcome = run(executor, FakeTranscriber(), transcripts)

        assert isinstance(outcome, Skipped)
        assert transcripts.stored == []
        # Done, not retried: asking the provider again would buy the same answer twice.
        assert job_row(connection, job_id) == ("done", None)


@requires_database
def test_integration_a_run_that_found_no_words_is_not_paid_for_four_more_times() -> None:
    # The same audio will be just as silent next time, so this one failure is terminal.
    # The admin sees it and can ask again once the file is replaced.
    with queue_schema() as (connection, executor):
        job_id = enqueue(connection)

        outcome = run(executor, FakeTranscriber(), FakeTranscripts(on_store=EmptyTranscript(ENTRY)))

        assert isinstance(outcome, Dead)
        state, error = job_row(connection, job_id)
        assert state == "failed"
        assert error is not None


@requires_database
def test_integration_a_finished_run_stores_the_draft_and_closes_the_job() -> None:
    with queue_schema() as (connection, executor):
        job_id = enqueue(connection)
        transcriber = FakeTranscriber()
        transcripts = FakeTranscripts()

        outcome = run(executor, transcriber, transcripts)

        assert outcome == Stored(entry_id=ENTRY, lines=1)
        assert transcriber.calls == [(AUDIO, Lang.AR)]
        assert transcripts.stored == [(ENTRY, DRAFT)]
        assert job_row(connection, job_id) == ("done", None)
