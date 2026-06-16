import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateConversation(BaseModel):
    equipment_id: uuid.UUID | None = None


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    answer_log_id: uuid.UUID | None
    created_at: datetime


class ConversationOut(BaseModel):
    id: uuid.UUID
    equipment_id: uuid.UUID | None
    created_at: datetime
    messages: list[MessageOut] = []


class AskRequest(BaseModel):
    question: str


class CitationOut(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID | None
    document_title: str | None
    page: int | None
    source_type: str


class FigureOut(BaseModel):
    page: int
    caption: str | None
    url: str


class AnswerOut(BaseModel):
    message_id: uuid.UUID
    answer_log_id: uuid.UUID
    text: str
    confidence: str
    escalated: bool
    citations: list[CitationOut]
    figures: list[FigureOut]


class FeedbackRequest(BaseModel):
    helped: bool
    fix_text: str | None = None
    photos: list[str] | None = None


class FeedbackOut(BaseModel):
    feedback_id: uuid.UUID
    helped: bool
    fix_id: uuid.UUID | None = None


class CreateEquipment(BaseModel):
    name: str
    manufacturer: str | None = None
    model: str | None = None


class EquipmentOut(BaseModel):
    id: uuid.UUID
    name: str
    manufacturer: str | None
    model: str | None
    created_at: datetime


class UpdateEquipment(BaseModel):
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None


class UpdateDocument(BaseModel):
    title: str | None = None


class ManualChunkOut(BaseModel):
    chunk_id: str
    page: int | None
    text: str
    score: float


class ReviewItemOut(BaseModel):
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
    edited_text: str | None = None


class ResolveRequest(BaseModel):
    reason: str


class UploadAccepted(BaseModel):
    task_id: str
    status: str


class DocumentStatus(BaseModel):
    task_id: str
    status: str
    document_id: uuid.UUID | None = None


class DocumentOut(BaseModel):
    id: uuid.UUID
    equipment_id: uuid.UUID
    title: str
    version: int
    superseded_by: uuid.UUID | None
    created_at: datetime


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None
    role: str
    created_at: datetime


class SetRoleRequest(BaseModel):
    role: str


class CreateUserRequest(BaseModel):
    name: str
    email: str | None = None
    role: str


class UpdateUserRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    role: str | None = None


class DevIdentityOut(BaseModel):
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: str


class FixSummaryOut(BaseModel):
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
    equipment_id: uuid.UUID
    proposed_text: str
    question: str | None = None


class UpdateFixRequest(BaseModel):
    proposed_text: str | None = None
    question: str | None = None
