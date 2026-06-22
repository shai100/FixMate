# Responsive ingestion: always-on worker + live progress bar

**Commit:** _(this commit)_ — "Run ingestion worker in Compose; add live progress (stage/percent) + progress bar"
**Date:** 2026-06-22
**Relates to:** CLAUDE.md §7.1 (ingestion <10 min SLO), spec §8.3 (local CPU profile), FR-8 (ingestion status)

## Problem

Uploads appeared "very slow" — stuck on "Queued for ingestion…" indefinitely.

**Root cause (the real one): no Celery worker was running.** `docker-compose.yml`
only started the backing services; the API and worker were expected to run as
separate host processes, and the worker simply wasn't started. So every upload was
accepted (202, queued to Redis) but **never consumed** — it sat in Celery `PENDING`
forever. Reproduced against the live API:

```
$ celery -A fixmate.ingestion.tasks inspect ping
Error: No nodes replied within time constraint

UPLOAD: {"task_id":"31715758-…","status":"queued"}
  poll 1..4: status":"pending"   (never advances — nothing is processing it)
```

**Secondary problem (responsiveness):** even with a worker, the UI showed a static
"Queued…" message polling every 2 s, because the worker reported only coarse Celery
states (`PENDING` → `SUCCESS`). There was no progress bar. The ingestion work
itself is near the hardware floor (BGE-M3 on CPU, ~2.8 chunks/s — see
`docs/2026-06-18-faster-ingestion.md`); the missing piece was *feedback*.

## What was built

### Always-on worker (the actual fix)

- **`Dockerfile`** (new) — builds the `fixmate` package and launches a Celery
  worker (Linux prefork pool; the `--pool=solo` workaround is Windows-only).
- **`docker-compose.yml`** — new `worker` service (`build: .`) depending on the
  backing services, with env pointing the shared settings at the Compose service
  hostnames, so `docker compose up` now always runs a worker.
- **Filename-only handoff** so a *containerized* worker can read a file the
  *host* API staged, without sharing absolute (Windows) paths:
  - **`fixmate/core/settings.py`** — new `upload_dir` (default repo-relative
    `.fixmate-uploads`).
  - **`fixmate/api/routers/documents.py`** — stages the PDF under `upload_dir`
    and enqueues only the **filename**.
  - **`fixmate/ingestion/tasks.py`** — `_resolve_pdf_path` re-resolves that
    filename against the worker's own `upload_dir` (separator-agnostic basename).
  - The Compose worker bind-mounts `./.fixmate-uploads:/uploads` and sets
    `UPLOAD_DIR=/uploads`, so host and container see the same bytes.
- **`.dockerignore`**, **`.gitignore`** (`.fixmate-uploads/`) added.

### Live progress bar

- **`fixmate/llm/embeddings.py`** — `embed()` gained an optional
  `on_progress(done, total)` callback fired as each batch completes (counted, not
  assumed-in-order, since batches run concurrently). Embedding is the slowest
  phase, so this drives the widest part of the bar.
- **`fixmate/ingestion/pipeline.py`** — `ingest_document`/`ingest_document_sync`
  take a `progress(stage, percent)` callback. A fixed percent budget maps the
  pipeline to overall progress (read PDF → extract 8% → embed 10–70% → caption
  70–88% → store → 100%), so percent is monotonic regardless of file shape.
- **`fixmate/ingestion/tasks.py`** — the Celery task is now `bind=True` and
  publishes a custom `PROGRESS` state with `{stage, percent}` meta via
  `self.update_state`.
- **`fixmate/api/routers/documents.py` + `schemas.py`** — `document_status`
  reads the `PROGRESS` meta and returns `status="processing"` with `stage` and
  `percent`; `DocumentStatus` gained those two optional fields.
- **`web/.../DocumentsAdmin.tsx` + `types.ts` + `styles.css`** — the status line
  is replaced by a real `<progress>` bar showing the stage label and percent
  (indeterminate bar when percent is unknown). Poll interval dropped 2000 → 750 ms
  (attempt cap raised to keep the same ~10 min coverage) so the bar feels live.

## Verification evidence

**Full UI flow, end to end** — `docker compose up -d worker` (Compose worker
running), then upload `sample-manual 04.pdf` through the live host API exactly as
the web UI does, and poll status:

```
$ docker compose logs worker
worker-1 | celery@… v5.6.3 … transport: redis://redis:6379/0 … concurrency: 16 (prefork)
worker-1 | celery@… ready.

UPLOAD: {"task_id":"c5cb69b2-…","status":"queued"}
staged in .fixmate-uploads: 4fd59bc3-…-sample-manual 04.pdf
  poll 1: status":"processing" … "percent":8,  "stage":"Extracted text and figures"
  poll 3: status":"ingested"   … "percent":100, "document_id":"5950c8ea-…"
>>> DONE   (~4.5 s)
```

(Before the fix, the same upload stayed `"pending"` on every poll — nothing
consumed it.)

**Direct pipeline run** of `sample-manual 04.pdf` (live Postgres/Ollama/MinIO),
capturing every progress callback to confirm percent is monotonic 0→100:

```
  [   0.0s]   2%  Reading PDF
  [  0.03s]   8%  Extracted text and figures
  [  3.77s]  70%  Embedding chunks (6/6)
  [  3.77s]  88%  Saving to index
  [  5.01s] 100%  Ingestion complete
monotonic OK, events: 6
```

Backend tests (real Postgres + Ollama, no mocks):

```
python -m pytest tests/ -k "embed or task or pipeline or documents" -q
17 passed, 111 deselected in 13.76s
```

Frontend type-check and lint:

```
npx tsc --noEmit            -> TSC OK
npx eslint DocumentsAdmin.tsx types.ts -> clean
```
