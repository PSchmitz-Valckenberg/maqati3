"""The review editor's rules, in Postgres.

An editor changes what the archive will one day quote, so the rules are properties of the
database and not of the page: rows are edited and never added, removed or moved; every
change leaves a line in the append-only `revision_log` *in the same transaction* (no log
row, no edit); a language moves only along the state machine; and nobody edits a language
someone else has taken.

The blocked cases come first in each group.
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
from maqati3.db.review import PgReview
from maqati3.db.submissions import PgSubmissions
from maqati3.db.transcripts import PgTranscripts
from maqati3.db.translations import PgTranslations
from maqati3.dedup.fingerprint import Fingerprint
from maqati3.domain import Lang, ReviewState
from maqati3.register.states import InvalidTransition
from maqati3.review import (
    ArabicNotApproved,
    ClaimedByOther,
    EmptyText,
    NotInProgress,
    UnknownRow,
)
from maqati3.transcription import UnknownEntry

REPO_MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations"
SCHEMA = "maqati3_reviewtest"

requires_database = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="integration test: set DATABASE_URL to a Postgres with pgvector",
)

YUSUF = "yusuf@example.org"
AISHA = "aisha@example.org"

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


def transcribed_entry(executor: Any, sha: str = "aa" * 32) -> str:
    submissions = PgSubmissions(executor)
    submissions.record(
        sha256=sha,
        original_name=f"{sha}.mp4",
        staged_path=Path(f"/staging/{sha}.mp4"),
        fingerprint=Fingerprint(items=tuple(range(1000, 1800)), duration_ms=80_333),
        candidate_keys=[],
    )
    submissions.keep(sha, "Abdullah")
    entry_id = PgDesk(executor).register(sha, "ibn-uthaymin", YUSUF)
    PgTranscripts(executor).store(entry_id, ARABIC)
    return entry_id


def drafted_entry(executor: Any, connection: Any) -> str:
    """Arabic approved, English drafted: the state the editor meets on a real entry."""
    entry_id = transcribed_entry(executor)
    set_state(connection, entry_id, "ar", "approved")
    PgTranslations(executor).store(entry_id, Lang.EN, ENGLISH)
    return entry_id


def set_state(connection: Any, entry_id: str, lang: str, state: str, who: str | None = None) -> None:
    connection.execute(
        "UPDATE entry_language SET state = %s, assignee = %s WHERE entry_id = %s AND lang = %s",
        (state, who, entry_id, lang),
    )


def text_of(connection: Any, entry_id: str, idx: int, lang: str) -> tuple[str, str]:
    row = connection.execute(
        "SELECT t.text_raw, t.provenance FROM segment s JOIN segment_text t ON t.segment_id = s.id"
        " WHERE s.entry_id = %s AND s.idx = %s AND t.lang = %s",
        (entry_id, idx, lang),
    ).fetchone()
    return str(row[0]), str(row[1])


def revisions(connection: Any) -> list[tuple[Any, ...]]:
    return list(
        connection.execute(
            "SELECT entity, entity_id, action, actor, detail FROM revision_log ORDER BY id"
        ).fetchall()
    )


def state_of(connection: Any, entry_id: str, lang: str) -> tuple[str, str | None]:
    row = connection.execute(
        "SELECT state, assignee FROM entry_language WHERE entry_id = %s AND lang = %s",
        (entry_id, lang),
    ).fetchone()
    return str(row[0]), row[1]


# ------------------------------------------------------------------ reading


@requires_database
def test_integration_an_unknown_entry_has_no_review_view() -> None:
    with migrated_schema() as (_, executor):
        assert PgReview(executor).view("nobody-000001") is None


@requires_database
def test_integration_the_view_is_one_row_per_moment_with_every_language() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = drafted_entry(executor, connection)

        view = PgReview(executor).view(entry_id)

        assert view is not None
        assert [(r.idx, r.t_start_ms, r.t_end_ms) for r in view.rows] == [
            (0, 0, 2400),
            (1, 2500, 6000),
        ]
        assert view.rows[0].texts == {Lang.AR: "ما حكم هذا؟", Lang.EN: ENGLISH[0]}
        assert view.states[Lang.AR].state is ReviewState.APPROVED
        assert view.states[Lang.EN].state is ReviewState.DRAFT_READY
        assert Lang.DE not in view.states or view.states[Lang.DE].state is ReviewState.NOT_STARTED


# ------------------------------------------------------------------ editing: blocked


@requires_database
@pytest.mark.parametrize("state", ["draft_ready", "awaiting_review", "needs_fixes", "approved"])
def test_integration_a_language_is_edited_only_while_someone_is_working_on_it(state: str) -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", state, YUSUF)

        with pytest.raises(NotInProgress):
            PgReview(executor).edit_text(entry_id, 0, Lang.AR, "نص جديد", YUSUF)

        assert text_of(connection, entry_id, 0, "ar") == ("ما حكم هذا؟", "asr")
        assert revisions(connection) == []


@requires_database
def test_integration_nobody_edits_a_language_someone_else_has_taken() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", "in_progress", YUSUF)

        with pytest.raises(ClaimedByOther):
            PgReview(executor).edit_text(entry_id, 0, Lang.AR, "نص جديد", AISHA)

        assert text_of(connection, entry_id, 0, "ar")[0] == "ما حكم هذا؟"
        assert revisions(connection) == []


@requires_database
def test_integration_a_row_that_is_not_there_is_not_created_by_editing_it() -> None:
    # Rows are edited, never added: that is what keeps every timestamp valid.
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", "in_progress", YUSUF)

        with pytest.raises(UnknownRow):
            PgReview(executor).edit_text(entry_id, 2, Lang.AR, "سطر زائد", YUSUF)

        count = connection.execute(
            "SELECT count(*) FROM segment WHERE entry_id = %s", (entry_id,)
        ).fetchone()
        assert count[0] == 2


@requires_database
def test_integration_a_language_with_no_text_yet_is_not_filled_in_by_editing() -> None:
    # German has no draft; typing a line into it would make row counts differ.
    with migrated_schema() as (connection, executor):
        entry_id = drafted_entry(executor, connection)
        set_state(connection, entry_id, "de", "in_progress", YUSUF)

        with pytest.raises(UnknownRow):
            PgReview(executor).edit_text(entry_id, 0, Lang.DE, "Was ist das Urteil?", YUSUF)


@requires_database
@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_integration_a_row_is_never_emptied(text: str) -> None:
    # An empty row is a deleted row that still occupies its second.
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", "in_progress", YUSUF)

        with pytest.raises(EmptyText):
            PgReview(executor).edit_text(entry_id, 0, Lang.AR, text, YUSUF)

        assert text_of(connection, entry_id, 0, "ar")[0] == "ما حكم هذا؟"


@requires_database
def test_integration_an_edit_of_an_unknown_entry_is_refused() -> None:
    with migrated_schema() as (_, executor):
        with pytest.raises(UnknownEntry):
            PgReview(executor).edit_text("nobody-000001", 0, Lang.AR, "x", YUSUF)


# ------------------------------------------------------------------ editing: allowed


@requires_database
def test_integration_an_edit_replaces_the_text_marks_it_human_and_is_logged() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", "in_progress", YUSUF)

        PgReview(executor).edit_text(entry_id, 0, Lang.AR, "  ما حكم هذا الفعل؟ ", YUSUF)

        assert text_of(connection, entry_id, 0, "ar") == ("ما حكم هذا الفعل؟", "human")
        assert text_of(connection, entry_id, 1, "ar") == ("هذا جائز.", "asr")
        [(entity, entity_id, action, actor, detail)] = revisions(connection)
        assert (entity, entity_id, action, actor) == (
            "segment_text",
            f"{entry_id}:0:ar",
            "edit",
            YUSUF,
        )
        assert detail == {"before": "ما حكم هذا؟", "after": "ما حكم هذا الفعل؟"}


@requires_database
def test_integration_saving_the_same_text_changes_nothing_and_logs_nothing() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", "in_progress", YUSUF)

        PgReview(executor).edit_text(entry_id, 0, Lang.AR, "ما حكم هذا؟", YUSUF)

        assert text_of(connection, entry_id, 0, "ar") == ("ما حكم هذا؟", "asr")
        assert revisions(connection) == []


@requires_database
def test_integration_an_edit_never_touches_the_timeline() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", "in_progress", YUSUF)

        PgReview(executor).edit_text(entry_id, 1, Lang.AR, "هذا جائز إن شاء الله.", YUSUF)

        rows = connection.execute(
            "SELECT idx, t_start_ms, t_end_ms, citable FROM segment WHERE entry_id = %s"
            " ORDER BY idx",
            (entry_id,),
        ).fetchall()
        assert rows == [(0, 0, 2400, False), (1, 2500, 6000, False)]


# ------------------------------------------------------------------ moving: blocked


@requires_database
@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("draft_ready", "approved"),
        ("draft_ready", "awaiting_review"),
        ("in_progress", "approved"),
        ("in_progress", "draft_ready"),
        ("awaiting_review", "in_progress"),
        ("approved", "in_progress"),
        ("approved", "needs_fixes"),
        ("needs_fixes", "approved"),
    ],
)
def test_integration_a_language_moves_only_along_the_state_machine(
    start: str, target: str
) -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", start, YUSUF)

        with pytest.raises(InvalidTransition):
            PgReview(executor).move(entry_id, Lang.AR, ReviewState(target), YUSUF)

        assert state_of(connection, entry_id, "ar") == (start, YUSUF)
        assert revisions(connection) == []


@requires_database
def test_integration_a_draft_is_made_by_the_worker_never_by_a_click() -> None:
    # not_started -> draft_ready is allowed by the machine, but it would declare a language
    # drafted that has no rows. Only the jobs that write the rows may do it.
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)

        with pytest.raises(InvalidTransition):
            PgReview(executor).move(entry_id, Lang.DE, ReviewState.DRAFT_READY, YUSUF)

        assert state_of(connection, entry_id, "de") == ("not_started", None)


@requires_database
def test_integration_nobody_moves_a_language_someone_else_is_working_on() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", "in_progress", YUSUF)

        with pytest.raises(ClaimedByOther):
            PgReview(executor).move(entry_id, Lang.AR, ReviewState.AWAITING_REVIEW, AISHA)

        assert state_of(connection, entry_id, "ar") == ("in_progress", YUSUF)


@requires_database
@pytest.mark.parametrize("target", ["in_progress"])
def test_integration_a_translation_waits_for_the_approved_arabic(target: str) -> None:
    # The same rule as the drafts button, held at the one place that moves the state.
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        PgTranslations(executor).store(entry_id, Lang.EN, ENGLISH)

        with pytest.raises(ArabicNotApproved):
            PgReview(executor).move(entry_id, Lang.EN, ReviewState(target), YUSUF)

        assert state_of(connection, entry_id, "en") == ("draft_ready", None)


@requires_database
def test_integration_a_move_on_an_unknown_entry_is_refused() -> None:
    with migrated_schema() as (_, executor):
        with pytest.raises(UnknownEntry):
            PgReview(executor).move("nobody-000001", Lang.AR, ReviewState.IN_PROGRESS, YUSUF)


# ------------------------------------------------------------------ moving: allowed


@requires_database
def test_integration_taking_a_language_puts_the_name_on_it_and_logs_it() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)

        PgReview(executor).move(entry_id, Lang.AR, ReviewState.IN_PROGRESS, YUSUF)

        assert state_of(connection, entry_id, "ar") == ("in_progress", YUSUF)
        [(entity, entity_id, action, actor, detail)] = revisions(connection)
        assert (entity, entity_id, action, actor) == (
            "entry_language",
            f"{entry_id}:ar",
            "state",
            YUSUF,
        )
        assert detail == {"from": "draft_ready", "to": "in_progress"}


@requires_database
def test_integration_the_whole_way_from_draft_to_approved() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        review = PgReview(executor)

        review.move(entry_id, Lang.AR, ReviewState.IN_PROGRESS, YUSUF)
        review.edit_text(entry_id, 0, Lang.AR, "ما حكم هذا الفعل؟", YUSUF)
        review.move(entry_id, Lang.AR, ReviewState.AWAITING_REVIEW, YUSUF)
        review.move(entry_id, Lang.AR, ReviewState.APPROVED, AISHA)

        assert state_of(connection, entry_id, "ar")[0] == "approved"
        assert [r[2] for r in revisions(connection)] == ["state", "edit", "state", "state"]


@requires_database
def test_integration_work_sent_back_is_taken_again_by_whoever_picks_it_up() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", "awaiting_review", YUSUF)
        review = PgReview(executor)

        review.move(entry_id, Lang.AR, ReviewState.NEEDS_FIXES, AISHA)
        review.move(entry_id, Lang.AR, ReviewState.IN_PROGRESS, AISHA)

        assert state_of(connection, entry_id, "ar") == ("in_progress", AISHA)


@requires_database
def test_integration_the_first_translation_can_be_taken_once_the_arabic_is_approved() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = drafted_entry(executor, connection)

        PgReview(executor).move(entry_id, Lang.EN, ReviewState.IN_PROGRESS, YUSUF)

        assert state_of(connection, entry_id, "en") == ("in_progress", YUSUF)
