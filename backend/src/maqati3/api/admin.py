"""The admin dashboard's routes: signing in with Google, and an admin's work on uploads.

Three rules hold everything together (CLAUDE.md, "The Admin Workflow"):

* **Fail closed.** Without a configured login every route here answers 503, never
  anything open. The login is built into the app only when `AdminConfig` is given.
* **The admin list is checked on every request**, not only at sign-in, so removing
  someone locks them out at once. The session says who signed in; the list says whether
  they still may.
* **A forged request is not the dashboard's request.** The session cookie is SameSite=Lax
  and HttpOnly, and every state-changing route also demands a header no other site's form
  can set.
"""

from __future__ import annotations

import hmac
import logging
import mimetypes
import re
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, StringConstraints

from maqati3.api.desk import (
    Admins,
    AdminUser,
    DashboardItem,
    Desk,
    LogRecord,
    NotWaiting,
    ScholarExists,
    UnknownScholar,
)
from maqati3.api.routes import PREVIEW_TYPES, Store
from maqati3.api.schemas import ScholarOut
from maqati3.auth.identity import IdentityError, IdentityProvider
from maqati3.domain import Lang, ReviewState
from maqati3.metadata import (
    AlreadyDrafted,
    EmptyTitle,
    EntryMetadata,
    Metadata,
    MetadataDrafter,
    MetadataError,
)
from maqati3.register.states import InvalidTransition
from maqati3.review import (
    ClaimedByOther,
    EmptyText,
    NotInProgress,
    Review,
    ReviewView,
    UnknownRow,
)
from maqati3.transcription import (
    AlreadyQueued,
    AlreadyTranscribed,
    DailyLimitReached,
    TranscriptState,
    UnknownEntry,
)
from maqati3.translation import AlreadyTranslated, ArabicNotApproved, NothingToTranslate

log = logging.getLogger("maqati3")

SESSION_COOKIE = "maqati3_admin"
SESSION_MAX_AGE_S = 7 * 24 * 3600
#: Long enough that a signed cookie cannot be forged by guessing the key.
MIN_SESSION_SECRET = 32

#: Where an admin lands when no (valid) page was named.
DEFAULT_RETURN = "/en/admin"

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "maqati3"

ADMIN_NOT_CONFIGURED = "admin_not_configured"
ADMIN_LOGIN_REQUIRED = "admin_login_required"
LOGIN_STATE_INVALID = "login_state_invalid"
CSRF_HEADER_MISSING = "csrf_header_missing"
NOT_WAITING = "not_waiting"
UNKNOWN_SCHOLAR = "unknown_scholar"
SCHOLAR_EXISTS = "scholar_exists"
TRANSCRIPTION_NOT_CONFIGURED = "transcription_not_configured"
UNKNOWN_ENTRY = "unknown_entry"
ALREADY_TRANSCRIBED = "already_transcribed"
ALREADY_QUEUED = "already_queued"
DAILY_LIMIT_REACHED = "daily_limit_reached"
TRANSLATION_NOT_CONFIGURED = "translation_not_configured"
NOTHING_TO_TRANSLATE = "nothing_to_translate"
ALREADY_TRANSLATED = "already_translated"
ARABIC_NOT_APPROVED = "arabic_not_approved"
REVIEW_NOT_AVAILABLE = "review_not_available"
UNKNOWN_ROW = "unknown_row"
NOT_IN_PROGRESS = "not_in_progress"
CLAIMED_BY_OTHER = "claimed_by_other"
EMPTY_TEXT = "empty_text"
INVALID_TRANSITION = "invalid_transition"
METADATA_NOT_CONFIGURED = "metadata_not_configured"
ALREADY_DRAFTED = "already_drafted"
METADATA_FAILED = "metadata_failed"
EMPTY_TITLE = "empty_title"

#: A page of ours, as a path. Anything that could leave the site -- a scheme, a second
#: slash, a backslash -- is not accepted, or the login would be an open redirect.
_LOCAL_PATH = re.compile(r"/(?![/\\])[\w\-./?=&%]*")


@dataclass(frozen=True, slots=True)
class AdminConfig:
    provider: IdentityProvider
    admins: Admins
    desk: Desk
    #: The site's own address, e.g. https://archiv.example.org -- what Google redirects
    #: back to, and what decides whether the session cookie is marked Secure.
    public_url: str
    session_secret: str
    #: Whether a speech-to-text provider is configured. False closes the one route that
    #: spends money, the same way a missing Google client closes the whole dashboard.
    transcription: bool = False
    #: Whether a translation model is configured. Same rule, separate key.
    translation: bool = False
    #: The review editor's work. None closes its routes, like a missing key closes the
    #: ones that spend money.
    review: Review | None = None
    #: Where an entry's title, question and keywords live, and the model that drafts
    #: them. Without the model the draft route answers 503; without the store, no metadata.
    metadata: Metadata | None = None
    drafter: MetadataDrafter | None = None

    def __post_init__(self) -> None:
        if len(self.session_secret) < MIN_SESSION_SECRET:
            raise ValueError(
                f"the session secret must be at least {MIN_SESSION_SECRET} characters"
            )

    @property
    def callback_url(self) -> str:
        return self.public_url.rstrip("/") + "/api/v1/admin/auth/callback"

    @property
    def secure_cookie(self) -> bool:
        return self.public_url.startswith("https://")


def safe_return(value: str | None) -> str:
    """The page to land on after signing in: a local path, or the default."""
    if value is not None and _LOCAL_PATH.fullmatch(value):
        return value
    return DEFAULT_RETURN


def with_login_result(destination: str, result: str) -> str:
    return f"{destination}{'&' if '?' in destination else '?'}login={result}"


# ------------------------------------------------------------------ the gates


def admin_config(request: Request) -> AdminConfig:
    config: AdminConfig | None = getattr(request.app.state, "admin", None)
    if config is None:
        raise HTTPException(status_code=503, detail=ADMIN_NOT_CONFIGURED)
    return config


Config = Annotated[AdminConfig, Depends(admin_config)]


def current_admin(request: Request, config: Config) -> AdminUser:
    """The signed-in admin, re-checked against the list on every request."""
    email = request.session.get("admin")
    admin = config.admins.find(email) if isinstance(email, str) else None
    if admin is None:
        raise HTTPException(status_code=401, detail=ADMIN_LOGIN_REQUIRED)
    return admin


def require_csrf_header(request: Request) -> None:
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise HTTPException(status_code=403, detail=CSRF_HEADER_MISSING)


Admin = Annotated[AdminUser, Depends(current_admin)]
#: Order matters: who are you (401) comes before is this really you (403).
Mutating = [Depends(current_admin), Depends(require_csrf_header)]

router = APIRouter(prefix="/api/v1/admin")


# ------------------------------------------------------------------ models


class AdminOut(BaseModel):
    email: str
    name: str | None = None
    #: What this dashboard can offer, so the page does not show a button that 503s.
    transcription: bool = False
    translation: bool = False
    metadata: bool = False


class RegisteredOut(BaseModel):
    entry_id: str
    scholar: ScholarOut


class DashboardItemOut(BaseModel):
    sha256: str
    original_name: str
    duration_ms: int
    received_at: datetime
    contributor: str | None
    kept_despite: list[str]
    status: Literal["waiting", "registered"]
    entry: RegisteredOut | None
    registered_by: str | None
    transcript: TranscriptState = TranscriptState.NONE
    transcript_error: str | None = None
    translations: TranscriptState = TranscriptState.NONE
    translations_error: str | None = None
    arabic_approved: bool = False
    all_approved: bool = False

    @classmethod
    def of(cls, item: DashboardItem) -> DashboardItemOut:
        entry = item.entry
        return cls(
            sha256=item.sha256,
            original_name=item.original_name,
            duration_ms=item.duration_ms,
            received_at=item.received_at,
            contributor=item.contributor,
            kept_despite=item.kept_despite,
            status="waiting" if entry is None else "registered",
            entry=(
                None
                if entry is None
                else RegisteredOut(
                    entry_id=entry.entry_id,
                    scholar=ScholarOut(
                        id=entry.scholar_id,
                        name_ar=entry.scholar_name_ar,
                        name_en=entry.scholar_name_en,
                    ),
                )
            ),
            registered_by=item.registered_by,
            transcript=item.transcript,
            transcript_error=item.transcript_error,
            translations=item.translations,
            translations_error=item.translations_error,
            arabic_approved=item.arabic_approved,
            all_approved=item.all_approved,
        )


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class RegisterIn(BaseModel):
    scholar_id: Text


class RegisterOut(BaseModel):
    entry_id: str


class ScholarIn(BaseModel):
    #: The front of every entry id, and part of URLs: a plain lowercase slug.
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=60)]
    name_ar: Text
    name_en: Text


class RowOut(BaseModel):
    idx: int
    t_start_ms: int
    t_end_ms: int | None
    texts: dict[Lang, str]


class LanguageOut(BaseModel):
    state: ReviewState
    assignee: str | None


class MetadataOut(BaseModel):
    title: str
    question: str
    keywords: list[str]
    state: str

    @classmethod
    def of(cls, metadata: EntryMetadata) -> MetadataOut:
        return cls(
            title=metadata.title,
            question=metadata.question,
            keywords=list(metadata.keywords),
            state=metadata.state.value,
        )


class MetadataIn(BaseModel):
    title: Annotated[str, StringConstraints(max_length=300)]
    question: Annotated[str, StringConstraints(max_length=1000)]
    keywords: Annotated[
        list[Annotated[str, StringConstraints(max_length=80)]], Field(max_length=20)
    ]


class ReviewOut(BaseModel):
    entry_id: str
    rows: list[RowOut]
    languages: dict[Lang, LanguageOut]
    metadata: MetadataOut | None = None

    @classmethod
    def of(cls, view: ReviewView, metadata: EntryMetadata | None = None) -> ReviewOut:
        return cls(
            metadata=None if metadata is None else MetadataOut.of(metadata),
            entry_id=view.entry_id,
            rows=[
                RowOut(idx=r.idx, t_start_ms=r.t_start_ms, t_end_ms=r.t_end_ms, texts=r.texts)
                for r in view.rows
            ],
            languages={
                lang: LanguageOut(state=s.state, assignee=s.assignee)
                for lang, s in view.states.items()
            },
        )


class EditIn(BaseModel):
    #: Only length is bounded here; whether it may be empty is the review's rule.
    text: Annotated[str, StringConstraints(max_length=5000)]


class MoveIn(BaseModel):
    to: ReviewState


class StateOut(BaseModel):
    state: ReviewState


class StatusOut(BaseModel):
    status: str


class LogRecordOut(BaseModel):
    at: datetime
    admin_email: str
    action: str
    subject: str | None
    detail: dict[str, Any]

    @classmethod
    def of(cls, record: LogRecord) -> LogRecordOut:
        return cls(
            at=record.at,
            admin_email=record.admin_email,
            action=record.action,
            subject=record.subject,
            detail=record.detail,
        )


# ------------------------------------------------------------------ signing in


@router.get("/auth/login")
def login(
    request: Request, config: Config, return_to: Annotated[str | None, Query(alias="return")] = None
) -> RedirectResponse:
    """Send the browser to Google, remembering what to check when it comes back."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    request.session["oauth"] = {"state": state, "nonce": nonce, "return": safe_return(return_to)}
    url = config.provider.authorization_url(
        redirect_uri=config.callback_url, state=state, nonce=nonce
    )
    return RedirectResponse(url, status_code=303)


@router.get("/auth/callback")
def callback(
    request: Request,
    config: Config,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    # Single use: popped whether or not it matches, so a callback cannot be replayed.
    started = request.session.pop("oauth", None)
    if (
        not isinstance(started, dict)
        or not state
        or not hmac.compare_digest(str(started.get("state", "")).encode(), state.encode())
    ):
        raise HTTPException(status_code=400, detail=LOGIN_STATE_INVALID)
    destination = safe_return(started.get("return"))

    if error or not code:
        return RedirectResponse(with_login_result(destination, "failed"), status_code=303)
    try:
        identity = config.provider.identify(
            code=code, redirect_uri=config.callback_url, nonce=str(started.get("nonce", ""))
        )
    except IdentityError as exc:
        log.warning("admin sign-in refused: %s", exc)
        return RedirectResponse(with_login_result(destination, "failed"), status_code=303)

    admin = config.admins.find(identity.email)
    if admin is None:
        config.admins.log(identity.email, "login_denied", None, {})
        return RedirectResponse(with_login_result(destination, "denied"), status_code=303)

    request.session.clear()
    request.session["admin"] = admin.email
    config.admins.log(admin.email, "login", None, {})
    return RedirectResponse(destination, status_code=303)


@router.post("/auth/logout", dependencies=Mutating)
def logout(request: Request) -> StatusOut:
    request.session.clear()
    return StatusOut(status="signed_out")


@router.get("/me")
def me(admin: Admin, config: Config) -> AdminOut:
    return AdminOut(
        email=admin.email,
        name=admin.name,
        transcription=config.transcription,
        translation=config.translation,
        metadata=config.metadata is not None and config.drafter is not None,
    )


# ------------------------------------------------------------------ the dashboard


@router.get("/submissions")
def submissions(config: Config, admin: Admin) -> list[DashboardItemOut]:
    return [DashboardItemOut.of(item) for item in config.desk.items()]


@router.get("/submissions/{sha256}/media")
def media(sha256: str, config: Config, admin: Admin, store: Store) -> FileResponse:
    """An upload's file, for the admin deciding whether it is worth the review time.

    FileResponse answers byte ranges, which is what lets a browser seek in a video. The
    path comes back out of the database; the store decides whether it is a staged file.
    """
    recorded = config.desk.media_path(sha256)
    path = store.locate(recorded) if recorded is not None else None
    if path is None:
        raise HTTPException(status_code=404, detail="media_not_found")
    media_type = PREVIEW_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0]
    return FileResponse(path, media_type=media_type or "application/octet-stream")


@router.post("/submissions/{sha256}/register", dependencies=Mutating)
def register(sha256: str, body: RegisterIn, config: Config, admin: Admin) -> RegisterOut:
    try:
        entry_id = config.desk.register(sha256, body.scholar_id, admin.email)
    except NotWaiting as exc:
        raise HTTPException(status_code=409, detail=NOT_WAITING) from exc
    except UnknownScholar as exc:
        raise HTTPException(status_code=422, detail=UNKNOWN_SCHOLAR) from exc
    return RegisterOut(entry_id=entry_id)


@router.post("/submissions/{sha256}/discard", dependencies=Mutating)
def discard(sha256: str, config: Config, admin: Admin, store: Store) -> StatusOut:
    try:
        path = config.desk.discard(sha256, admin.email)
    except NotWaiting as exc:
        raise HTTPException(status_code=409, detail=NOT_WAITING) from exc
    try:
        store.discard(path)
    except ValueError:
        # The row is gone, and a path outside staging must never be deleted. Say so.
        log.warning("discarded upload pointed outside staging: %s", path)
    return StatusOut(status="discarded")


class TranscriptionOut(BaseModel):
    job_id: int


@router.post("/entries/{entry_id}/transcribe", status_code=202, dependencies=Mutating)
def transcribe(entry_id: str, config: Config, admin: Admin) -> TranscriptionOut:
    """Queue the Arabic transcription of one entry.

    202, not 200: nothing has been transcribed when this returns. A worker picks the
    job up, and the draft appears for review minutes later.
    """
    if not config.transcription:
        raise HTTPException(status_code=503, detail=TRANSCRIPTION_NOT_CONFIGURED)
    try:
        job_id = config.desk.request_transcription(entry_id, admin.email)
    except UnknownEntry as exc:
        raise HTTPException(status_code=404, detail=UNKNOWN_ENTRY) from exc
    except AlreadyTranscribed as exc:
        raise HTTPException(status_code=409, detail=ALREADY_TRANSCRIBED) from exc
    except AlreadyQueued as exc:
        raise HTTPException(status_code=409, detail=ALREADY_QUEUED) from exc
    except DailyLimitReached as exc:
        # 429, like the upload key limit: the answer is "not now", not "never".
        log.warning("transcription refused, daily budget spent: %s", exc)
        raise HTTPException(status_code=429, detail=DAILY_LIMIT_REACHED) from exc
    return TranscriptionOut(job_id=job_id)


class DraftsOut(BaseModel):
    job_ids: list[int]


@router.post("/entries/{entry_id}/translate", status_code=202, dependencies=Mutating)
def translate(entry_id: str, config: Config, admin: Admin) -> DraftsOut:
    """Queue a draft translation of every language still untouched.

    One job per language, so a German failure does not redo the English. 202 for the
    same reason as transcription: nothing is translated when this returns.
    """
    if not config.translation:
        raise HTTPException(status_code=503, detail=TRANSLATION_NOT_CONFIGURED)
    try:
        job_ids = config.desk.request_translation(entry_id, admin.email)
    except UnknownEntry as exc:
        raise HTTPException(status_code=404, detail=UNKNOWN_ENTRY) from exc
    except NothingToTranslate as exc:
        raise HTTPException(status_code=409, detail=NOTHING_TO_TRANSLATE) from exc
    except ArabicNotApproved as exc:
        raise HTTPException(status_code=409, detail=ARABIC_NOT_APPROVED) from exc
    except AlreadyTranslated as exc:
        raise HTTPException(status_code=409, detail=ALREADY_TRANSLATED) from exc
    except AlreadyQueued as exc:
        raise HTTPException(status_code=409, detail=ALREADY_QUEUED) from exc
    except DailyLimitReached as exc:
        log.warning("drafts refused, daily budget spent: %s", exc)
        raise HTTPException(status_code=429, detail=DAILY_LIMIT_REACHED) from exc
    return DraftsOut(job_ids=job_ids)


# ------------------------------------------------------------------ the review editor


def reviewer(config: Config) -> Review:
    if config.review is None:
        raise HTTPException(status_code=503, detail=REVIEW_NOT_AVAILABLE)
    return config.review


Reviewing = Annotated[Review, Depends(reviewer)]


@router.get("/entries/{entry_id}/review")
def review_entry(
    entry_id: str, review: Reviewing, config: Config, admin: Admin
) -> ReviewOut:
    """Every row of an entry with its text in each language, and where each language stands."""
    view = review.view(entry_id)
    if view is None:
        raise HTTPException(status_code=404, detail=UNKNOWN_ENTRY)
    metadata = config.metadata.get(entry_id) if config.metadata is not None else None
    return ReviewOut.of(view, metadata)


@router.put("/entries/{entry_id}/rows/{idx}/{lang}", dependencies=Mutating)
def edit_row(
    entry_id: str, idx: int, lang: Lang, body: EditIn, review: Reviewing, admin: Admin
) -> StatusOut:
    """Replace one row's text. The editor is always the signed-in admin, never a name sent."""
    try:
        review.edit_text(entry_id, idx, lang, body.text, admin.email)
    except UnknownEntry as exc:
        raise HTTPException(status_code=404, detail=UNKNOWN_ENTRY) from exc
    except UnknownRow as exc:
        raise HTTPException(status_code=404, detail=UNKNOWN_ROW) from exc
    except NotInProgress as exc:
        raise HTTPException(status_code=409, detail=NOT_IN_PROGRESS) from exc
    except ClaimedByOther as exc:
        raise HTTPException(status_code=409, detail=CLAIMED_BY_OTHER) from exc
    except EmptyText as exc:
        raise HTTPException(status_code=422, detail=EMPTY_TEXT) from exc
    return StatusOut(status="saved")


@router.post("/entries/{entry_id}/languages/{lang}/state", dependencies=Mutating)
def move_language(
    entry_id: str, lang: Lang, body: MoveIn, review: Reviewing, admin: Admin
) -> StateOut:
    """Take a language, hand it on, approve it or send it back: one step of the machine."""
    try:
        new = review.move(entry_id, lang, body.to, admin.email)
    except UnknownEntry as exc:
        raise HTTPException(status_code=404, detail=UNKNOWN_ENTRY) from exc
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=INVALID_TRANSITION) from exc
    except ClaimedByOther as exc:
        raise HTTPException(status_code=409, detail=CLAIMED_BY_OTHER) from exc
    except ArabicNotApproved as exc:
        raise HTTPException(status_code=409, detail=ARABIC_NOT_APPROVED) from exc
    return StateOut(state=new)


@router.post("/entries/{entry_id}/metadata/draft", dependencies=Mutating)
def draft_metadata(entry_id: str, config: Config, admin: Admin) -> StatusOut:
    """Ask the model for a title, question and keywords, from the approved Arabic only.

    The model is asked only after every gate has said yes: no gate passed, no money spent.
    """
    if config.metadata is None or config.drafter is None:
        raise HTTPException(status_code=503, detail=METADATA_NOT_CONFIGURED)
    try:
        lines = config.metadata.lines_to_draft_from(entry_id)
        draft = config.drafter.draft(lines)
        config.metadata.store_draft(entry_id, draft, admin.email)
    except UnknownEntry as exc:
        raise HTTPException(status_code=404, detail=UNKNOWN_ENTRY) from exc
    except ArabicNotApproved as exc:
        raise HTTPException(status_code=409, detail=ARABIC_NOT_APPROVED) from exc
    except AlreadyDrafted as exc:
        raise HTTPException(status_code=409, detail=ALREADY_DRAFTED) from exc
    except MetadataError as exc:
        log.warning("metadata draft failed: %s", exc)
        raise HTTPException(status_code=502, detail=METADATA_FAILED) from exc
    return StatusOut(status="drafted")


@router.put("/entries/{entry_id}/metadata", dependencies=Mutating)
def save_metadata(entry_id: str, body: MetadataIn, config: Config, admin: Admin) -> StatusOut:
    """A person's own words for the title, question and keywords."""
    if config.metadata is None:
        raise HTTPException(status_code=503, detail=METADATA_NOT_CONFIGURED)
    try:
        config.metadata.save(
            entry_id, body.title, body.question, tuple(body.keywords), admin.email
        )
    except UnknownEntry as exc:
        raise HTTPException(status_code=404, detail=UNKNOWN_ENTRY) from exc
    except EmptyTitle as exc:
        raise HTTPException(status_code=422, detail=EMPTY_TITLE) from exc
    return StatusOut(status="saved")


@router.post("/scholars", dependencies=Mutating)
def add_scholar(body: ScholarIn, config: Config, admin: Admin) -> ScholarOut:
    try:
        config.desk.add_scholar(body.id, body.name_ar, body.name_en, admin.email)
    except ScholarExists as exc:
        raise HTTPException(status_code=409, detail=SCHOLAR_EXISTS) from exc
    return ScholarOut(id=body.id, name_ar=body.name_ar, name_en=body.name_en)


@router.get("/log")
def log_entries(
    config: Config,
    admin: Admin,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[LogRecordOut]:
    """Latest actions on the admin dashboard."""
    return [LogRecordOut.of(record) for record in config.admins.recent_log(limit=limit)]


__all__ = ["AdminConfig", "router", "safe_return"]
