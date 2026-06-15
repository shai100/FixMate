import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from fixmate.answers.composer import Citation, compose_answer
from fixmate.api.deps import AuthContext, get_current_user
from fixmate.api.schemas import AnswerOut, AskRequest, CitationOut, FigureOut
from fixmate.core.db import session_for_org
from fixmate.core.models import Conversation, Document, Message

router = APIRouter(prefix="/conversations", tags=["ask"])


async def _document_titles(session, citations: list[Citation]) -> dict[uuid.UUID, str]:
    doc_ids = {c.document_id for c in citations if c.document_id}
    if not doc_ids:
        return {}
    rows = (
        await session.execute(select(Document.id, Document.title).where(Document.id.in_(doc_ids)))
    ).all()
    return {did: title for did, title in rows}


@router.post("/{conversation_id}/ask", response_model=AnswerOut)
async def ask(
    conversation_id: uuid.UUID,
    body: AskRequest,
    auth: AuthContext = Depends(get_current_user),
) -> AnswerOut:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be empty")

    async with session_for_org(auth.org_id) as s:
        conv = await s.get(Conversation, conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        equipment_id = conv.equipment_id

        prior = (
            (
                await s.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at)
                )
            )
            .scalars()
            .all()
        )
        history = [{"role": m.role, "content": m.content} for m in prior]

        s.add(
            Message(
                organization_id=auth.org_id,
                conversation_id=conversation_id,
                role="user",
                content=question,
            )
        )
        await s.commit()

    # Multi-turn context (FR-5): prior turns are passed as history, the new
    # question is composed separately by the RAG pipeline.
    answer = await compose_answer(
        auth.org_id,
        equipment_id,
        question,
        history,
        conversation_id=conversation_id,
    )

    async with session_for_org(auth.org_id) as s:
        assistant = Message(
            organization_id=auth.org_id,
            conversation_id=conversation_id,
            role="assistant",
            content=answer.text,
            answer_log_id=answer.answer_log_id,
        )
        s.add(assistant)
        await s.commit()
        message_id = assistant.id
        titles = await _document_titles(s, answer.citations)

    return AnswerOut(
        message_id=message_id,
        answer_log_id=answer.answer_log_id,
        text=answer.text,
        confidence=answer.confidence,
        escalated=answer.escalated,
        citations=[
            CitationOut(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=titles.get(c.document_id),
                page=c.page,
                source_type=c.source_type,
            )
            for c in answer.citations
        ],
        figures=[
            FigureOut(page=f["page"], caption=f["caption"], url=f["url"]) for f in answer.figures
        ],
    )
