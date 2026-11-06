"""The metadata routes: draft one from the approved Arabic, correct and confirm it.

The rules are in `test_db_metadata.py`. Pinned here: the gates of the dashboard (signed in,
CSRF header, 503 without a model), that the actor is always the signed-in admin, and that
every refusal has a code of its own.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_api_admin import (
    CSRF,
    PUBLIC_URL,
    SECRET,
    FakeAdmins,
    FakeDesk,
    FakeProvider,
    FakeRepository,
    FakeStore,
    login,
)
from test_api_review import ENTRY, FakeReview

from maqati3.api.admin import AdminConfig
from maqati3.api.app import create_app
from maqati3.metadata import (
    AlreadyDrafted,
    ArabicNotApproved,
    EmptyTitle,
    EntryMetadata,
    MetadataDraft,
    MetadataError,
    MetadataState,
)
from maqati3.transcription import UnknownEntry

DRAFT = MetadataDraft("A title", "A question?", ("family", "mother"))


class FakeMetadata:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.raises: Exception | None = None

    def get(self, entry_id: str) -> EntryMetadata | None:
        return (
            EntryMetadata("A title", "A question?", ("family",), MetadataState.DRAFT)
            if entry_id == ENTRY
            else None
        )

    def lines_to_draft_from(self, entry_id: str) -> tuple[str, ...]:
        if self.raises:
            raise self.raises
        return ("سطر",)

    def store_draft(self, entry_id: str, draft: MetadataDraft, actor: str) -> None:
        self.calls.append(("store", entry_id, draft, actor))

    def save(
        self, entry_id: str, title: str, question: str, keywords: tuple[str, ...], actor: str
    ) -> None:
        if self.raises:
            raise self.raises
        self.calls.append(("save", entry_id, title, question, keywords, actor))


class FakeDrafter:
    def __init__(self) -> None:
        self.failing = False
        self.seen: list[tuple[str, ...]] = []

    def draft(self, lines: tuple[str, ...]) -> MetadataDraft:
        self.seen.append(lines)
        if self.failing:
            raise MetadataError("down")
        return DRAFT


class Setup:
    def __init__(self, *, drafter: bool = True, signed_in: bool = True) -> None:
        self.metadata = FakeMetadata()
        self.drafter = FakeDrafter()
        config = AdminConfig(
            provider=FakeProvider(),
            admins=FakeAdmins("yusuf@example.org"),
            desk=FakeDesk(),
            public_url=PUBLIC_URL,
            session_secret=SECRET,
            review=FakeReview(),
            metadata=self.metadata,
            drafter=self.drafter if drafter else None,
        )
        app = create_app(FakeRepository(), store=FakeStore(), admin=config)  # type: ignore[arg-type]
        self.client = TestClient(app, base_url="https://testserver")
        if signed_in:
            assert login(self).status_code == 303  # type: ignore[arg-type]


DRAFT_URL = f"/api/v1/admin/entries/{ENTRY}/metadata/draft"
SAVE_URL = f"/api/v1/admin/entries/{ENTRY}/metadata"
BODY = {"title": "T", "question": "Q?", "keywords": ["a", "b"]}


@pytest.mark.parametrize(("method", "path"), [("post", DRAFT_URL), ("put", SAVE_URL)])
def test_nobody_signed_in_reaches_the_metadata(method: str, path: str) -> None:
    setup = Setup(signed_in=False)

    response = getattr(setup.client, method)(path, headers=CSRF, json=BODY)

    assert response.status_code == 401
    assert setup.metadata.calls == []


@pytest.mark.parametrize(("method", "path"), [("post", DRAFT_URL), ("put", SAVE_URL)])
def test_a_change_without_the_csrf_header_is_refused(method: str, path: str) -> None:
    setup = Setup()

    assert getattr(setup.client, method)(path, json=BODY).status_code == 403
    assert setup.metadata.calls == []


def test_without_a_model_no_draft_is_made_and_nothing_is_spent() -> None:
    setup = Setup(drafter=False)

    response = setup.client.post(DRAFT_URL, headers=CSRF)

    assert (response.status_code, response.json()["detail"]) == (503, "metadata_not_configured")


def test_the_review_says_what_the_metadata_are() -> None:
    setup = Setup()

    body = setup.client.get(f"/api/v1/admin/entries/{ENTRY}/review").json()

    assert body["metadata"] == {
        "title": "A title",
        "question": "A question?",
        "keywords": ["family"],
        "state": "draft",
    }


def test_the_dashboard_says_whether_a_model_is_there() -> None:
    assert Setup().client.get("/api/v1/admin/me").json()["metadata"] is True
    assert Setup(drafter=False).client.get("/api/v1/admin/me").json()["metadata"] is False


def test_a_draft_is_made_from_the_approved_arabic_and_stored_as_the_admin() -> None:
    setup = Setup()

    response = setup.client.post(DRAFT_URL, headers=CSRF)

    assert response.status_code == 200
    assert setup.drafter.seen == [("سطر",)]
    assert setup.metadata.calls == [("store", ENTRY, DRAFT, "yusuf@example.org")]


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (UnknownEntry("x"), 404, "unknown_entry"),
        (ArabicNotApproved("x"), 409, "arabic_not_approved"),
        (AlreadyDrafted("x"), 409, "already_drafted"),
    ],
)
def test_a_refused_draft_never_asks_the_model(error: Exception, status: int, code: str) -> None:
    setup = Setup()
    setup.metadata.raises = error

    response = setup.client.post(DRAFT_URL, headers=CSRF)

    assert (response.status_code, response.json()["detail"]) == (status, code)
    assert setup.drafter.seen == []


def test_a_model_that_fails_stores_nothing() -> None:
    setup = Setup()
    setup.drafter.failing = True

    response = setup.client.post(DRAFT_URL, headers=CSRF)

    assert (response.status_code, response.json()["detail"]) == (502, "metadata_failed")
    assert setup.metadata.calls == []


def test_a_person_saves_their_words_as_themselves() -> None:
    setup = Setup()

    response = setup.client.put(SAVE_URL, json={**BODY, "actor": "x@y.z"}, headers=CSRF)

    assert response.status_code == 200
    assert setup.metadata.calls == [("save", ENTRY, "T", "Q?", ("a", "b"), "yusuf@example.org")]


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [(UnknownEntry("x"), 404, "unknown_entry"), (EmptyTitle("x"), 422, "empty_title")],
)
def test_a_refused_save_has_a_code_of_its_own(error: Exception, status: int, code: str) -> None:
    setup = Setup()
    setup.metadata.raises = error

    response = setup.client.put(SAVE_URL, json=BODY, headers=CSRF)

    assert (response.status_code, response.json()["detail"]) == (status, code)
