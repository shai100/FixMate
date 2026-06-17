# Documents page: working uploads, live ingestion status, and manual download

**Date:** 2026-06-17
**Scope:** Admin Documents screen (FR-8/9) — `web/src/components/DocumentsAdmin.tsx`,
`web/src/api.ts`, `web/src/types.ts`, `fixmate/api/routers/documents.py`,
`fixmate/core/storage.py`, `tests/api/test_documents.py`.

## What was built

Three reported problems on the Documents page were fixed:

1. **Uploads appeared to do nothing.** The component bumped its `revision` reload
   counter *immediately* after the upload request returned `202`. But the
   `Document` row is created by the background Celery worker, not by the HTTP
   request — so the list reloaded before the row existed and the new manual never
   showed up. Fix: the screen now polls the ingestion task and only refreshes the
   list once the task reports `ingested`.

2. **No progress or error feedback.** The upload now polls
   `GET /documents/{task_id}` every 2s (cap ~5 min, matching the 500-page <10min
   SLO) and shows live status — *queued → processing → complete* — via a
   `role="status"` live region, and surfaces an explicit `role="alert"` error if
   the task state is `failure` (or if the upload request itself errors).

3. **No way to download an uploaded manual.** Added a tenant-scoped download:
   - `storage.get_object(key)` reads object bytes from MinIO/S3.
   - `GET /documents/{document_id}/download` looks the manual up by id under
     `session_for_org` (so a caller can only fetch their own org's file), streams
     the PDF with `Content-Disposition: attachment`, and returns 404 if the row or
     stored object is missing.
   - The client (`api.downloadDocument`) fetches the PDF as a Blob with auth
     headers (a plain `<a href>` can't carry them) and triggers a save via a
     temporary object URL. Each `DocRow` gained a **Download** button.

Route ordering note: `GET /documents/{document_id}/download` (two path segments)
does not collide with the existing `GET /documents/{task_id}` (one segment).

## Verification evidence

TypeScript typecheck (web):

```
$ cd web && npx tsc --noEmit
(no output — clean)
```

Backend syntax check:

```
$ python -c "import ast; ast.parse(open('fixmate/api/routers/documents.py').read()); ast.parse(open('fixmate/core/storage.py').read()); print('py syntax ok')"
py syntax ok
```

Added integration tests in `tests/api/test_documents.py`:
`test_download_document_returns_pdf` (puts an object, downloads it, asserts bytes +
headers) and `test_download_missing_document_404`. These run against the real
MinIO + Postgres compose stack (`pytest -m integration`).
