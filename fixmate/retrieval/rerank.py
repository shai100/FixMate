import math

from fixmate.core.models import Chunk
from fixmate.llm.embeddings import embed


def _cosine_to_unit(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    # Map cosine [-1, 1] → [0, 1] so downstream confidence bands (Phase 5) read
    # as a probability-like relevance score.
    return (dot / (na * nb) + 1.0) / 2.0


async def rerank(query: str, chunks: list[Chunk]) -> list[tuple[Chunk, float]]:
    """MVP reranker: re-score candidates by BGE-M3 cosine similarity to the query.

    Cross-encoder bge-reranker-v2-m3 is a drop-in upgrade later — same signature.
    """
    if not chunks:
        return []
    vectors = await embed([query] + [c.content for c in chunks])
    qvec, cand_vecs = vectors[0], vectors[1:]
    scored = [(chunk, _cosine_to_unit(qvec, cv)) for chunk, cv in zip(chunks, cand_vecs)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
