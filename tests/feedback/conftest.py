from dataclasses import dataclass

import pytest

from fixmate.core.db import session_for_org
from fixmate.core.models import (
    AnswerLog,
    Chunk,
    Conversation,
    Document,
    EquipmentProfile,
    Message,
    User,
)

ZERO_VEC = [0.0] * 1024


@dataclass
class FeedbackWorld:
    org_id: object
    other_org_id: object
    user_id: object
    equipment_id: object
    conversation_id: object
    message_id: object
    answer_log_id: object
    chunk_ids: list


@pytest.fixture
async def feedback_world(two_orgs) -> FeedbackWorld:
    """A tenant with an answered message that cites two manual chunks.

    Seeds DB state directly (no Ollama) so the DB-level feedback behaviours —
    reinforcement counter and candidate-fix submission — can be tested without
    the integration stack.
    """
    org_a, org_b = two_orgs
    async with session_for_org(org_a) as s:
        user = User(organization_id=org_a, name="Tech One", role="tech")
        eq = EquipmentProfile(organization_id=org_a, name="Pump X")
        s.add_all([user, eq])
        await s.flush()

        doc = Document(
            organization_id=org_a,
            equipment_id=eq.id,
            title="Manual",
            storage_key=f"{org_a}/manual.pdf",
        )
        s.add(doc)
        await s.flush()

        c1 = Chunk(
            organization_id=org_a,
            document_id=doc.id,
            source_type="manual",
            content="Inspect the concentrate valve seat for scale buildup.",
            page=2,
            embedding=ZERO_VEC,
        )
        c2 = Chunk(
            organization_id=org_a,
            document_id=doc.id,
            source_type="manual",
            content="Tighten to 12 Nm during reassembly.",
            page=3,
            embedding=ZERO_VEC,
        )
        s.add_all([c1, c2])
        await s.flush()

        conv = Conversation(organization_id=org_a, user_id=user.id, equipment_id=eq.id)
        s.add(conv)
        await s.flush()

        log = AnswerLog(
            organization_id=org_a,
            conversation_id=conv.id,
            question="How do I fix error E47?",
            answer_text="Inspect the valve [chunk:%s] and tighten to 12 Nm [chunk:%s]."
            % (c1.id, c2.id),
            retrieved_chunk_ids=[c1.id, c2.id],
            model_version="qwen3:4b",
            provider="ollama",
            confidence="high",
            citations=[
                {"chunk_id": str(c1.id), "source_type": "manual", "page": 2},
                {"chunk_id": str(c2.id), "source_type": "manual", "page": 3},
            ],
        )
        s.add(log)
        await s.flush()

        msg = Message(
            organization_id=org_a,
            conversation_id=conv.id,
            role="assistant",
            content="Inspect the valve and tighten to 12 Nm.",
            answer_log_id=log.id,
        )
        s.add(msg)
        await s.commit()

        return FeedbackWorld(
            org_id=org_a,
            other_org_id=org_b,
            user_id=user.id,
            equipment_id=eq.id,
            conversation_id=conv.id,
            message_id=msg.id,
            answer_log_id=log.id,
            chunk_ids=[c1.id, c2.id],
        )
