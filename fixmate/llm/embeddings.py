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


async def embed(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts into 1024-dim vectors via the Ollama embed API.

    Asserts every returned vector has the expected dimension so a model/config
    mismatch fails loudly instead of corrupting the index.
    """
    # Embeddings always run on the Ollama/CPU path regardless of LLM_PROVIDER
    # (spec §8.3) so the vector dimension stays a stable cross-phase contract.
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/embed",
            json={"model": settings.ollama_embedding_model, "input": texts},
        )
        resp.raise_for_status()
        vectors = resp.json()["embeddings"]
    for vec in vectors:
        assert len(vec) == EMBEDDING_DIM, f"expected {EMBEDDING_DIM}-dim, got {len(vec)}"
    return vectors
