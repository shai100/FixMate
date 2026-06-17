# Documents upload fixes — CMYK/Separation figures, embed batching, polling errors

**Date:** 2026-06-17
**Scope:** Documents admin upload flow (FR-8). Frontend + ingestion pipeline.
**Plan/spec links:** CLAUDE.md §2.3 (image-aware ingestion), §4.2 (boundary error
handling), §7.1 (ingestion SLO <10min/500 pages).

## Problem

Uploading `tests/fixtures/sample-manual 02.pdf` from the Documents page reproduced
three reported symptoms:

1. **Upload doesn't work well** — ingestion crashed, so the manual never appeared.
2. **No error on a failed upload** — the status display froze with no message.
3. **After upload it doesn't stay on the page** — a downstream symptom of (1): the
   upload appeared to do nothing and no document showed up.

## Root causes & fixes

### 1. Figure extraction crashed on print colorspaces — `fixmate/ingestion/pdf.py`
`extract_figures` only converted ≥4-channel images (DeviceCMYK) to RGB before PNG
encoding. The manual also contains single-channel **Separation/spot-color** images
(`n == 1`), which PNG cannot encode either, so `tobytes("png")` raised
`FzErrorArgument: pixmap must be grayscale or rgb to write as png`. The channel-count
heuristic missed them.

**Fix:** key on the colorspace name — convert anything that isn't already
`DeviceGray`/`DeviceRGB` to RGB.

### 2. Embedding a large manual timed out — `fixmate/llm/embeddings.py`
`embed()` sent every chunk of the manual in a single Ollama `/api/embed` request.
A 300+ page manual (~3000 chunks) exceeded the 120s client timeout → `httpx.ReadTimeout`,
failing the whole ingestion task.

**Fix:** embed in bounded sub-batches of 32 and concatenate in order; each request
stays well inside the timeout. Empty input short-circuits to `[]`.

### 3. Status-poll errors were swallowed — `web/src/components/DocumentsAdmin.tsx`
`pollIngestion` was invoked as `void pollIngestion(...)`, so any error thrown by the
status request became an unhandled promise rejection — the technician saw the status
frozen with no explanation.

**Fix:** wrap the poll loop in try/catch and surface a clear error message.

> Issue (3) "doesn't stay on the page" required no code change: the upload form already
> calls `e.preventDefault()` and the console tabs are state-driven (no remount). With the
> ingestion fixes, the `revision` bump fires on `ingested` and the new manual appears in
> the list while the Documents tab stays active.

## Verification evidence

### Figure colorspace normalization (all 284 images encode)
```
$ python - <<'PY'  # normalize-then-encode every embedded image in the fixture
... OK 284 FAIL 0
PY
```

### Unit / regression tests
```
$ pytest tests/ingestion/test_pdf.py -q
...                                                                      [100%]
3 passed in 1.22s

$ pytest tests/llm/test_embeddings.py -q
..                                                                       [100%]
2 passed in 0.20s

$ pytest tests/ -k "embed or pdf or figure or ingest" -q
...........                                                              [100%]
11 passed, 114 deselected in 86.35s
```
(`tests/llm/test_embeddings.py` asserts a 70-text call splits into 32/32/6 requests.)

### End-to-end upload of `sample-manual 02.pdf`
Started a Celery worker, uploaded via the API, polled to completion:
```
UPLOAD: {"task_id":"1acd8aeb-...","status":"queued"}
FINAL:  {"task_id":"1acd8aeb-...","status":"ingested",
         "document_id":"3f3b6b31-e860-4268-8a83-b77c434c92f2"}
```
Document is live and fully indexed:
```
=== Documents list ===
Sample Manual 02 v1 live
Pump X Service Manual v1 live
=== row counts for the new document ===
chunks  3040
figures 285
```
Before the fix the same upload raised `FzErrorArgument` (figures) and, once that was
fixed, `httpx.ReadTimeout` (embeddings); both now pass.

### Frontend typecheck
```
$ npx tsc --noEmit   # in web/
TSC EXIT 0
```

## Notes
- Ingestion requires a running Celery worker (`celery -A fixmate.ingestion.tasks worker
  -l info --pool=solo`, see `setup-instructions.md`). With no worker, uploads sit at
  "Queued…" indefinitely — a deployment prerequisite, not a code bug.
