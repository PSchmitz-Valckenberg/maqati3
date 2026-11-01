"""Asking for a transcription, and storing the one that comes back.

Two gates, both in Postgres because both are about what a transaction may do while
another one is running:

* **Ask once.** ASR is paid per run and a second run on the same entry would also mean
  two writers on one timeline. A request is refused while one is queued, and refused
  outright once there is anything to overwrite.
* **Never overwrite.** A transcript that exists may be a reviewer's corrected one. The
  worker writes a draft only where there is none.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from maqati3.asr import AsrLine, AsrTranscript
from maqati3.db.admin import PgDesk
from maqati3.db.submissions import PgSubmissions
from maqati3.db.transcripts import PgTranscripts
from maqati3.dedup.fingerprint import Fingerprint
from maqati3.domain import Lang
from maqati3.transcription import (
    JOB_KIND,
    AlreadyQueued,
    AlreadyTranscribed,
    EmptyTranscript,
    TranscriptState,
    UnknownEntry,
)

REPO_MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations"
SCHEMA = "maqati3_asrtest"

requires_database = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="integration test: set DATABASE_URL to a Postgres with pgvector",
)


@contextmanager
def migrated_schema() -> Iterator[tuple[Any, Any]]:
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
            connection.execute(
                "INSERT INTO scholar (id, name_ar, name_en) VALUES "
                "('ibn-uthaymin', 'ابن عثيمين', 'Ibn Uthaymin')"
            )
            yield connection, executor
        finally:
            connection.execute("SET search_path TO public")
            connection.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")


def registered_entry(executor: Any, sha: str = "aa" * 32) -> str:
    """An upload kept by a contributor and registered by an admin: a draft entry."""
    submissions = PgSubmissions(executor)
    submissions.record(
        sha256=sha,
        original_name=f"{sha}.mp4",
        staged_path=Path(f"/staging/{sha}.mp4"),
        fingerprint=Fingerprint(items=tuple(range(1000, 1800)), duration_ms=80_333),
        candidate_keys=[],
    )
    submissions.keep(sha, "Abdullah")
    return PgDesk(executor).register(sha, "ibn-uthaymin", "yusuf@example.org")


def jobs(connection: Any) -> list[tuple[Any, ...]]:
    return list(
        connection.execute(
            "SELECT id, kind, payload, state FROM job ORDER BY id"
        ).fetchall()
    )


DRAFT = AsrTranscript(
    lang=Lang.AR,
    lines=(
        AsrLine(t_start_ms=0, t_end_ms=2400, text="ما حكم هذا؟"),
        AsrLine(t_start_ms=2500, t_end_ms=6000, text="هذا جائز."),
    ),
)


# ------------------------------------------------------- asking: the blocked cases


@requires_database
def test_integration_a_transcription_cannot_be_asked_for_an_entry_that_is_not_there() -> None:
    with migrated_schema() as (connection, executor):
        with pytest.raises(UnknownEntry):
            PgDesk(executor).request_transcription("nobody-000001", "yusuf@example.org")

        assert jobs(connection) == []


@requires_database
def test_integration_an_entry_whose_arabic_is_being_worked_on_is_not_transcribed_again() -> None:
    # The expensive mistake: a run that overwrites a reviewer's corrections with ASR
    # output, and bills us for doing it.
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)
        connection.execute(
            "UPDATE entry_language SET state = 'in_progress' WHERE entry_id = %s AND lang = 'ar'",
            (entry_id,),
        )

        with pytest.raises(AlreadyTranscribed):
            PgDesk(executor).request_transcription(entry_id, "yusuf@example.org")

        assert jobs(connection) == []


@requires_database
def test_integration_an_entry_that_already_has_lines_is_not_transcribed_again() -> None:
    # Belt and braces: an imported transcript can leave the review state untouched, and
    # the rows are what a run would overwrite.
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)
        connection.execute(
            "INSERT INTO segment (entry_id, idx, t_start_ms) VALUES (%s, 0, 0)", (entry_id,)
        )

        with pytest.raises(AlreadyTranscribed):
            PgDesk(executor).request_transcription(entry_id, "yusuf@example.org")

        assert jobs(connection) == []


@requires_database
def test_integration_a_second_request_while_one_is_queued_adds_no_second_job() -> None:
    # The cost guard. Two jobs for one entry are two ASR bills and two writers on one
    # timeline; an impatient second click must not buy either.
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)
        desk = PgDesk(executor)
        desk.request_transcription(entry_id, "yusuf@example.org")

        with pytest.raises(AlreadyQueued):
            desk.request_transcription(entry_id, "yusuf@example.org")

        assert len(jobs(connection)) == 1


@requires_database
def test_integration_a_request_is_allowed_again_after_a_run_gave_up() -> None:
    # A job out of attempts leaves nothing behind. Refusing here would mean one bad
    # upload could never be transcribed again without a hand in the database.
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)
        desk = PgDesk(executor)
        desk.request_transcription(entry_id, "yusuf@example.org")
        connection.execute("UPDATE job SET state = 'failed'")

        desk.request_transcription(entry_id, "yusuf@example.org")

        assert len(jobs(connection)) == 2


# ------------------------------------------------------- asking: the one that goes through


@requires_database
def test_integration_asking_queues_one_job_for_the_entry_and_records_who_asked() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)

        job_id = PgDesk(executor).request_transcription(entry_id, "yusuf@example.org")

        (row,) = jobs(connection)
        assert (row[0], row[1], row[3]) == (job_id, JOB_KIND, "pending")
        assert row[2]["entry_id"] == entry_id
        logged = connection.execute(
            "SELECT admin_email, action, subject FROM admin_log WHERE action = 'transcribe'"
        ).fetchall()
        assert logged == [("yusuf@example.org", "transcribe", entry_id)]


@requires_database
def test_integration_the_file_to_transcribe_is_found_by_the_entry_id() -> None:
    with migrated_schema() as (_, executor):
        entry_id = registered_entry(executor)

        path = PgTranscripts(executor).media_path(entry_id)

        assert path == Path(f"/staging/{'aa' * 32}.mp4")
        assert PgTranscripts(executor).media_path("nobody-000001") is None


# ------------------------------------------------------- storing: the blocked cases


@requires_database
def test_integration_a_transcript_is_never_written_over_one_that_is_already_there() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)
        connection.execute(
            "INSERT INTO segment (entry_id, idx, t_start_ms, citable) VALUES (%s, 0, 42, true)",
            (entry_id,),
        )

        with pytest.raises(AlreadyTranscribed):
            PgTranscripts(executor).store(entry_id, DRAFT)

        rows = connection.execute(
            "SELECT t_start_ms, citable FROM segment WHERE entry_id = %s", (entry_id,)
        ).fetchall()
        assert rows == [(42, True)]


@requires_database
def test_integration_a_run_that_found_no_words_stores_nothing_and_can_be_repeated() -> None:
    # An empty transcript means the audio was unusable, not that the work is done.
    # Marking it draft_ready would put an empty table in front of a reviewer and close
    # the entry to another attempt.
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)

        with pytest.raises(EmptyTranscript):
            PgTranscripts(executor).store(entry_id, AsrTranscript(lang=Lang.AR, lines=()))

        state = connection.execute(
            "SELECT state FROM entry_language WHERE entry_id = %s AND lang = 'ar'", (entry_id,)
        ).fetchone()
        assert state == ("not_started",)
        assert connection.execute("SELECT count(*) FROM segment").fetchone() == (0,)


# ------------------------------------------------------- storing: the one that goes through


@requires_database
def test_integration_a_stored_draft_is_not_citable_and_is_nobody_s_words_yet() -> None:
    # The whole reason a machine transcript may be stored at all: it cannot be quoted.
    # `citable` says a human confirmed the second; `span_role` says whose words these
    # are. ASR confirms neither, and the retrieval view reads both.
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)

        PgTranscripts(executor).store(entry_id, DRAFT)

        rows = connection.execute(
            "SELECT s.idx, s.t_start_ms, s.t_end_ms, s.span_role, s.citable, t.text_raw, "
            "t.provenance FROM segment s JOIN segment_text t ON t.segment_id = s.id "
            "WHERE s.entry_id = %s ORDER BY s.idx",
            (entry_id,),
        ).fetchall()
        assert rows == [
            (0, 0, 2400, "unclear", False, "ما حكم هذا؟", "asr"),
            (1, 2500, 6000, "unclear", False, "هذا جائز.", "asr"),
        ]


@requires_database
def test_integration_a_stored_draft_puts_the_arabic_in_front_of_a_reviewer() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)

        stored = PgTranscripts(executor).store(entry_id, DRAFT)

        assert stored == 2
        states = dict(
            connection.execute(
                "SELECT lang, state FROM entry_language WHERE entry_id = %s", (entry_id,)
            ).fetchall()
        )
        # Only the language that was transcribed moves. The translations are a separate
        # piece of work, each approved on its own.
        assert states == {"ar": "draft_ready", "en": "not_started", "de": "not_started"}


# ------------------------------------------------------- what the dashboard is told


def only_item(executor: Any) -> Any:
    (item,) = PgDesk(executor).items()
    return item


@requires_database
def test_integration_a_fresh_entry_offers_a_transcription_and_claims_none() -> None:
    with migrated_schema() as (_, executor):
        registered_entry(executor)

        assert only_item(executor).transcript is TranscriptState.NONE


@requires_database
def test_integration_the_dashboard_follows_the_run_from_queued_to_running() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)
        PgDesk(executor).request_transcription(entry_id, "yusuf@example.org")

        assert only_item(executor).transcript is TranscriptState.QUEUED

        connection.execute("UPDATE job SET state = 'running'")

        assert only_item(executor).transcript is TranscriptState.RUNNING


@requires_database
def test_integration_a_failed_run_shows_its_reason_so_an_admin_can_act() -> None:
    # "It did not work" is not enough to decide whether to ask again or replace the file.
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)
        PgDesk(executor).request_transcription(entry_id, "yusuf@example.org")
        connection.execute(
            "UPDATE job SET state = 'failed', last_error = 'nothing to transcribe: no audio'"
        )

        item = only_item(executor)

        assert item.transcript is TranscriptState.FAILED
        assert item.transcript_error is not None
        assert "no audio" in item.transcript_error


@requires_database
def test_integration_a_stored_transcript_is_what_the_dashboard_reports() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = registered_entry(executor)
        PgDesk(executor).request_transcription(entry_id, "yusuf@example.org")
        connection.execute("UPDATE job SET state = 'done'")
        PgTranscripts(executor).store(entry_id, DRAFT)

        item = only_item(executor)

        assert item.transcript is TranscriptState.READY
        assert item.transcript_error is None
