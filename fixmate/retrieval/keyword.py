"""Keyword (full-text) search over chunks using PostgreSQL FTS.

The complement to vector search: it matches *exact* terms — error codes, part
numbers, model strings — by querying the precomputed ``tsv`` column. This is the
half of hybrid retrieval that reliably surfaces tokens like "E47" that semantic
search would otherwise smear into unrelated text. Reuses the same equipment /
superseded-version filters as ``vector.py`` so both searchers see the same rows.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fixmate.core.models import Chunk
from fixmate.retrieval.vector import _equipment_filter, active_document_filter


async def keyword_search(
    session: AsyncSession,
    query: str,
    equipment_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[Chunk]:
    """Return up to ``limit`` chunks matching ``query`` by full-text relevance.

    Same superseded/equipment filtering and RLS scoping as ``vector_search``.
    """
    # Postgres FTS over the generated 'english' tsvector — the query config MUST
    # match the column config (Phase 1) for stemming to line up. This is where
    # exact tokens like "E47" survive that pure-vector search would blur away.
    tsquery = func.plainto_tsquery("english", query)
    stmt = (
        select(Chunk)
        .where(Chunk.tsv.op("@@")(tsquery), active_document_filter())
        .order_by(func.ts_rank(Chunk.tsv, tsquery).desc())
        .limit(limit)
    )
    if equipment_id is not None:
        stmt = stmt.where(_equipment_filter(equipment_id))
    return list((await session.execute(stmt)).scalars().all())
