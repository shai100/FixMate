import httpx

from fixmate.core.settings import settings

EMBEDDING_DIM = 1024  # BGE-M3 contract with schema vector(1024) (plan Appendix A.2)


async def embed(texts: list[str]) -> list[list[float]]:
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
