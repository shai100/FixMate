# Speed up retrieval: rerank from stored embeddings (no re-embed)

**Date:** 2026-06-22
**Commit:** _(pending)_ — "Speed up retrieval: rerank reuses stored chunk embeddings"
**Relates to:** CLAUDE.md §2.2 (Hybrid Retrieval), §7.1 (Latency SLOs); `docs/ARCHITECTURE.md` §5.5

## Problem

Queries (reported on the MPS org, e.g. "no light in power btn") were very slow.
The dominant cost was in the retrieval reranker, not the LLM.

`rerank()` re-embedded the query **plus every fused candidate chunk** through
BGE-M3 on the local CPU profile at request time:

```python
vectors = await embed([query] + [c.content for c in chunks])  # ~21 CPU embeddings/query
```

This is fully redundant: each candidate's 1024-dim embedding is already stored in
`Chunk.embedding` (computed once at ingestion), and the query was already embedded
once in `search()`. So every question paid for ~21 unnecessary CPU embeddings.

## What was built

- **`fixmate/retrieval/rerank.py`** — `rerank` is now a synchronous function
  `rerank(query_embedding, chunks)` that scores each candidate with
  `_cosine_to_unit(query_embedding, chunk.embedding)` using the **stored** vectors.
  No `embed()` call, no `await`. Cross-encoder upgrade path noted as needing a
  config flag since it would reintroduce a model call.
- **`fixmate/retrieval/service.py`** — passes the already-computed `qvec` to
  `rerank` (was `await rerank(query, candidates)`).
- **`docs/ARCHITECTURE.md`** §5.5 — documents that reranking reuses stored
  embeddings and why it no longer re-embeds at request time.

No schema, API contract, or ranking-behavior change: same vectors, same cosine,
same ordering — only the source of the candidate vectors changed (DB vs. re-embed).

## Verification evidence

Infra up: `fixmate-postgres-1 (healthy)`, `fixmate-ollama-1`, redis, minio.

Retrieval integration tests (full hybrid search path) pass:

```
tests/retrieval/test_search_integration.py::test_keyword_finds_exact_error_code PASSED
tests/retrieval/test_search_integration.py::test_hybrid_search_surfaces_e47_chunk PASSED
tests/retrieval/test_search_integration.py::test_hybrid_beats_vector_alone_for_error_code PASSED
tests/retrieval/test_search_integration.py::test_equipment_filter_isolates_results PASSED
======================== 4 passed in 103.65s ========================
```

Before/after benchmark, real org `5069b448…` (6151 chunks), query
"no light in power btn", 20 candidates:

```
OLD rerank (re-embed query+candidates): 7262 ms
NEW rerank (stored embeddings):            9.82 ms
-> saved ~7.25s per query on the rerank step alone
full search() now: 1014 ms, 8 results
```

The rerank step went from ~7.3s to ~0.01s; end-to-end retrieval is now ~1s,
bounded by the single query embedding + DB round-trips.
