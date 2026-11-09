"""The routes for who speaks on a row and for confirming its second (issue #26).

The rules are in `test_db_span_role.py`. Pinned here: sign-in and the CSRF header, that
the actor is always the signed-in admin, that a role outside the five is refused before
the review is asked, and a code of its own for every refusal.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from maqati3.api.admin import AdminConfig
from maqati3.api.app import create_app
from maqati3.domain import SpanRole
from maqati3.review import (
    ClaimedByOther,
    NotInProgress,
    ReviewRow,
    ReviewView,
    RoleNotSet,
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
from test_api_review import ENTRY, VIEW, FakeReview


class RoleReview(FakeReview):
    def set_role(self, entry_id: str, idx: int, role: SpanRole, actor: str) -> None:
        if self.raises:
            raise self.raises
        self.calls.append(("role", entry_id, idx, role, actor))

    def confirm_timestamp(self, entry_id: str, idx: int, confirmed: bool, actor: str) -> None:
        if self.raises:
            raise self.raises
        self.calls.append(("confirm", entry_id, idx, confirmed, actor))


class Setup:
    def __init__(self, *, signed_in: bool = True) -> None:
        self.review = RoleReview()
        config = AdminConfig(
            provider=FakeProvider(),
            admins=FakeAdmins("yusuf@example.org"),
            desk=FakeDesk(),
            public_url=PUBLIC_URL,
            session_secret=SECRET,
            review=self.review,
        )
        app = create_app(FakeRepository(), store=FakeStore(), admin=config)  # type: ignore[arg-type]
        self.client = TestClient(app, base_url="https://testserver")
        if signed_in:
            assert login(self).status_code == 303  # type: ignore[arg-type]


ROLE = f"/api/v1/admin/entries/{ENTRY}/rows/0/role"
SECOND = f"/api/v1/admin/entries/{ENTRY}/rows/0/timestamp"
ROLE_BODY = {"role": "scholar_own"}
SECOND_BODY = {"confirmed": True}


@pytest.mark.parametrize(("path", "body"), [(ROLE, ROLE_BODY), (SECOND, SECOND_BODY)])
def test_nobody_signed_in_changes_a_row(path: str, body: Any) -> None:
    setup = Setup(signed_in=False)

    assert setup.client.put(path, json=body, headers=CSRF).status_code == 401
    assert setup.review.calls == []


@pytest.mark.parametrize(("path", "body"), [(ROLE, ROLE_BODY), (SECOND, SECOND_BODY)])
def test_a_change_without_the_csrf_header_is_refused(path: str, body: Any) -> None:
    setup = Setup()

    assert setup.client.put(path, json=body).status_code == 403
    assert setup.review.calls == []


def test_the_review_says_who_speaks_and_whether_the_second_is_confirmed() -> None:
    setup = Setup()
    setup.review.view = lambda entry_id: ReviewView(  # type: ignore[method-assign]
        entry_id=entry_id,
        rows=[ReviewRow(0, 0, 2400, {}, SpanRole.SCHOLAR_OWN, True), *VIEW.rows[1:]],
        states=VIEW.states,
    )

    rows = setup.client.get(f"/api/v1/admin/entries/{ENTRY}/review").json()["rows"]

    assert (rows[0]["span_role"], rows[0]["citable"]) == ("scholar_own", True)
    assert (rows[1]["span_role"], rows[1]["citable"]) == ("unclear", False)


def test_a_role_is_set_as_the_signed_in_admin() -> None:
    setup = Setup()

    response = setup.client.put(ROLE, json={**ROLE_BODY, "actor": "x@y.z"}, headers=CSRF)

    assert response.status_code == 200
    assert setup.review.calls == [
        ("role", ENTRY, 0, SpanRole.SCHOLAR_OWN, "yusuf@example.org")
    ]


@pytest.mark.parametrize("role", ["scholar", "", "SCHOLAR_OWN", "mufti"])
def test_a_role_outside_the_five_is_refused_before_the_review_is_asked(role: str) -> None:
    setup = Setup()

    response = setup.client.put(ROLE, json={"role": role}, headers=CSRF)

    assert response.status_code == 422
    assert setup.review.calls == []


def test_a_second_is_confirmed_as_the_signed_in_admin() -> None:
    setup = Setup()

    response = setup.client.put(SECOND, json=SECOND_BODY, headers=CSRF)

    assert response.status_code == 200
    assert setup.review.calls == [("confirm", ENTRY, 0, True, "yusuf@example.org")]


@pytest.mark.parametrize("path", [ROLE, SECOND])
@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (UnknownEntry("x"), 404, "unknown_entry"),
        (UnknownRow("x"), 404, "unknown_row"),
        (NotInProgress("x"), 409, "not_in_progress"),
        (ClaimedByOther("x"), 409, "claimed_by_other"),
    ],
)
def test_every_refusal_has_a_code_of_its_own(
    path: str, error: Exception, status: int, code: str
) -> None:
    setup = Setup()
    setup.review.raises = error

    response = setup.client.put(path, json=ROLE_BODY if path == ROLE else SECOND_BODY, headers=CSRF)

    assert (response.status_code, response.json()["detail"]) == (status, code)


def test_a_second_on_a_row_nobody_has_attributed_has_a_code_of_its_own() -> None:
    setup = Setup()
    setup.review.raises = RoleNotSet("x")

    response = setup.client.put(SECOND, json=SECOND_BODY, headers=CSRF)

    assert (response.status_code, response.json()["detail"]) == (409, "role_not_set")
