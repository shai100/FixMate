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


class UploadAccepted(BaseModel):
    task_id: str
    status: str


class DocumentStatus(BaseModel):
    task_id: str
    status: str
    document_id: uuid.UUID | None = None
