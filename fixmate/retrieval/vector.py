import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fixmate.core.models import Chunk, Document, Fix


def active_document_filter():
    # Exclude chunks from superseded document versions (FR-9 / CLAUDE.md §10:
    # never retrieve outdated procedures). Field_fix chunks have no document and
    # are governed by fix state instead, so they always pass.
    superseded = (
        select(Document.id)
        .where(Document.id == Chunk.document_id, Document.superseded_by.isnot(None))
        .exists()
    )
    return ~superseded


def _equipment_filter(equipment_id: uuid.UUID):
    # A chunk belongs to the equipment if its manual document targets it, or —
    # for field_fix chunks (document_id is null) — its parent fix targets it.
    manual = (
        select(Document.id)
        .where(Document.id == Chunk.document_id, Document.equipment_id == equipment_id)
        .exists()
    )
    fix = (
        select(Fix.id)
        .where(Fix.id == Chunk.fix_id, Fix.equipment_id == equipment_id)
        .exists()
    )
    return or_(manual, fix)


async def vector_search(
    session: AsyncSession,
    query_embedding: list[float],
    equipment_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[Chunk]:
    # Cosine KNN over pgvector's HNSW index (schema: vector_cosine_ops). RLS on
    # the session already scopes rows to the tenant (CLAUDE.md §6).
    stmt = (
        select(Chunk)
        .where(active_document_filter())
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    if equipment_id is not None:
        stmt = stmt.where(_equipment_filter(equipment_id))
    return list((await session.execute(stmt)).scalars().all())
