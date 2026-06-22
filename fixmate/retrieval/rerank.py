"""Reranking — a second, finer pass to reorder the fused candidate chunks.

Fusion (RRF) only knows rank positions, not how relevant each candidate really
is. The reranker re-scores the shortlist directly against the query to sharpen
the final ordering. This MVP version uses BGE-M3 cosine similarity; a heavier
cross-encoder (bge-reranker-v2-m3) is a drop-in upgrade with the same signature.
"""

import math

from fixmate.core.models import Chunk


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


def rerank(query_embedding: list[float], chunks: list[Chunk]) -> list[tuple[Chunk, float]]:
    """Re-score and reorder ``chunks`` by similarity to the query (best first).

    Scores each candidate against the query using the *already-computed*
    embeddings: ``query_embedding`` was produced once when retrieval embedded the
    query, and each candidate's vector is the ``Chunk.embedding`` already stored in
    the index at ingestion time. Reranking is therefore pure in-memory cosine math
    with no model round-trip — re-embedding the query plus every candidate on the
    CPU profile (BGE-M3) was the dominant per-question latency and is fully
    redundant with the vectors the system already holds. Returns ``(chunk, score)``
    pairs sorted high-to-low. Empty in, empty out. A cross-encoder
    (bge-reranker-v2-m3) remains a future upgrade, but would reintroduce a model
    call by design and should be gated behind a config flag.
    """
    if not chunks:
        return []
    scored = [
        (chunk, _cosine_to_unit(query_embedding, list(chunk.embedding)))
        for chunk in chunks
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
