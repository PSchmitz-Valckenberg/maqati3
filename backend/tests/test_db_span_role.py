"""Who is speaking on a row, and whether its second has been confirmed (issue #26).

Only a row marked `scholar_own` whose timestamp a person has confirmed may ever be
quoted. These tests pin the two switches that produce that, and the database view that
reads them. Blocked cases first.
"""

from __future__ import annotations

from typing import Any

import pytest

from maqati3.db.review import PgReview
from maqati3.domain import Lang, SpanRole
from maqati3.review import ClaimedByOther, NotInProgress, RoleNotSet, UnknownRow
from maqati3.transcription import UnknownEntry
from test_db_review import (
    AISHA,
    YUSUF,
    migrated_schema,
    requires_database,
    revisions,
    set_state,
    transcribed_entry,
)


def working_entry(executor: Any, connection: Any) -> str:
    """An entry whose Arabic YUSUF has taken: what the editor looks like mid-review."""
    entry_id = transcribed_entry(executor)
    set_state(connection, entry_id, "ar", "in_progress", YUSUF)
    return entry_id


def row_flags(connection: Any, entry_id: str, idx: int) -> tuple[str, bool]:
    row = connection.execute(
        "SELECT span_role, citable FROM segment WHERE entry_id = %s AND idx = %s",
        (entry_id, idx),
    ).fetchone()
    return str(row[0]), bool(row[1])


# ------------------------------------------------------------------ blocked


@requires_database
@pytest.mark.parametrize("state", ["draft_ready", "awaiting_review", "needs_fixes", "approved"])
def test_integration_a_role_is_set_only_while_the_arabic_is_being_worked_on(state: str) -> None:
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", state, YUSUF)

        with pytest.raises(NotInProgress):
            PgReview(executor).set_role(entry_id, 0, SpanRole.SCHOLAR_OWN, YUSUF)

        assert row_flags(connection, entry_id, 0) == ("unclear", False)
        assert revisions(connection) == []


@requires_database
def test_integration_nobody_sets_a_role_on_a_language_someone_else_has_taken() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)

        with pytest.raises(ClaimedByOther):
            PgReview(executor).set_role(entry_id, 0, SpanRole.SCHOLAR_OWN, AISHA)

        assert row_flags(connection, entry_id, 0) == ("unclear", False)


@requires_database
def test_integration_a_row_that_is_not_there_has_no_role() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)

        with pytest.raises(UnknownRow):
            PgReview(executor).set_role(entry_id, 9, SpanRole.SCHOLAR_OWN, YUSUF)


@requires_database
def test_integration_a_role_on_an_unknown_entry_is_refused() -> None:
    with migrated_schema() as (_, executor), pytest.raises(UnknownEntry):
        PgReview(executor).set_role("nobody-000001", 0, SpanRole.SCHOLAR_OWN, YUSUF)


@requires_database
def test_integration_a_second_cannot_be_confirmed_on_a_row_whose_speaker_is_not_known() -> None:
    # "Unclear" is the default. A timestamp confirmed on a row nobody has attributed
    # would still be unquotable, and would look finished.
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)

        with pytest.raises(RoleNotSet):
            PgReview(executor).confirm_timestamp(entry_id, 0, True, YUSUF)

        assert row_flags(connection, entry_id, 0) == ("unclear", False)
        assert revisions(connection) == []


@requires_database
@pytest.mark.parametrize("state", ["draft_ready", "awaiting_review", "needs_fixes", "approved"])
def test_integration_a_second_is_confirmed_only_while_the_arabic_is_being_worked_on(
    state: str,
) -> None:
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)
        PgReview(executor).set_role(entry_id, 0, SpanRole.SCHOLAR_OWN, YUSUF)
        set_state(connection, entry_id, "ar", state, YUSUF)

        with pytest.raises(NotInProgress):
            PgReview(executor).confirm_timestamp(entry_id, 0, True, YUSUF)

        assert row_flags(connection, entry_id, 0) == ("scholar_own", False)


@requires_database
def test_integration_nobody_confirms_a_second_on_a_language_someone_else_has_taken() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)
        PgReview(executor).set_role(entry_id, 0, SpanRole.SCHOLAR_OWN, YUSUF)

        with pytest.raises(ClaimedByOther):
            PgReview(executor).confirm_timestamp(entry_id, 0, True, AISHA)

        assert row_flags(connection, entry_id, 0) == ("scholar_own", False)


# ------------------------------------------------------------------ allowed


@requires_database
def test_integration_a_role_is_set_and_logged_with_before_and_after() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)

        PgReview(executor).set_role(entry_id, 1, SpanRole.QUESTIONER, YUSUF)

        assert row_flags(connection, entry_id, 1) == ("questioner", False)
        assert row_flags(connection, entry_id, 0) == ("unclear", False)
        [(entity, entity_id, action, actor, detail)] = revisions(connection)
        assert (entity, entity_id, action, actor) == (
            "segment",
            f"{entry_id}:1",
            "span_role",
            YUSUF,
        )
        assert detail == {"before": "unclear", "after": "questioner", "citable_withdrawn": False}


@requires_database
def test_integration_setting_the_same_role_again_changes_and_logs_nothing() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)
        review = PgReview(executor)
        review.set_role(entry_id, 0, SpanRole.SCHOLAR_OWN, YUSUF)

        review.set_role(entry_id, 0, SpanRole.SCHOLAR_OWN, YUSUF)

        assert len(revisions(connection)) == 1


@requires_database
def test_integration_a_confirmed_second_on_an_attributed_row_makes_it_citable() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)
        review = PgReview(executor)
        review.set_role(entry_id, 0, SpanRole.SCHOLAR_OWN, YUSUF)

        review.confirm_timestamp(entry_id, 0, True, YUSUF)

        assert row_flags(connection, entry_id, 0) == ("scholar_own", True)
        last = revisions(connection)[-1]
        assert (last[0], last[1], last[2], last[3]) == (
            "segment",
            f"{entry_id}:0",
            "citable",
            YUSUF,
        )
        assert last[4] == {"before": False, "after": True}


@requires_database
def test_integration_a_confirmation_can_be_taken_back() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)
        review = PgReview(executor)
        review.set_role(entry_id, 0, SpanRole.SCHOLAR_OWN, YUSUF)
        review.confirm_timestamp(entry_id, 0, True, YUSUF)

        review.confirm_timestamp(entry_id, 0, False, YUSUF)

        assert row_flags(connection, entry_id, 0) == ("scholar_own", False)


@requires_database
def test_integration_changing_who_speaks_withdraws_the_confirmation() -> None:
    # The person confirmed the second for one judgement. A different judgement needs its
    # own confirmation, or "he said it" survives the correction that says he did not.
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)
        review = PgReview(executor)
        review.set_role(entry_id, 0, SpanRole.SCHOLAR_OWN, YUSUF)
        review.confirm_timestamp(entry_id, 0, True, YUSUF)

        review.set_role(entry_id, 0, SpanRole.QUOTED_OTHER, YUSUF)

        assert row_flags(connection, entry_id, 0) == ("quoted_other", False)
        assert revisions(connection)[-1][4] == {
            "before": "scholar_own",
            "after": "quoted_other",
            "citable_withdrawn": True,
        }


@requires_database
def test_integration_the_view_shows_role_and_confirmation_of_every_row() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)
        review = PgReview(executor)
        review.set_role(entry_id, 0, SpanRole.SCHOLAR_OWN, YUSUF)
        review.confirm_timestamp(entry_id, 0, True, YUSUF)

        view = review.view(entry_id)

        assert view is not None
        assert [(r.span_role, r.citable) for r in view.rows] == [
            (SpanRole.SCHOLAR_OWN, True),
            (SpanRole.UNCLEAR, False),
        ]


@requires_database
def test_integration_only_a_confirmed_scholar_row_of_an_approved_public_entry_is_quotable() -> None:
    # The end of the chain: the view the query path reads. Every switch has to be on.
    with migrated_schema() as (connection, executor):
        entry_id = working_entry(executor, connection)
        review = PgReview(executor)
        review.set_role(entry_id, 0, SpanRole.SCHOLAR_OWN, YUSUF)
        review.confirm_timestamp(entry_id, 0, True, YUSUF)
        review.set_role(entry_id, 1, SpanRole.SCHOLAR_OWN, YUSUF)  # attributed, not confirmed
        connection.execute(
            "UPDATE entry SET attribution = 'confirmed', visibility = 'public' WHERE id = %s",
            (entry_id,),
        )
        set_state(connection, entry_id, "ar", "approved")

        quotable = connection.execute(
            "SELECT idx FROM segment_citable WHERE entry_id = %s AND lang = 'ar' ORDER BY idx",
            (entry_id,),
        ).fetchall()

        assert [r[0] for r in quotable] == [0]
        assert Lang.AR.value == "ar"
