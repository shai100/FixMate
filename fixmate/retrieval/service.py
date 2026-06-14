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
    """Hybrid retrieval: vector + keyword → RRF → field-fix boost → rerank → top_k.

    The boost is applied to the *rerank* scores (not just fusion) so an approved
    field fix outranks comparably-relevant manual content in the final order —
    the approved-fix moat (spec §2.4), provable by the Phase 8 moat test.
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

    reranked = await rerank(query, candidates)
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
