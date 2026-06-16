"""Reranking — a second, finer pass to reorder the fused candidate chunks.

Fusion (RRF) only knows rank positions, not how relevant each candidate really
is. The reranker re-scores the shortlist directly against the query to sharpen
the final ordering. This MVP version uses BGE-M3 cosine similarity; a heavier
cross-encoder (bge-reranker-v2-m3) is a drop-in upgrade with the same signature.
"""

import math

from fixmate.core.models import Chunk
from fixmate.llm.embeddings import embed


def _cosine_to_unit(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two vectors, remapped from [-1, 1] to [0, 1].

    The [0, 1] range lets the downstream confidence bands read the score as a
    probability-like relevance. Returns 0 if either vector is all zeros.
    """
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    # Map cosine [-1, 1] → [0, 1] so downstream confidence bands (Phase 5) read
    # as a probability-like relevance score.
    return (dot / (na * nb) + 1.0) / 2.0


async def rerank(query: str, chunks: list[Chunk]) -> list[tuple[Chunk, float]]:
    """Re-score and reorder ``chunks`` by similarity to ``query`` (best first).

    Embeds the query and all candidates in one batch, scores each candidate, and
    returns ``(chunk, score)`` pairs sorted high-to-low. Empty in, empty out.
    Cross-encoder bge-reranker-v2-m3 is a drop-in upgrade later — same signature.
    """
    if not chunks:
        return []
    vectors = await embed([query] + [c.content for c in chunks])
    qvec, cand_vecs = vectors[0], vectors[1:]
    scored = [(chunk, _cosine_to_unit(qvec, cv)) for chunk, cv in zip(chunks, cand_vecs)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
