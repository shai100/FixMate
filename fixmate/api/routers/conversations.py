import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from fixmate.api.deps import AuthContext, get_current_user
from fixmate.api.schemas import ConversationOut, CreateConversation, MessageOut
from fixmate.core.db import session_for_org
from fixmate.core.models import Conversation, Message

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", status_code=201, response_model=ConversationOut)
async def create_conversation(
    body: CreateConversation,
    auth: AuthContext = Depends(get_current_user),
) -> ConversationOut:
    async with session_for_org(auth.org_id) as s:
        conv = Conversation(
            organization_id=auth.org_id,
            user_id=auth.user_id,
            equipment_id=body.equipment_id,
        )
        s.add(conv)
        await s.commit()
        return ConversationOut(
            id=conv.id, equipment_id=conv.equipment_id, created_at=conv.created_at, messages=[]
        )


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
) -> ConversationOut:
    async with session_for_org(auth.org_id) as s:
        # RLS scopes the lookup to the tenant: another org's conversation is
        # simply invisible here, so a cross-tenant fetch 404s (Phase 6.2 test).
        conv = await s.get(Conversation, conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        rows = (
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
        return ConversationOut(
            id=conv.id,
            equipment_id=conv.equipment_id,
            created_at=conv.created_at,
            messages=[
                MessageOut(
                    id=m.id,
                    role=m.role,
                    content=m.content,
                    answer_log_id=m.answer_log_id,
                    created_at=m.created_at,
                )
                for m in rows
            ],
        )
