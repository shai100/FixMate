"""Turns text into embedding vectors for semantic search.

An embedding is a list of numbers that captures a text's meaning, so two texts
with similar meaning have nearby vectors. FixMate stores one per chunk and one
per query, then compares them (see ``retrieval/vector.py``). Embeddings always
run on the local Ollama/CPU path (BGE-M3) regardless of ``LLM_PROVIDER`` so the
1024-dim vector size stays a fixed contract with the database schema — changing
it would require re-embedding every chunk.
"""

import httpx

from fixmate.core.settings import settings

EMBEDDING_DIM = 1024  # BGE-M3 contract with schema vector(1024) (plan Appendix A.2)

# Max texts per Ollama embed request. A whole manual can produce hundreds of
# chunks; sending them all in one POST blows past the request timeout on the
# CPU profile (BGE-M3 is not fast), which previously made large-manual ingestion
# fail with a ReadTimeout. Embedding in bounded batches keeps each request well
# inside the timeout while the SLO (<10min for a 500-page manual) is met across
# the loop.
_EMBED_BATCH_SIZE = 32


async def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts into 1024-dim vectors via the Ollama embed API.

    Splits the input into bounded sub-batches (``_EMBED_BATCH_SIZE``) so a large
    manual's chunks never overflow a single request's timeout, then concatenates
    the results in order. Asserts every returned vector has the expected
    dimension so a model/config mismatch fails loudly instead of corrupting the
    index.
    """
    if not texts:
        return []
    # Embeddings always run on the Ollama/CPU path regardless of LLM_PROVIDER
    # (spec §8.3) so the vector dimension stays a stable cross-phase contract.
    vectors: list[list[float]] = []
    async with httpx.AsyncClient(timeout=120) as client:
        for start in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[start : start + _EMBED_BATCH_SIZE]
            resp = await client.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/embed",
                json={"model": settings.ollama_embedding_model, "input": batch},
            )
            resp.raise_for_status()
            vectors.extend(resp.json()["embeddings"])
    for vec in vectors:
        assert len(vec) == EMBEDDING_DIM, f"expected {EMBEDDING_DIM}-dim, got {len(vec)}"
    return vectors
