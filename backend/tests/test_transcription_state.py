"""What the dashboard is told about one entry's transcription.

A pure reading of two facts: the newest transcription job for the entry, and the Arabic
review state. The second one wins whenever there is anything at all, because a
transcript that exists is a transcript that exists -- whether a worker wrote it, a
reviewer typed it, or an import brought it in.
"""

from __future__ import annotations

import pytest

from maqati3.domain import ReviewState
from maqati3.transcription import TranscriptState, transcript_state
from maqati3.translation import translation_state


def test_nothing_asked_for_and_nothing_there() -> None:
    assert transcript_state(ReviewState.NOT_STARTED, None) is TranscriptState.NONE
    assert transcript_state(None, None) is TranscriptState.NONE


@pytest.mark.parametrize(
    ("job", "expected"),
    [
        ("pending", TranscriptState.QUEUED),
        ("running", TranscriptState.RUNNING),
        ("failed", TranscriptState.FAILED),
        ("done", TranscriptState.NONE),
    ],
)
def test_a_job_in_flight_is_what_the_admin_sees(job: str, expected: TranscriptState) -> None:
    # A job marked done while the Arabic is still not_started means its result was
    # dropped (someone else won the race). Nothing is there, so nothing is claimed.
    assert transcript_state(ReviewState.NOT_STARTED, job) is expected


@pytest.mark.parametrize(
    "state",
    [
        ReviewState.DRAFT_READY,
        ReviewState.IN_PROGRESS,
        ReviewState.AWAITING_REVIEW,
        ReviewState.NEEDS_FIXES,
        ReviewState.APPROVED,
    ],
)
def test_a_transcript_that_exists_outranks_whatever_the_job_says(state: ReviewState) -> None:
    # Including a failed job: a later attempt that failed must not make the dashboard
    # offer to overwrite work that is already there.
    assert transcript_state(state, "failed") is TranscriptState.READY
    assert transcript_state(state, None) is TranscriptState.READY


def test_an_unknown_job_state_is_never_read_as_a_transcript() -> None:
    # Fails closed: a state nobody has seen before must not read as "there is one".
    assert transcript_state(ReviewState.NOT_STARTED, "something_new") is TranscriptState.NONE


# ------------------------------------------------------- the drafts in other languages


def test_no_drafts_asked_for_and_none_there() -> None:
    assert translation_state(0, None) is TranscriptState.NONE


@pytest.mark.parametrize(
    ("job", "expected"),
    [
        ("pending", TranscriptState.QUEUED),
        ("running", TranscriptState.RUNNING),
        ("failed", TranscriptState.FAILED),
        ("done", TranscriptState.NONE),
    ],
)
def test_a_draft_job_in_flight_is_what_the_admin_sees(
    job: str, expected: TranscriptState
) -> None:
    assert translation_state(0, job) is expected


def test_one_language_of_two_is_not_done() -> None:
    # English drafted, German not. Offering nothing more would strand the German; the
    # state says there is still something to ask for.
    assert translation_state(1, None) is TranscriptState.NONE
    assert translation_state(1, "failed") is TranscriptState.FAILED


def test_every_language_drafted_is_done_whatever_the_job_says() -> None:
    assert translation_state(2, None) is TranscriptState.READY
    assert translation_state(2, "failed") is TranscriptState.READY
