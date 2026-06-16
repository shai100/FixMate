"""Pydantic models that define the API's request and response shapes.

These classes are the *contract* between the backend and any client (the React
web app, tests, future integrations). FastAPI uses them two ways:

  - As a request body type, it parses + validates incoming JSON into the model,
    rejecting malformed input with a 422 before your handler runs.
  - As a response type, it serializes your return value to JSON in exactly this
    shape, so the client always knows what fields to expect.

By convention a ``*Request`` / ``Create*`` / ``Update*`` model is what comes in,
and a ``*Out`` model is what goes back. The frontend mirrors these shapes in
``web/src/types.ts`` — keep the two in step. Because every field is typed, the
models double as living documentation of the wire format.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateConversation(BaseModel):
    """Body for starting a conversation; optionally pins it to a piece of equipment."""

    equipment_id: uuid.UUID | None = None


class MessageOut(BaseModel):
    """One turn returned to the client. ``answer_log_id`` is set on assistant turns
    and links back to the full audit record."""

    id: uuid.UUID
    role: str
    content: str
    answer_log_id: uuid.UUID | None
    created_at: datetime


class ConversationOut(BaseModel):
    """A conversation with its ordered list of messages."""

    id: uuid.UUID
    equipment_id: uuid.UUID | None
    created_at: datetime
    messages: list[MessageOut] = []


class AskRequest(BaseModel):
    """Body for the main Q&A endpoint: the technician's question text."""

    question: str


class CitationOut(BaseModel):
    """A source backing an answer. ``source_type`` ("manual" / "field_fix") lets the
    UI badge field-verified fixes distinctly from manual content."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID | None
    document_title: str | None
    page: int | None
    source_type: str


class FigureOut(BaseModel):
    """A diagram shown alongside an answer. ``url`` is a short-lived signed link to
    the image in object storage."""

    page: int
    caption: str | None
    url: str


class AnswerOut(BaseModel):
    """The full result of asking a question.

    ``escalated`` is True when confidence was too low to answer safely, in which
    case the UI shows the escalation card instead of a normal answer. ``citations``
    and ``figures`` are the grounding the answer is built from.
    """

    message_id: uuid.UUID
    answer_log_id: uuid.UUID
    text: str
    confidence: str
    escalated: bool
    citations: list[CitationOut]
    figures: list[FigureOut]


class FeedbackRequest(BaseModel):
    """A "did it help?" submission. On "not helped", the optional ``fix_text`` /
    ``photos`` let the technician propose a candidate fix in the same call."""

    helped: bool
    fix_text: str | None = None
    photos: list[str] | None = None


class FeedbackOut(BaseModel):
    """Result of recording feedback; ``fix_id`` is set if a candidate fix was opened."""

    feedback_id: uuid.UUID
    helped: bool
    fix_id: uuid.UUID | None = None


class CreateEquipment(BaseModel):
    """Body for registering a new piece of equipment."""

    name: str
    manufacturer: str | None = None
    model: str | None = None


class EquipmentOut(BaseModel):
    """An equipment profile as returned to clients."""

    id: uuid.UUID
    name: str
    manufacturer: str | None
    model: str | None
    created_at: datetime


class UpdateEquipment(BaseModel):
    """Partial update for equipment; only the provided fields change."""

    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None


class UpdateDocument(BaseModel):
    """Partial update for a manual (currently just its display title)."""

    title: str | None = None


class ManualChunkOut(BaseModel):
    """A manual excerpt shown to a curator as evidence while reviewing a fix.
    ``score`` is the retrieval relevance of this excerpt to the fix's question."""

    chunk_id: str
    page: int | None
    text: str
    score: float


class ReviewItemOut(BaseModel):
    """Everything a curator needs to review one fix in the queue.

    Bundles the proposed fix with the original question/answer that prompted it,
    the most relevant manual excerpts (``manual_chunks``) for cross-checking, and
    the AI safety advisory (``prescreen``).
    """

    fix_id: uuid.UUID
    state: str
    question: str | None
    original_answer: str | None
    proposed_text: str
    submitted_by: uuid.UUID
    equipment_id: uuid.UUID
    manual_chunks: list[ManualChunkOut]
    prescreen: dict | None
    created_at: datetime


class ApproveRequest(BaseModel):
    """Body for approving a fix; ``edited_text`` lets the curator approve a revised
    version of the proposed text."""

    edited_text: str | None = None


class ResolveRequest(BaseModel):
    """Body for rejecting or flagging a fix; ``reason`` is recorded in the audit trail."""

    reason: str


class UploadAccepted(BaseModel):
    """Returned when a document upload is accepted for async ingestion; ``task_id``
    polls progress."""

    task_id: str
    status: str


class DocumentStatus(BaseModel):
    """Progress of an ingestion task; ``document_id`` is filled once ingestion finishes."""

    task_id: str
    status: str
    document_id: uuid.UUID | None = None


class DocumentOut(BaseModel):
    """A manual as returned to clients. ``superseded_by`` is set when a newer
    version has replaced this one."""

    id: uuid.UUID
    equipment_id: uuid.UUID
    title: str
    version: int
    superseded_by: uuid.UUID | None
    created_at: datetime


class UserOut(BaseModel):
    """A user as returned to admin clients."""

    id: uuid.UUID
    name: str
    email: str | None
    role: str
    created_at: datetime


class SetRoleRequest(BaseModel):
    """Body for changing a user's role (admin-only)."""

    role: str


class CreateUserRequest(BaseModel):
    """Body for creating a user within the caller's organization (admin-only)."""

    name: str
    email: str | None = None
    role: str


class UpdateUserRequest(BaseModel):
    """Partial update for a user (admin-only)."""

    name: str | None = None
    email: str | None = None
    role: str | None = None


class DevIdentityOut(BaseModel):
    """The identity returned by the local-only dev auto-login endpoint."""

    org_id: uuid.UUID
    user_id: uuid.UUID
    role: str


class FixSummaryOut(BaseModel):
    """A fix with full lifecycle metadata for the admin fixes table / audit view.

    Includes submitter and reviewer names (resolved server-side) and the review
    notes / approval timestamp so the whole history is visible at a glance.
    """

    fix_id: uuid.UUID
    state: str
    question: str | None
    proposed_text: str
    equipment_id: uuid.UUID
    submitted_by: uuid.UUID
    submitted_by_name: str | None
    reviewed_by: uuid.UUID | None
    reviewed_by_name: str | None
    review_notes: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CreateFixRequest(BaseModel):
    """Body for an admin/curator to author a fix directly (not via technician feedback)."""

    equipment_id: uuid.UUID
    proposed_text: str
    question: str | None = None


class UpdateFixRequest(BaseModel):
    """Partial update for a fix's text/question before it is approved."""

    proposed_text: str | None = None
    question: str | None = None
