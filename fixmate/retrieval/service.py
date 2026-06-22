"""Hybrid retrieval — finds the most relevant knowledge for a question.

"Hybrid" because it combines two complementary searches and blends them:

  - **Dense vector search** (``vector.py``) finds passages that *mean* the same
    thing as the query, even with different words.
  - **Keyword search** (``keyword.py``) finds *exact* tokens — error codes like
    "E47", part numbers, specs — which vector search tends to blur away.

The two ranked lists are merged with Reciprocal Rank Fusion (``fusion.py``),
the top candidates are re-scored by a reranker (``rerank.py``), approved field
fixes get a ranking boost (the business "moat"), and the best ``top_k`` are
returned. ``search`` is the single public entry point used by the answer
pipeline.
"""

import uuid
from dataclasses import dataclass

from fixmate.core.db import session_for_org
from fixmate.core.models import Chunk
from fixmate.llm.embeddings import embed
from fixmate.retrieval.fusion import apply_field_fix_boost, reciprocal_rank_fusion
from fixmate.retrieval.keyword import keyword_search
from fixmate.retrieval.rerank import rerank
from fixmate.retrieval.vector import vector_search

CANDIDATE_POOL = 20  # how many fused candidates to rerank


@dataclass
class ScoredChunk:
    """A retrieved chunk plus its final relevance ``score`` (higher = better).

    This is the shape retrieval hands to the rest of the system; ``source_type``
    distinguishes manual content from field fixes, and ``fix_id`` links field-fix
    chunks back to their ``Fix`` for badge lookup.
    """

    chunk_id: uuid.UUID
    document_id: uuid.UUID | None
    source_type: str
    page: int | None
    text: str
    score: float
    fix_id: uuid.UUID | None


async def search(
    org_id: uuid.UUID,
    equipment_id: uuid.UUID | None,
    query: str,
    top_k: int = 8,
) -> list[ScoredChunk]:
    """Find the ``top_k`` most relevant chunks for ``query`` (the retrieval entry point).

    Steps: embed the query -> run vector + keyword search (both RLS-scoped to the
    tenant and optionally filtered to one equipment profile) -> fuse the two
    rankings with RRF -> rerank the top candidates -> boost approved field fixes
    -> sort and return the best ``top_k`` as ``ScoredChunk``s.

    The boost is applied to the *rerank* scores (not just fusion) so an approved
    field fix outranks comparably-relevant manual content in the final order —
    the approved-fix moat (spec §2.4), provable by the Phase 8 moat test.

    Args:
        org_id: Tenant whose index to search.
        equipment_id: If set, restrict results to this equipment's material.
        query: The natural-language search text.
        top_k: How many results to return.

    Returns:
        ``ScoredChunk``s ordered best-first; empty if nothing matched.
    """
    [qvec] = await embed([query])

    async with session_for_org(org_id) as s:
        vec_hits = await vector_search(s, qvec, equipment_id)
        kw_hits = await keyword_search(s, query, equipment_id)

    by_id: dict[str, Chunk] = {str(c.id): c for c in [*vec_hits, *kw_hits]}
    if not by_id:
        return []

    fused_ids = reciprocal_rank_fusion(
        [[str(c.id) for c in vec_hits], [str(c.id) for c in kw_hits]]
    )
    candidates = [by_id[cid] for cid in fused_ids[:CANDIDATE_POOL]]

    reranked = rerank(qvec, candidates)
    rerank_scores = {str(chunk.id): score for chunk, score in reranked}
    field_fix_ids = {cid for cid, c in by_id.items() if c.source_type == "field_fix"}
    boosted = apply_field_fix_boost(rerank_scores, field_fix_ids)

    ordered = sorted(reranked, key=lambda x: boosted[str(x[0].id)], reverse=True)
    return [
        ScoredChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            source_type=chunk.source_type,
            page=chunk.page,
            text=chunk.content,
            score=boosted[str(chunk.id)],
            fix_id=chunk.fix_id,
        )
        for chunk, _ in ordered[:top_k]
    ]
