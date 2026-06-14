# Phase 3 — Ingestion pipeline

**Commit:** `feat: PDF ingestion pipeline — parse, chunk, embed, caption, store (phase 3)`
**Plan:** [`docs/superpowers/plans/2026-06-12-fixmate-mvp.md`](superpowers/plans/2026-06-12-fixmate-mvp.md) § "Phase 3 — Ingestion pipeline"
**Spec:** §3.2 (knowledge ingestion), §2.3 (image-aware ingestion), §6 (tenant isolation), §8.3 (local profile)
**Date:** 2026-06-14

---

## What was built

The ingestion pipeline turns a tenant's PDF manual into retrievable rows: text chunks with
1024-dim embeddings, plus captioned + stored figures. Built test-first (TDD per CLAUDE.md §4.3).

| File | Purpose / design decisions |
|------|----------------------------|
| `fixmate/ingestion/chunking.py` | `chunk_pages(pages, max_chars=800, overlap=120)` → `TextChunk(page, text)`. Sentence-boundary split assembled to a **char budget** (~800 ≈ <512 tokens) as a cheap proxy for the reranker-stability constraint (CLAUDE.md §4.4), avoiding a tokenizer in the hot path. Overlap carries cross-chunk context (a torque spec split across a seam stays retrievable). Hard-splits any single over-budget sentence. |
| `fixmate/ingestion/pdf.py` | `extract_pages` (1-based `(page, text)`) and `extract_figures` → `ExtractedFigure(page, bbox, image, media_type)` via PyMuPDF. CMYK/alpha pixmaps normalized to RGB before PNG encoding (`tobytes` rejects >4-channel colorspaces). bbox from `get_image_rects`. |
| `fixmate/core/storage.py` | boto3 MinIO helper. **Every key prefixed `org_id/`** (CLAUDE.md §6) — tenant isolation at the object layer mirrors Postgres RLS. `put_object` / `object_exists` / idempotent `ensure_bucket`. |
| `fixmate/ingestion/figures.py` | `caption_and_store(provider, figure, org_id, document_id, context)`. Captions via the configured LLM provider; **on `NotImplementedError` (local `ollama`/qwen3:4b has no vision, spec §8.3) falls back to a deterministic non-empty caption** so the figure stays indexable. Uploads bytes, returns the row dict. |
| `fixmate/ingestion/registry.py` | `get_or_create_org` (owner connection — org creation is a bootstrap op outside any tenant context, mirroring `tests/conftest.py`), `get_or_create_equipment`, `latest_document`. |
| `fixmate/ingestion/pipeline.py` | `ingest_document(org_id, equipment_id, pdf_path, title=None, provider=None)` async core: parse → chunk → embed (batched) → create `documents` row → `chunks` (`source_type='manual'`) → captioned `figures`. Document identity is `(equipment_id, title)`: re-ingest bumps `version` and sets `superseded_by` on the prior row (FR-9). `ingest_document_sync` wraps it in `asyncio.run` for the Celery worker. |
| `fixmate/ingestion/tasks.py` | Celery app (`redis_url` broker + backend). `ingest_document_task` returns a `str` UUID (result backend needs JSON-serializable). |
| `fixmate/ingestion/cli.py` | `python -m fixmate.ingestion.cli <pdf> --org <name> --equipment <name> [--async]`. Creates org/equipment if missing (dev convenience); prints chunk/figure counts, or enqueues + prints task id with `--async`. |
| `tests/ingestion/conftest.py` | Session-scoped `sample_pdf` fixture (3 pages, "Error E47: concentrate valve blocked", "Tighten to 12 Nm", one embedded image on p.2) generated with PyMuPDF. |
| `tests/fixtures/sample-manual.pdf` | Committed copy of the same fixture for standalone CLI runs. |

---

## Verification evidence

### Unit + integration tests (TDD: each test watched fail before implementation)

```
$ python -m pytest tests/ingestion -q
.......                                                                  [100%]
7 passed in 11.66s
```

Covers: chunk size/page/overlap; PDF text + single-figure-with-bbox extraction; end-to-end
ingest (documents v1, ≥1 chunks with 1024-dim embeddings + `source_type='manual'`, 1 figure
with non-empty caption whose `storage_key` exists in MinIO); re-ingest → version 2 +
`superseded_by` on v1; Celery task registration + execution through to a persisted document.

### Full suite — no regressions

```
$ python -m pytest -q
.....................                                                    [100%]
21 passed in 54.29s
```

### Lint

```
$ python -m ruff check fixmate/ingestion fixmate/core/storage.py tests/ingestion
All checks passed!
```

### Standalone CLI + DB check (plan §3.5 / §3 "Run it standalone")

```
$ python -m fixmate.ingestion.cli tests/fixtures/sample-manual.pdf --org demo --equipment "Pump X"
ingested document 5ecd12cc-5a0c-4982-a9a8-d9f8fd636d95: 3 chunks, 1 figures

$ docker compose exec postgres psql -U fixmate -c "select count(*), source_type from chunks group by source_type;"
 count | source_type
-------+-------------
     3 | manual
(1 row)
```

### Celery worker — real broker (plan §3.4)

```
$ celery -A fixmate.ingestion.tasks worker -l info --pool=solo
  . fixmate.ingestion.ingest_document
[...] Connected to redis://localhost:6379/0
[...] celery@Shai ready.

$ python -m fixmate.ingestion.cli tests/fixtures/sample-manual.pdf --org demo --equipment "Pump X" --async
enqueued task 4aab21e7-... (org=demo, equipment=Pump X)

# worker log:
[...] Task fixmate.ingestion.ingest_document[4aab21e7-...] received
[...] Task fixmate.ingestion.ingest_document[4aab21e7-...] succeeded in 4.19s: '2a97dfee-...'
```

`setup-instructions.md` updated (CLAUDE.md §4.8): Phase 3 header, `pytest tests/ingestion`,
ingestion CLI standalone check, and the `--pool=solo` Celery worker section.
