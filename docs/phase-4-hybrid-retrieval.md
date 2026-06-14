# Phase 4 — Hybrid retrieval (vector + FTS + RRF + field-fix boost)

**Commit:** _(this commit)_ — `feat: hybrid retrieval — vector + FTS + RRF + field-fix boost (phase 4)`
**Plan:** `docs/superpowers/plans/2026-06-12-fixmate-mvp.md` §Phase 4 (tasks 4.1–4.6)
**Architecture rules:** CLAUDE.md §2.2 (hybrid retrieval), §2.4 (approved-fix moat), §10 (versioning pitfall)
**Date:** 2026-06-14

---

## What was built

A tenant-scoped hybrid retrieval layer that merges dense-vector and keyword search,
fuses them with reciprocal-rank fusion, boosts approved field fixes, and reranks
the candidate pool. New package `fixmate/retrieval/`:

- **`fusion.py`** — `reciprocal_rank_fusion(result_lists, k=60, with_scores=False)` and
  `apply_field_fix_boost(scores, field_fix_ids, boost=1.15)`. RRF uses only rank
  position so it fuses searchers whose raw scores are not comparable. `with_scores`
  exposes the score dict the boost operates on. The boost (1.15) is a safety/business
  constant per Appendix A.8 — tune only via Phase 12 evals.
- **`vector.py`** — `vector_search(...)` cosine KNN via pgvector
  (`Chunk.embedding.cosine_distance(qvec)`, HNSW `vector_cosine_ops`). Also defines the
  shared `_equipment_filter` (manual chunks via `documents.equipment_id`, field_fix
  chunks via `fixes.equipment_id`) and `active_document_filter` (excludes superseded
  document versions — FR-9 / CLAUDE.md §10).
- **`keyword.py`** — `keyword_search(...)` Postgres FTS: `tsv @@ plainto_tsquery('english', q)`
  ordered by `ts_rank`. The `'english'` query config matches the Phase-1 generated
  tsvector column so stemming lines up. This is the path that guarantees exact tokens
  like `E47` are recalled when pure-vector ranking blurs them (spec §5.2).
- **`rerank.py`** — `rerank(query, chunks)` MVP reranker: re-score candidates by BGE-M3
  cosine similarity, mapped to `[0,1]`. Same signature as the future cross-encoder
  `bge-reranker-v2-m3` drop-in.
- **`service.py`** — `ScoredChunk` dataclass (Appendix A.4) and
  `search(org_id, equipment_id, query, top_k=8)`: embed query → vector + keyword →
  RRF candidate pool (20) → rerank → **field-fix boost applied to rerank scores** →
  top_k. Boosting the final rerank scores (not just fusion) is what makes an approved
  field fix outrank comparably-relevant manual content — the moat, provable by the
  Phase 8 moat test. All DB access goes through `session_for_org` (RLS-scoped).
- **`cli.py`** — `python -m fixmate.retrieval.cli "<query>" --org <name> [--equipment <name>] [--top-k N]`
  prints a ranked table (score, source_type, page, snippet).

### Design decisions
- **Boost on rerank scores, not fusion order.** The reranker fully reorders by semantic
  similarity, which would otherwise discard the fusion/boost. Applying the field-fix
  multiplier to the final rerank scores keeps confidence (top rerank score, consumed by
  Phase 5) meaningful while honoring the moat.
- **Superseded-version exclusion** added to both searchers. Repeated ingestion of the
  same title creates new versions (Phase 3 FR-9); without this filter, stale chunks from
  superseded documents surfaced as duplicates. Field_fix chunks (no `document_id`) always
  pass — their lifecycle is governed by fix state, not document version.

## Verification evidence

Compose services up (postgres healthy, ollama with qwen3:4b + bge-m3).

### Unit + integration tests (`pytest tests/retrieval -v`)
```
tests/retrieval/test_fusion.py::test_rrf_rewards_agreement PASSED
tests/retrieval/test_fusion.py::test_rrf_returns_scores_when_requested PASSED
tests/retrieval/test_fusion.py::test_field_fix_boost_promotes_fix PASSED
tests/retrieval/test_search_integration.py::test_keyword_finds_exact_error_code PASSED
tests/retrieval/test_search_integration.py::test_hybrid_search_surfaces_e47_chunk PASSED
tests/retrieval/test_search_integration.py::test_hybrid_beats_vector_alone_for_error_code PASSED
tests/retrieval/test_search_integration.py::test_equipment_filter_isolates_results PASSED
7 passed in 13.76s
```

### Full suite (no regressions)
```
28 passed in 50.64s
```

### Lint
```
$ ruff check fixmate/retrieval
All checks passed!
```

### Standalone CLI (against Phase-3 ingested `demo` org)
```
$ python -m fixmate.retrieval.cli "E47 concentrate valve" --org demo --equipment "Pump X"
 score  source     page  text
--------------------------------------------------------------------------------
 0.846  manual        2  Error E47: concentrate valve blocked. Inspect the valve seat for scale buildup.
 0.741  manual        1  Maintenance manual. This pump moves dialysate concentrate through the circuit.
 0.708  manual        3  Reassembly. Tighten to 12 Nm. Do not exceed torque or the housing will crack.
```
The exact-error-code chunk ranks first; superseded-version duplicates are excluded.
