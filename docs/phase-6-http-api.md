# Phase 6 — HTTP API + dev auth + conversations

**Commit:** _(this commit)_ — `feat: HTTP API — dev auth + conversations + ask + equipment + documents (phase 6)`
**Plan:** `docs/superpowers/plans/2026-06-12-fixmate-mvp.md` §Phase 6 (tasks 6.1–6.3)
**Architecture rules:** CLAUDE.md §6 (tenant isolation — org id from auth, never query params),
§4.2 (boundary validation), §4.5 (RLS via `session_for_org`); Appendix A.6 (`AuthContext`)
**Date:** 2026-06-15

---

## What was built

`fixmate/api/` — the FastAPI surface that exposes Phase 4/5 retrieval+answer machinery and
the conversation store over HTTP, gated by a pluggable auth dependency.

- **`deps.py`** — `AuthContext(org_id, user_id, role)` (Appendix A.6) and
  `get_current_user`. With `DEV_AUTH=true` it reads `X-Org-Id` / `X-User-Id` / `X-Role`
  headers (validates UUIDs + role ∈ {tech,curator,admin}, else 401); with `DEV_AUTH=false`
  it raises 501 (Phase 9 wires the OIDC validator into the same dataclass). `require_role(*)`
  is the role-guard factory Phase 8 will use for curator/admin actions. **Org id always comes
  from the authenticated identity, never from a query param** (CLAUDE.md §6).
- **`main.py`** — app assembly + `_guard_auth_config()`: the API **refuses to boot** when
  `DEV_AUTH=true` and `ENV != local`, so spoofable header auth can never reach a real
  deployment (task 6.1). `GET /health` for liveness.
- **`schemas.py`** — Pydantic request/response contracts (conversations, ask answer payload
  with citations carrying document title + page, equipment, document upload/status).
- **`routers/conversations.py`** — `POST /conversations` (create, 201) and
  `GET /conversations/{id}` (fetch with ordered messages). A cross-tenant fetch 404s because
  RLS makes the other org's row invisible — the API-level proof of CLAUDE.md §6.
- **`routers/ask.py`** — `POST /conversations/{id}/ask`: stores the user message, loads prior
  turns as history (FR-5 multi-turn), calls `compose_answer(..., conversation_id=...)`, stores
  the assistant message linked to its `answer_log_id`, and returns the answer payload (text,
  confidence, citations enriched with document title + page, figure URLs, escalated,
  message_id).
- **`routers/equipment.py`** — `POST /equipment` / `GET /equipment` (FR-10), tenant-scoped.
- **`routers/documents.py`** — `POST /documents/upload` (multipart): validates PDF at the
  boundary (CLAUDE.md §4.2), writes the bytes to a temp path, enqueues
  `ingest_document_task.delay(...)`, returns 202 + Celery `task_id`. `GET /documents/{task_id}`
  reports ingestion status from the Celery result (`ingested` + the new document id on
  success) (FR-8).

Supporting change: `core/settings.py` gains `env: str = "local"` (drives the boot guard);
`.env.example` documents `ENV`.

### Design decisions

- **Auth is a single dependency, two backends.** Handlers depend only on `AuthContext`; the
  dev-header reader (now) and the Keycloak OIDC validator (Phase 9) produce the same dataclass,
  so no handler changes when auth is swapped — Appendix A.6.
- **Document id surfaces via the Celery result, not at enqueue.** The ingestion pipeline mints
  the document id internally (with version/supersede logic). Rather than fork that, the upload
  returns the task id and `GET /documents/{task_id}` exposes the document id once ingestion
  succeeds. This needs no schema change and reports real status (PENDING until a worker runs).
- **Upload handoff is a temp file.** API and worker share the host in the local profile; the
  pipeline re-uploads the original PDF to MinIO under the tenant prefix, so the temp file is
  only the enqueue handoff.
- **Phase 6 tests assert the API contract, not the LLM's verdict.** The ask integration test
  checks the answer round-trips and both messages persist in order with the assistant linked
  to its answer log; it does **not** assert grounded-vs-escalated, because that decision is the
  LLM's and on the qwen3:4b dev backend is non-deterministic (over-refusal is a documented
  small-model artifact, see Phase 5). Grounding/abstention is owned and tested in Phase 5;
  production runs on Claude (spec §8.3).

## Verification evidence

Compose services up (postgres healthy; redis; ollama with qwen3:4b + bge-m3).

### Lint + format
```
$ ruff check fixmate/api tests/api
All checks passed!
$ ruff format --check fixmate/api tests/api
16 files already formatted
```

### Fast API tests (`pytest tests/api -m "not integration" -v`)
```
tests/api/test_auth.py::test_missing_headers_rejected PASSED
tests/api/test_auth.py::test_bad_role_rejected PASSED
tests/api/test_auth.py::test_non_uuid_org_rejected PASSED
tests/api/test_auth.py::test_health_ok PASSED
tests/api/test_auth.py::test_production_dev_auth_is_refused PASSED
tests/api/test_auth.py::test_auth_context_shape PASSED
tests/api/test_conversations.py::test_create_and_get_conversation PASSED
tests/api/test_conversations.py::test_get_missing_conversation_404 PASSED
tests/api/test_conversations.py::test_cross_tenant_conversation_is_404 PASSED
tests/api/test_equipment.py::test_create_and_list_equipment PASSED
tests/api/test_equipment.py::test_equipment_is_tenant_scoped PASSED
====================== 11 passed, 5 deselected in 3.35s =======================
```

### Documents integration (`pytest tests/api/test_documents.py -v`)
```
tests/api/test_documents.py::test_upload_enqueues_and_status_reports PASSED
tests/api/test_documents.py::test_upload_rejects_non_pdf PASSED
tests/api/test_documents.py::test_upload_rejects_bad_equipment_id PASSED
============================== 3 passed in 1.91s ==============================
```

### Ask integration — full RAG through the API (`pytest tests/api/test_ask.py -v`)
```
tests/api/test_ask.py::test_ask_returns_grounded_answer_and_persists_messages PASSED
tests/api/test_ask.py::test_ask_unknown_conversation_404 PASSED
======================== 2 passed in 309.15s (0:05:09) ========================
```

### No regressions — full non-integration suite (`pytest -m "not integration" -q`)
```
.....................................                                     [100%]
37 passed, 18 deselected in 9.12s
```

### Standalone (`uvicorn fixmate.api.main:app --port 8000`)
```
$ curl -s localhost:8000/health
{"status":"ok","env":"local"}

$ curl -s -X POST localhost:8000/conversations -H "X-Org-Id: $ORG" -H "X-User-Id: $USER" -H "X-Role: tech" -d '{}'
{"id":"c44ae71e-...","equipment_id":null,"created_at":"2026-06-15T13:56:07Z","messages":[]}

$ curl -s localhost:8000/conversations/c44ae71e-... -H "X-Org-Id: $ORG" -H "X-User-Id: $USER" -H "X-Role: tech"
{"id":"c44ae71e-...","equipment_id":null,"created_at":"...","messages":[]}

$ curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/conversations -d '{}'   # no auth headers
401

$ curl -s -X POST localhost:8000/equipment -H "X-Org-Id: $ORG" -H "X-User-Id: $USER" -H "X-Role: tech" -d '{"name":"Pump X","manufacturer":"Acme"}'
{"id":"5458a5a5-...","name":"Pump X","manufacturer":"Acme","model":null,"created_at":"..."}
```
Endpoints respond, dev-auth headers gate access, and a request with no headers is rejected 401.
```
