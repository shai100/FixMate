import pytest
from sqlalchemy import select

from fixmate.core.db import session_for_org
from fixmate.core.models import AuditEvent, Chunk, Feedback, Fix
from fixmate.feedback.service import (
    EquipmentRequired,
    MessageNotFound,
    record_feedback,
)


async def test_helped_records_feedback_and_reinforces_cited_chunks(feedback_world):
    w = feedback_world
    result = await record_feedback(w.org_id, w.message_id, w.user_id, helped=True)

    assert result.helped is True
    assert result.fix_id is None

    async with session_for_org(w.org_id) as s:
        fb = (await s.execute(select(Feedback))).scalars().all()
        assert len(fb) == 1 and fb[0].helped is True and fb[0].fix_id is None

        # Both cited chunks were reinforced; nothing else exists to reinforce.
        signals = {
            cid: sig
            for cid, sig in (
                await s.execute(select(Chunk.id, Chunk.positive_signals))
            ).all()
        }
        assert all(signals[cid] == 1 for cid in w.chunk_ids)


async def test_not_helped_with_fix_text_opens_pending_review_fix(feedback_world):
    w = feedback_world
    result = await record_feedback(
        w.org_id,
        w.message_id,
        w.user_id,
        helped=False,
        fix_text="Replace the valve seat O-ring, part RG-2210.",
        photos=["org/photo1.jpg"],
    )

    assert result.fix_id is not None

    async with session_for_org(w.org_id) as s:
        fix = await s.get(Fix, result.fix_id)
        # Submitted, then immediately advanced to the review queue (spec §2.5).
        assert fix.state == "pending_review"
        assert fix.equipment_id == w.equipment_id
        assert fix.answer_log_id == w.answer_log_id
        assert fix.question_text == "How do I fix error E47?"
        assert fix.submitted_by == w.user_id
        assert fix.proposed_text.startswith("Replace the valve seat")

        fb = (await s.execute(select(Feedback))).scalars().one()
        assert fb.helped is False and fb.fix_id == fix.id

        audit = (
            await s.execute(select(AuditEvent).where(AuditEvent.entity_id == fix.id))
        ).scalars().one()
        assert audit.action == "submit"
        assert audit.before == {"state": "submitted"}
        assert audit.after == {"state": "pending_review"}
        assert audit.actor_id == w.user_id

        # Cited chunks are NOT reinforced on a negative signal.
        signals = (await s.execute(select(Chunk.positive_signals))).scalars().all()
        assert signals == [0, 0]


async def test_submitted_fix_is_not_indexed_so_never_retrievable(feedback_world):
    """A pending fix must not become a chunk — never served before approval (§2.4)."""
    w = feedback_world
    result = await record_feedback(
        w.org_id,
        w.message_id,
        w.user_id,
        helped=False,
        fix_text="Bypass the interlock to keep running.",
    )

    async with session_for_org(w.org_id) as s:
        fix_chunks = (
            await s.execute(select(Chunk).where(Chunk.fix_id == result.fix_id))
        ).scalars().all()
        assert fix_chunks == []
        field_fixes = (
            await s.execute(select(Chunk).where(Chunk.source_type == "field_fix"))
        ).scalars().all()
        assert field_fixes == []


async def test_not_helped_without_fix_text_records_feedback_only(feedback_world):
    w = feedback_world
    result = await record_feedback(w.org_id, w.message_id, w.user_id, helped=False)

    assert result.fix_id is None
    async with session_for_org(w.org_id) as s:
        assert (await s.execute(select(Fix))).scalars().all() == []
        fb = (await s.execute(select(Feedback))).scalars().one()
        assert fb.helped is False


async def test_unknown_message_raises(feedback_world):
    import uuid

    w = feedback_world
    with pytest.raises(MessageNotFound):
        await record_feedback(w.org_id, uuid.uuid4(), w.user_id, helped=True)


async def test_fix_without_equipment_is_rejected(two_orgs):
    """A candidate fix needs equipment to be reviewable/indexable later."""
    from fixmate.core.models import AnswerLog, Conversation, Message, User

    org_a, _ = two_orgs
    async with session_for_org(org_a) as s:
        user = User(organization_id=org_a, name="T", role="tech")
        s.add(user)
        await s.flush()
        conv = Conversation(organization_id=org_a, user_id=user.id, equipment_id=None)
        s.add(conv)
        await s.flush()
        log = AnswerLog(
            organization_id=org_a,
            conversation_id=conv.id,
            question="q",
            answer_text="a",
            model_version="m",
            provider="ollama",
            confidence="high",
        )
        s.add(log)
        await s.flush()
        msg = Message(
            organization_id=org_a,
            conversation_id=conv.id,
            role="assistant",
            content="a",
            answer_log_id=log.id,
        )
        s.add(msg)
        await s.commit()
        msg_id, user_id = msg.id, user.id

    with pytest.raises(EquipmentRequired):
        await record_feedback(org_a, msg_id, user_id, helped=False, fix_text="do x")
