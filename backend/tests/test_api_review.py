"""The review editor's routes: reading an entry's rows, editing one, moving a language.

The rules themselves are in `test_db_review.py`, against Postgres. What is pinned here is
what the routes add: only a signed-in admin gets in, a change needs the CSRF header, the
acting person is always the signed-in one (never a name taken from the request), and every
refusal is a specific code the page can turn into words.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from maqati3.api.admin import AdminConfig
from maqati3.api.app import create_app
from maqati3.domain import Lang, ReviewState
from maqati3.register.states import InvalidTransition
from maqati3.review import (
    ArabicNotApproved,
    ClaimedByOther,
    EmptyText,
    LanguageState,
    NotInProgress,
    ReviewRow,
    ReviewView,
    UnknownRow,
)
from maqati3.transcription import UnknownEntry
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

ENTRY = "ibn-baz-000001"
VIEW = ReviewView(
    entry_id=ENTRY,
    rows=[
        ReviewRow(0, 0, 2400, {Lang.AR: "ما حكم هذا؟", Lang.EN: "What is the ruling?"}),
        ReviewRow(1, 2500, 6000, {Lang.AR: "هذا جائز.", Lang.EN: "This is permitted."}),
    ],
    states={
        Lang.AR: LanguageState(ReviewState.IN_PROGRESS, "yusuf@example.org"),
        Lang.EN: LanguageState(ReviewState.DRAFT_READY),
    },
)


class FakeReview:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.raises: Exception | None = None

    def view(self, entry_id: str) -> ReviewView | None:
        return VIEW if entry_id == ENTRY else None

    def edit_text(self, entry_id: str, idx: int, lang: Lang, text: str, actor: str) -> None:
        if self.raises:
            raise self.raises
        self.calls.append(("edit", entry_id, idx, lang, text, actor))

    def move(self, entry_id: str, lang: Lang, to: ReviewState, actor: str) -> ReviewState:
        if self.raises:
            raise self.raises
        self.calls.append(("move", entry_id, lang, to, actor))
        return to


class Editor:
    def __init__(self, *, with_review: bool = True, signed_in: bool = True) -> None:
        self.review = FakeReview()
        config = AdminConfig(
            provider=FakeProvider(),
            admins=FakeAdmins("yusuf@example.org"),
            desk=FakeDesk(),
            public_url=PUBLIC_URL,
            session_secret=SECRET,
            review=self.review if with_review else None,
        )
        app = create_app(FakeRepository(), store=FakeStore(), admin=config)  # type: ignore[arg-type]
        self.client = TestClient(app, base_url="https://testserver")
        if signed_in:
            assert login(self).status_code == 303  # type: ignore[arg-type]


EDIT = f"/api/v1/admin/entries/{ENTRY}/rows/0/ar"
MOVE = f"/api/v1/admin/entries/{ENTRY}/languages/ar/state"


# ------------------------------------------------------------------ closed


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", f"/api/v1/admin/entries/{ENTRY}/review", None),
        ("put", EDIT, {"text": "x"}),
        ("post", MOVE, {"to": "in_progress"}),
    ],
)
def test_nobody_signed_in_reaches_the_editor(method: str, path: str, body: Any) -> None:
    editor = Editor(signed_in=False)

    response = getattr(editor.client, method)(
        path, headers=CSRF, **({"json": body} if body else {})
    )

    assert response.status_code == 401
    assert editor.review.calls == []


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [("put", EDIT, {"text": "x"}), ("post", MOVE, {"to": "in_progress"})],
)
def test_a_change_without_the_csrf_header_is_refused(method: str, path: str, body: Any) -> None:
    editor = Editor()

    response = getattr(editor.client, method)(path, json=body)

    assert response.status_code == 403
    assert editor.review.calls == []


def test_without_a_review_behind_it_the_editor_answers_503() -> None:
    editor = Editor(with_review=False)

    response = editor.client.get(f"/api/v1/admin/entries/{ENTRY}/review")

    assert response.status_code == 503


# ------------------------------------------------------------------ reading


def test_the_editor_reads_rows_and_the_state_of_every_language() -> None:
    editor = Editor()

    response = editor.client.get(f"/api/v1/admin/entries/{ENTRY}/review")

    assert response.status_code == 200
    body = response.json()
    assert body["entry_id"] == ENTRY
    assert body["rows"][1] == {
        "idx": 1,
        "t_start_ms": 2500,
        "t_end_ms": 6000,
        "texts": {"ar": "هذا جائز.", "en": "This is permitted."},
    }
    assert body["languages"]["ar"] == {"state": "in_progress", "assignee": "yusuf@example.org"}
    assert body["languages"]["en"] == {"state": "draft_ready", "assignee": None}


def test_an_unknown_entry_is_404() -> None:
    editor = Editor()

    response = editor.client.get("/api/v1/admin/entries/nobody-000001/review")

    assert (response.status_code, response.json()["detail"]) == (404, "unknown_entry")


# ------------------------------------------------------------------ changing


def test_an_edit_is_made_as_the_signed_in_admin() -> None:
    editor = Editor()

    response = editor.client.put(EDIT, json={"text": "ما حكم هذا الفعل؟"}, headers=CSRF)

    assert response.status_code == 200
    assert editor.review.calls == [
        ("edit", ENTRY, 0, Lang.AR, "ما حكم هذا الفعل؟", "yusuf@example.org")
    ]


def test_the_actor_cannot_be_named_in_the_request() -> None:
    editor = Editor()

    editor.client.put(EDIT, json={"text": "x", "actor": "someone@else.org"}, headers=CSRF)

    assert editor.review.calls[0][-1] == "yusuf@example.org"


def test_a_language_that_does_not_exist_is_refused_before_the_review_is_asked() -> None:
    editor = Editor()

    response = editor.client.put(
        f"/api/v1/admin/entries/{ENTRY}/rows/0/fr", json={"text": "x"}, headers=CSRF
    )

    assert response.status_code == 422
    assert editor.review.calls == []


def test_a_move_is_made_as_the_signed_in_admin_and_answers_the_new_state() -> None:
    editor = Editor()

    response = editor.client.post(MOVE, json={"to": "awaiting_review"}, headers=CSRF)

    assert response.status_code == 200
    assert response.json() == {"state": "awaiting_review"}
    assert editor.review.calls == [
        ("move", ENTRY, Lang.AR, ReviewState.AWAITING_REVIEW, "yusuf@example.org")
    ]


def test_a_state_that_does_not_exist_is_refused() -> None:
    editor = Editor()

    response = editor.client.post(MOVE, json={"to": "published"}, headers=CSRF)

    assert response.status_code == 422
    assert editor.review.calls == []


REFUSALS = {
    "unknown_entry": (UnknownEntry("x"), 404),
    "unknown_row": (UnknownRow("x"), 404),
    "not_in_progress": (NotInProgress("x"), 409),
    "claimed_by_other": (ClaimedByOther("x"), 409),
    "empty_text": (EmptyText("x"), 422),
    "invalid_transition": (InvalidTransition("x"), 409),
    "arabic_not_approved": (ArabicNotApproved("x"), 409),
}


@pytest.mark.parametrize(
    "code",
    ["unknown_entry", "unknown_row", "not_in_progress", "claimed_by_other", "empty_text"],
)
def test_every_refusal_of_an_edit_has_a_code_of_its_own(code: str) -> None:
    error, status = REFUSALS[code]
    editor = Editor()
    editor.review.raises = error

    response = editor.client.put(EDIT, json={"text": "x"}, headers=CSRF)

    assert (response.status_code, response.json()["detail"]) == (status, code)


@pytest.mark.parametrize(
    "code", ["unknown_entry", "claimed_by_other", "invalid_transition", "arabic_not_approved"]
)
def test_every_refusal_of_a_move_has_a_code_of_its_own(code: str) -> None:
    error, status = REFUSALS[code]
    editor = Editor()
    editor.review.raises = error

    response = editor.client.post(MOVE, json={"to": "in_progress"}, headers=CSRF)

    assert (response.status_code, response.json()["detail"]) == (status, code)
