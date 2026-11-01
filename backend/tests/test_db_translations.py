"""Asking for draft translations, and storing the ones that come back.

The same two gates as transcription -- ask once, never overwrite -- plus the rule that
only exists for translations: **the row count is identical in every language**. It is
checked again here, where the rows are actually written, and not only in the client that
talked to the model. A client can be replaced; this is the last place before the archive.
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
from maqati3.db.translations import PgTranslations
from maqati3.dedup.fingerprint import Fingerprint
from maqati3.domain import Lang
from maqati3.transcription import AlreadyQueued, UnknownEntry
from maqati3.translate import LineCountMismatch
from maqati3.translation import (
    TRANSLATE_JOB_KIND,
    AlreadyTranslated,
    NothingToTranslate,
)

REPO_MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations"
SCHEMA = "maqati3_mttest"

requires_database = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="integration test: set DATABASE_URL to a Postgres with pgvector",
)

ARABIC = AsrTranscript(
    lang=Lang.AR,
    lines=(
        AsrLine(t_start_ms=0, t_end_ms=2400, text="ما حكم هذا؟"),
        AsrLine(t_start_ms=2500, t_end_ms=6000, text="هذا جائز."),
    ),
)
ENGLISH = ("What is the ruling on this?", "This is permitted.")


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


def transcribed_entry(executor: Any, sha: str = "aa" * 32, *, arabic: bool = True) -> str:
    submissions = PgSubmissions(executor)
    submissions.record(
        sha256=sha,
        original_name=f"{sha}.mp4",
        staged_path=Path(f"/staging/{sha}.mp4"),
        fingerprint=Fingerprint(items=tuple(range(1000, 1800)), duration_ms=80_333),
        candidate_keys=[],
    )
    submissions.keep(sha, "Abdullah")
    entry_id = PgDesk(executor).register(sha, "ibn-uthaymin", "yusuf@example.org")
    if arabic:
        PgTranscripts(executor).store(entry_id, ARABIC)
    return entry_id


def jobs(connection: Any) -> list[tuple[Any, ...]]:
    return list(
        connection.execute("SELECT id, kind, payload FROM job ORDER BY id").fetchall()
    )


# ------------------------------------------------------- asking: the blocked cases


@requires_database
def test_integration_a_translation_cannot_be_asked_for_an_entry_that_is_not_there() -> None:
    with migrated_schema() as (connection, executor):
        with pytest.raises(UnknownEntry):
            PgDesk(executor).request_translation("nobody-000001", "yusuf@example.org")

        assert jobs(connection) == []


@requires_database
def test_integration_there_is_nothing_to_translate_before_there_is_arabic() -> None:
    # Translating an entry with no transcript would pay a model to look at nothing.
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor, arabic=False)

        with pytest.raises(NothingToTranslate):
            PgDesk(executor).request_translation(entry_id, "yusuf@example.org")

        assert jobs(connection) == []


@requires_database
def test_integration_a_language_already_drafted_is_left_alone() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        PgTranslations(executor).store(entry_id, Lang.EN, ENGLISH)

        PgDesk(executor).request_translation(entry_id, "yusuf@example.org")

        # Only German is queued: English is already there and must not be overwritten.
        targets = [row[2]["target"] for row in jobs(connection)]
        assert targets == ["de"]


@requires_database
def test_integration_an_entry_whose_languages_are_all_done_is_refused() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        PgTranslations(executor).store(entry_id, Lang.EN, ENGLISH)
        PgTranslations(executor).store(entry_id, Lang.DE, ("Was ist das Urteil?", "Erlaubt."))

        with pytest.raises(AlreadyTranslated):
            PgDesk(executor).request_translation(entry_id, "yusuf@example.org")

        assert jobs(connection) == []


@requires_database
def test_integration_a_language_someone_is_working_on_is_not_drafted_over() -> None:
    # A reviewer who started typing English must not have a machine draft land on top.
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        connection.execute(
            "UPDATE entry_language SET state = 'in_progress' WHERE entry_id = %s AND lang = 'en'",
            (entry_id,),
        )

        PgDesk(executor).request_translation(entry_id, "yusuf@example.org")

        assert [row[2]["target"] for row in jobs(connection)] == ["de"]


@requires_database
def test_integration_a_second_click_while_drafts_are_on_their_way_adds_no_second_job() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        desk = PgDesk(executor)
        desk.request_translation(entry_id, "yusuf@example.org")

        with pytest.raises(AlreadyQueued):
            desk.request_translation(entry_id, "yusuf@example.org")

        assert len(jobs(connection)) == 2


@requires_database
def test_integration_translation_and_transcription_share_one_daily_budget() -> None:
    # Both spend money on the same recording. One budget is the only number an admin
    # has to understand, and the only one that cannot be bypassed by switching button.
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)

        with pytest.raises(Exception) as excinfo:
            PgDesk(executor, daily_limit_seconds=10).request_translation(
                entry_id, "yusuf@example.org"
            )

        assert "limit" in str(excinfo.value)
        assert jobs(connection) == []


# ------------------------------------------------------- storing: the blocked cases


@requires_database
def test_integration_a_draft_with_the_wrong_number_of_lines_is_not_stored() -> None:
    # The rule the whole feature exists under, checked where the rows are written.
    # A draft of two Arabic lines that comes back as one is not "mostly fine": every
    # line after it would point at the wrong second.
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)

        with pytest.raises(LineCountMismatch):
            PgTranslations(executor).store(entry_id, Lang.EN, ("One sentence for both.",))

        assert connection.execute(
            "SELECT count(*) FROM segment_text WHERE lang = 'en'"
        ).fetchone() == (0,)


@requires_database
def test_integration_a_draft_never_lands_on_a_language_that_already_has_text() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        translations = PgTranslations(executor)
        translations.store(entry_id, Lang.EN, ENGLISH)

        with pytest.raises(AlreadyTranslated):
            translations.store(entry_id, Lang.EN, ("Something else.", "And more."))

        kept = connection.execute(
            "SELECT text_raw FROM segment_text WHERE lang = 'en' ORDER BY segment_id"
        ).fetchall()
        assert [row[0] for row in kept] == list(ENGLISH)


# ------------------------------------------------------- the ones that go through


@requires_database
def test_integration_asking_queues_one_job_per_language_and_records_who_asked() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)

        queued = PgDesk(executor).request_translation(entry_id, "yusuf@example.org")

        rows = jobs(connection)
        assert len(queued) == 2
        assert {row[1] for row in rows} == {TRANSLATE_JOB_KIND}
        assert sorted(row[2]["target"] for row in rows) == ["de", "en"]
        assert all(row[2]["entry_id"] == entry_id for row in rows)
        logged = connection.execute(
            "SELECT admin_email, subject FROM admin_log WHERE action = 'translate'"
        ).fetchall()
        assert logged == [("yusuf@example.org", entry_id)]


@requires_database
def test_integration_the_arabic_comes_back_in_order_to_be_translated() -> None:
    with migrated_schema() as (_, executor):
        entry_id = transcribed_entry(executor)

        lines = PgTranslations(executor).source_lines(entry_id, Lang.AR)

        assert lines == ("ما حكم هذا؟", "هذا جائز.")


@requires_database
def test_integration_a_stored_draft_is_machine_written_and_waits_for_a_person() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)

        stored = PgTranslations(executor).store(entry_id, Lang.EN, ENGLISH)

        assert stored == 2
        rows = connection.execute(
            "SELECT s.idx, t.text_raw, t.provenance FROM segment s "
            "JOIN segment_text t ON t.segment_id = s.id "
            "WHERE s.entry_id = %s AND t.lang = 'en' ORDER BY s.idx",
            (entry_id,),
        ).fetchall()
        assert rows == [
            (0, ENGLISH[0], "machine_translation"),
            (1, ENGLISH[1], "machine_translation"),
        ]
        states = dict(
            connection.execute(
                "SELECT lang, state FROM entry_language WHERE entry_id = %s", (entry_id,)
            ).fetchall()
        )
        # Only the language that was drafted moves, and only as far as draft_ready:
        # nothing is public until a person approves that language.
        assert states == {"ar": "draft_ready", "en": "draft_ready", "de": "not_started"}
