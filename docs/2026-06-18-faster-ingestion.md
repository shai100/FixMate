# Faster PDF ingestion — concurrent embedding & captioning, image dedup

**Commit:** _(this commit)_ — "Speed up PDF ingestion: concurrent embedding + captioning, dedup figures"
**Date:** 2026-06-18
**Relates to:** CLAUDE.md §7.1 (ingestion <10 min SLO), spec §8.3 (local 4 GB CPU profile), §2.3 (image-aware ingestion)

## Problem

Uploading `sample-manual 02.pdf` (714 pages) left the UI showing
"Queued for ingestion…" for a very long time. Per-stage profiling on the live
local profile (Postgres + Ollama + MinIO) isolated the cause:

| Stage | Time | Notes |
|-------|------|-------|
| `extract_pages` | 18s | 714 pages |
| `chunk_pages` | 0.8s | 3040 chunks |
| `extract_figures` | 3s | 284 figures (only 1 true duplicate) |
| **embed (serial)** | **~36 min** | **0.9 chunks/s — the bottleneck** |
| caption | ~0s | local model has no vision → instant fallback |

Embedding 3040 chunks through BGE-M3 on CPU dominated. The old code issued embed
batches **strictly serially**, leaving the model idle during each request's
overhead and capping throughput at 0.9 chunks/s.

## What was built

- **`fixmate/llm/embeddings.py`** — embed batches now run with bounded concurrency
  (`_EMBED_CONCURRENCY = 4`) via a semaphore + `asyncio.gather`, which preserves
  input order. Measured throughput rose from 0.9 → **2.8 chunks/s**, the CPU
  saturation ceiling (4× concurrency and 4× batch size both plateau there).
- **`fixmate/ingestion/pipeline.py`** — figure captioning changed from a serial
  list comprehension to bounded-concurrency `asyncio.gather`
  (`_CAPTION_CONCURRENCY = 8`). Each caption is an independent vision call; this
  is the major win on the **production Anthropic path** (284 sequential vision
  round-trips would otherwise dominate). No effect on the local path, where
  captioning falls back instantly.
- **`fixmate/ingestion/pdf.py`** — `extract_figures` deduplicates by `xref`, so a
  logo/header embedded on every page is extracted (and later captioned) once
  rather than once per page. Minor for this file (1 dup), large for logo-heavy
  manuals.

## Verification evidence

Embedding throughput benchmark (real Ollama, 128 chunks from the sample file):

```
batch=32 concurrency=1: 138.1s -> 0.9 chunks/s   (old behaviour)
batch=32 concurrency=4:  45.8s -> 2.8 chunks/s   (new behaviour)
batch=64 concurrency=1:  46.4s -> 2.8 chunks/s
batch=128 concurrency=1: 45.4s -> 2.8 chunks/s   (CPU-saturation ceiling)
```

Full end-to-end ingestion of `sample-manual 02.pdf` (live Postgres/Ollama/MinIO):

```
INGEST COMPLETE: 1638.0s (27.3 min) -> 3040 chunks, 284 figures
```

(Note: this run overlapped with the integration test suite competing for the same
CPU/Ollama; the isolated embed ceiling implies ~18 min unloaded.)

Tests (real Postgres + Ollama, no mocks):

```
python -m pytest tests/ -k "embed or ingest or pdf or figure or pipeline" -q
14 passed, 114 deselected in 307.20s
```

## Remaining floor

2.8 chunks/s is the BGE-M3-on-CPU hardware limit for the 4 GB profile (spec §8.3).
Going meaningfully faster requires a GPU for embeddings, or fewer chunks (raising
`chunk_pages` `max_chars`, which trades retrieval granularity — deferred pending
product sign-off).
