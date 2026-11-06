"""An entry's descriptive metadata: title, question, keywords.

A model drafts them from the *approved* Arabic, a person corrects and confirms them.
The rules are properties of the database: no draft before the Arabic is approved, no
second draft over a person's text, and every change leaves a row in `revision_log`.
Blocked cases first.
"""

from __future__ import annotations

from typing import Any

import pytest

from maqati3.db.metadata import PgMetadata
from maqati3.metadata import (
    AlreadyDrafted,
    ArabicNotApproved,
    EmptyTitle,
    MetadataDraft,
    MetadataState,
)
from maqati3.transcription import UnknownEntry
from test_db_review import (
    YUSUF,
    migrated_schema,
    requires_database,
    revisions,
    set_state,
    transcribed_entry,
)

DRAFT = MetadataDraft(
    title="On what is forbidden and on kindness to one's mother",
    question="How should a sister treat her mother?",
    keywords=("family", "kindness", "mother"),
)


def approved_entry(executor: Any, connection: Any) -> str:
    entry_id = transcribed_entry(executor)
    set_state(connection, entry_id, "ar", "approved")
    return entry_id


# ------------------------------------------------------------------ drafting: blocked


@requires_database
def test_integration_a_draft_is_asked_for_an_entry_that_is_not_there() -> None:
    with migrated_schema() as (_, executor), pytest.raises(UnknownEntry):
        PgMetadata(executor).lines_to_draft_from("nobody-000001")


@requires_database
@pytest.mark.parametrize("state", ["draft_ready", "in_progress", "awaiting_review", "needs_fixes"])
def test_integration_metadata_wait_for_the_approved_arabic(state: str) -> None:
    # A title made from a transcript nobody has checked would be a wrong title.
    with migrated_schema() as (connection, executor):
        entry_id = transcribed_entry(executor)
        set_state(connection, entry_id, "ar", state, YUSUF)

        with pytest.raises(ArabicNotApproved):
            PgMetadata(executor).lines_to_draft_from(entry_id)


@requires_database
def test_integration_a_second_draft_never_replaces_the_first() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = approved_entry(executor, connection)
        metadata = PgMetadata(executor)
        metadata.store_draft(entry_id, DRAFT, YUSUF)

        with pytest.raises(AlreadyDrafted):
            metadata.lines_to_draft_from(entry_id)
        with pytest.raises(AlreadyDrafted):
            metadata.store_draft(entry_id, DRAFT, YUSUF)


@requires_database
def test_integration_a_late_draft_does_not_overwrite_what_a_person_wrote() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = approved_entry(executor, connection)
        metadata = PgMetadata(executor)
        metadata.save(entry_id, "My title", "My question?", ("mine",), YUSUF)

        with pytest.raises(AlreadyDrafted):
            metadata.store_draft(entry_id, DRAFT, YUSUF)

        assert metadata.get(entry_id).title == "My title"  # type: ignore[union-attr]


@requires_database
@pytest.mark.parametrize("title", ["", "   "])
def test_integration_a_title_is_never_empty(title: str) -> None:
    with migrated_schema() as (connection, executor):
        entry_id = approved_entry(executor, connection)

        with pytest.raises(EmptyTitle):
            PgMetadata(executor).save(entry_id, title, "q", (), YUSUF)

        assert revisions(connection) == []


# ------------------------------------------------------------------ drafting: allowed


@requires_database
def test_integration_the_draft_lines_are_the_arabic_in_row_order() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = approved_entry(executor, connection)

        assert PgMetadata(executor).lines_to_draft_from(entry_id) == (
            "ما حكم هذا؟",
            "هذا جائز.",
        )


@requires_database
def test_integration_a_draft_is_stored_as_a_draft_and_logged() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = approved_entry(executor, connection)
        metadata = PgMetadata(executor)

        metadata.store_draft(entry_id, DRAFT, YUSUF)

        stored = metadata.get(entry_id)
        assert stored is not None
        assert stored.state is MetadataState.DRAFT
        assert (stored.title, stored.question, stored.keywords) == (
            DRAFT.title,
            DRAFT.question,
            DRAFT.keywords,
        )
        [(entity, entity_id, action, actor, _)] = revisions(connection)
        assert (entity, entity_id, action, actor) == ("entry", entry_id, "metadata_draft", YUSUF)


@requires_database
def test_integration_a_person_confirms_by_saving_and_the_change_is_logged() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = approved_entry(executor, connection)
        metadata = PgMetadata(executor)
        metadata.store_draft(entry_id, DRAFT, YUSUF)

        metadata.save(entry_id, "  A better title ", DRAFT.question, DRAFT.keywords, YUSUF)

        stored = metadata.get(entry_id)
        assert stored is not None
        assert (stored.title, stored.state) == ("A better title", MetadataState.CONFIRMED)
        last = revisions(connection)[-1]
        assert last[2] == "metadata_edit"
        assert last[4]["before"]["title"] == DRAFT.title
        assert last[4]["after"]["title"] == "A better title"


@requires_database
def test_integration_keywords_are_tidied_not_trusted() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = approved_entry(executor, connection)
        metadata = PgMetadata(executor)

        metadata.save(entry_id, "T", "", (" Family ", "family", "", "KINDNESS"), YUSUF)

        assert metadata.get(entry_id).keywords == ("family", "kindness")  # type: ignore[union-attr]


@requires_database
def test_integration_an_entry_without_metadata_reads_as_none() -> None:
    with migrated_schema() as (connection, executor):
        entry_id = approved_entry(executor, connection)

        stored = PgMetadata(executor).get(entry_id)

        assert stored is not None
        assert stored.state is MetadataState.NONE
        assert stored.keywords == ()


@requires_database
def test_integration_saving_on_an_unknown_entry_is_refused() -> None:
    with migrated_schema() as (_, executor), pytest.raises(UnknownEntry):
        PgMetadata(executor).save("nobody-000001", "T", "", (), YUSUF)
