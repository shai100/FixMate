"""Turns text into embedding vectors for semantic search.

An embedding is a list of numbers that captures a text's meaning, so two texts
with similar meaning have nearby vectors. FixMate stores one per chunk and one
per query, then compares them (see ``retrieval/vector.py``). Embeddings always
run on the local Ollama/CPU path (BGE-M3) regardless of ``LLM_PROVIDER`` so the
1024-dim vector size stays a fixed contract with the database schema — changing
it would require re-embedding every chunk.
"""

import asyncio
from collections.abc import Callable

import httpx

from fixmate.core.settings import settings

EMBEDDING_DIM = 1024  # BGE-M3 contract with schema vector(1024) (plan Appendix A.2)

# Max texts per Ollama embed request. A whole manual can produce thousands of
# chunks; sending them all in one POST blows past the request timeout on the
# CPU profile (BGE-M3 is not fast), which previously made large-manual ingestion
# fail with a ReadTimeout. Embedding in bounded batches keeps each request well
# inside the timeout.
_EMBED_BATCH_SIZE = 32

# Number of embed requests in flight at once. Issuing batches strictly serially
# left the embedding server idle during each request's network/queue overhead,
# capping throughput at ~0.9 chunks/s on the local CPU profile. Overlapping a
# few requests keeps BGE-M3 continuously fed and ~triples throughput (measured
# ~2.8 chunks/s — the CPU-saturation ceiling on the 4 GB profile), which is the
# difference between a ~36-minute and a ~12-minute large-manual ingest. Kept
# small so we saturate the model without thrashing memory on the 4 GB profile.
_EMBED_CONCURRENCY = 4


async def embed(
    texts: list[str],
    on_progress: Callable[[int, int], None] | None = None,
) -> list[list[float]]:
    """Embed a batch of texts into 1024-dim vectors via the Ollama embed API.

    Splits the input into bounded sub-batches (``_EMBED_BATCH_SIZE``) so a large
    manual's chunks never overflow a single request's timeout, issues up to
    ``_EMBED_CONCURRENCY`` of them concurrently to keep the embedding model busy,
    then reassembles the vectors in input order. Asserts every returned vector
    has the expected dimension so a model/config mismatch fails loudly instead of
    corrupting the index.

    Args:
        texts: The chunk texts to embed.
        on_progress: Optional callback invoked ``(done_texts, total_texts)`` each
            time a batch completes, so the ingestion pipeline can surface a live
            progress bar during the embedding stage (the slowest phase on the CPU
            profile). Called from the event loop thread; keep it cheap.

    How it works: the texts are sliced into ordered batches; a semaphore caps how
    many are POSTed at once. ``asyncio.gather`` preserves the batch order it is
    given, so concatenating the results reproduces the original input order — the
    i-th returned vector still belongs to the i-th input text.
    """
    if not texts:
        return []
    # Embeddings always run on the Ollama/CPU path regardless of LLM_PROVIDER
    # (spec §8.3) so the vector dimension stays a stable cross-phase contract.
    batches = [
        texts[start : start + _EMBED_BATCH_SIZE]
        for start in range(0, len(texts), _EMBED_BATCH_SIZE)
    ]
    sem = asyncio.Semaphore(_EMBED_CONCURRENCY)
    done = 0
    total = len(texts)

    async with httpx.AsyncClient(timeout=120) as client:

        async def embed_batch(batch: list[str]) -> list[list[float]]:
            nonlocal done
            async with sem:
                resp = await client.post(
                    f"{settings.ollama_base_url.rstrip('/')}/api/embed",
                    json={"model": settings.ollama_embedding_model, "input": batch},
                )
                resp.raise_for_status()
                vectors = resp.json()["embeddings"]
            # Report after the request returns, not when it is scheduled, so the
            # bar reflects work actually finished. gather runs concurrently, so
            # batches may complete out of order — we only count, never assume order.
            done += len(batch)
            if on_progress is not None:
                on_progress(done, total)
            return vectors

        batch_results = await asyncio.gather(*(embed_batch(b) for b in batches))

    vectors = [vec for batch in batch_results for vec in batch]
    for vec in vectors:
        assert len(vec) == EMBEDDING_DIM, f"expected {EMBEDDING_DIM}-dim, got {len(vec)}"
    return vectors
