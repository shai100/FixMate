"""Records technician feedback and turns it into useful signals.

This is the closing of the learning loop. When a technician says an answer
"helped", we reinforce the chunks it cited (a ranking signal for the future).
When they say it "didn't help" and propose a better fix, we open that fix as a
candidate and send it straight to the curation review queue — never auto-serving
it (CLAUDE.md §2.5). One public function, ``record_feedback``, does both.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import update

from fixmate.core.db import session_for_org
from fixmate.core.models import AnswerLog, AuditEvent, Chunk, Conversation, Feedback, Fix, Message


class MessageNotFound(Exception):
    """Raised when the message being given feedback on doesn't exist."""


class EquipmentRequired(Exception):
    """A candidate fix needs an equipment profile to be reviewable/indexable."""


@dataclass
class FeedbackResult:
    """Outcome of recording feedback; ``fix_id`` is set when a candidate fix was opened."""

    feedback_id: uuid.UUID
    fix_id: uuid.UUID | None
    helped: bool


def _cited_chunk_ids(answer_log: AnswerLog | None) -> list[uuid.UUID]:
    """Chunk ids the answer actually cited (not the full retrieved set).

    The positive signal reinforces the chunks the technician was shown and acted
    on, which is the FR-13 helpfulness signal — not every candidate retrieved.
    """
    if answer_log is None or not answer_log.citations:
        return []
    ids: list[uuid.UUID] = []
    for cite in answer_log.citations:
        cid = cite.get("chunk_id") if isinstance(cite, dict) else None
        if cid:
            ids.append(uuid.UUID(str(cid)))
    return ids


async def record_feedback(
    org_id: uuid.UUID,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    helped: bool,
    fix_text: str | None = None,
    photos: list | None = None,
) -> FeedbackResult:
    """Record a technician's "did it help?" signal (FR-12/FR-13).

    helped=True   → feedback row; reinforce the cited chunks (positive_signals++).
    helped=False  → feedback row; if fix_text is given, open a candidate fix and
                    move it straight to pending_review with an audit trail. The
                    fix is *not* indexed, so it is never retrievable until a
                    curator approves it (spec §2.4).
    """
    org_id = uuid.UUID(str(org_id))
    async with session_for_org(org_id) as s:
        message = await s.get(Message, message_id)
        if message is None:
            raise MessageNotFound(str(message_id))

        answer_log = (
            await s.get(AnswerLog, message.answer_log_id) if message.answer_log_id else None
        )

        feedback = Feedback(
            organization_id=org_id,
            message_id=message_id,
            user_id=user_id,
            helped=helped,
        )

        fix_id: uuid.UUID | None = None
        if helped:
            chunk_ids = _cited_chunk_ids(answer_log)
            if chunk_ids:
                await s.execute(
                    update(Chunk)
                    .where(Chunk.id.in_(chunk_ids))
                    .values(positive_signals=Chunk.positive_signals + 1)
                )
        elif fix_text and fix_text.strip():
            conv = await s.get(Conversation, message.conversation_id)
            equipment_id = conv.equipment_id if conv else None
            if equipment_id is None:
                raise EquipmentRequired(str(message.conversation_id))

            fix = Fix(
                organization_id=org_id,
                equipment_id=equipment_id,
                question_text=answer_log.question if answer_log else None,
                answer_log_id=message.answer_log_id,
                proposed_text=fix_text.strip(),
                photos=photos,
                submitted_by=user_id,
                state="submitted",
            )
            s.add(fix)
            await s.flush()

            # AI assists, humans approve (spec §2.5): a fresh submission goes to
            # the review queue immediately — never auto-approved.
            fix.state = "pending_review"
            s.add(
                AuditEvent(
                    organization_id=org_id,
                    actor_id=user_id,
                    entity_type="fix",
                    entity_id=fix.id,
                    action="submit",
                    before={"state": "submitted"},
                    after={"state": "pending_review"},
                )
            )
            feedback.fix_id = fix.id
            fix_id = fix.id

        s.add(feedback)
        await s.commit()
        return FeedbackResult(feedback_id=feedback.id, fix_id=fix_id, helped=helped)
