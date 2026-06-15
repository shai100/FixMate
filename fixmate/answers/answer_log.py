import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from fixmate.core.models import AnswerLog


async def write_answer_log(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    question: str,
    answer_text: str,
    retrieved_chunk_ids: list[uuid.UUID],
    model_version: str,
    provider: str,
    confidence: str,
    citations: list[dict],
    groundedness: dict,
    tokens_used: int,
    conversation_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Persist the immutable answer record (CLAUDE.md §4.5 / spec §8.2).

    Stores the exact retrieved chunk ids, model/provider, confidence, citations,
    and the groundedness outcome so any answer is later reconstructable for
    regression and "why did it say that?" investigations.
    """
    log = AnswerLog(
        organization_id=org_id,
        conversation_id=conversation_id,
        question=question,
        answer_text=answer_text,
        retrieved_chunk_ids=retrieved_chunk_ids,
        model_version=model_version,
        provider=provider,
        confidence=confidence,
        citations=citations,
        groundedness=groundedness,
        tokens_used=tokens_used,
    )
    session.add(log)
    await session.flush()
    return log.id
