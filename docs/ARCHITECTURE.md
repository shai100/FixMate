# FixMate — Architecture & Developer Guide

**Audience:** Any engineer joining the project. After reading this you should understand what
each component does, how the codebase is laid out, and how a request flows end-to-end.

**Companion docs:**
- Product/why decisions: [`../CLAUDE.md`](../CLAUDE.md) (architectural principles) and
  [`fixmate-product-spec.md`](fixmate-product-spec.md).
- Running it locally: [`../setup-instructions.md`](../setup-instructions.md) and
  [`how_to_run.md`](how_to_run.md).
- Per-phase build logs: `docs/phase-*.md`.

> **Maintenance rule:** This document is kept current. Whenever a change alters the components,
> their responsibilities, the data model, or how they interact, update this file in the same
> commit (see [`../CLAUDE.md`](../CLAUDE.md) §4.9).

---

## 1. What FixMate Is

An AI troubleshooting assistant for field technicians. A technician asks a question about a
piece of equipment; FixMate answers using **RAG** (Retrieval-Augmented Generation) grounded
strictly in that tenant's uploaded manuals **and** human-approved field fixes, with citations.
Low-confidence or ungrounded answers escalate to a human instead of guessing. Every answer and
every fix state change is logged immutably.

Three non-negotiable properties shape every component:
- **Groundedness** — answers must trace to retrieved sources, or they escalate.
- **Tenant isolation** — one org's data is never visible to another (enforced in Postgres RLS).
- **Auditability** — answers and fix lifecycle changes are logged for 24 months.

---

## 2. System at a Glance

```
                          ┌────────────────────────────────────────────┐
                          │              Web client (React)             │
                          │  Technician PWA  │  Curator/Admin Console   │
                          └───────────────┬──────────────┬──────────────┘
                                          │ HTTP (JSON)   │
                                          ▼               ▼
                          ┌────────────────────────────────────────────┐
                          │           FastAPI app (fixmate.api)         │
                          │  routers → auth (deps) → service packages   │
                          └───┬───────────┬───────────┬───────────┬─────┘
                              │           │           │           │
              ┌───────────────┘   ┌───────┘    ┌──────┘     ┌──────┘
              ▼                   ▼            ▼            ▼
        ┌───────────┐      ┌────────────┐ ┌──────────┐ ┌───────────┐
        │ retrieval │      │  answers   │ │ curation │ │ feedback  │
        │ (hybrid)  │◀─────│ (RAG flow) │ │(lifecycle│ │           │
        └─────┬─────┘      └─────┬──────┘ │ + index) │ └─────┬─────┘
              │                  │        └────┬─────┘       │
              │                  ▼             │             │
              │            ┌──────────┐        │             │
              │            │   llm    │◀───────┘             │
              │            │ provider │  (also used by       │
              │            │ (factory)│   ingestion)         │
              │            └────┬─────┘                      │
              ▼                 ▼                            ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │   core: db (RLS session)  ·  models (SQLAlchemy)  ·  storage (S3)  │
   └───────┬─────────────────────────┬───────────────────────┬─────────┘
           ▼                         ▼                        ▼
   ┌──────────────┐         ┌─────────────────┐       ┌──────────────┐
   │  PostgreSQL  │         │  Ollama / Claude │       │  MinIO / S3  │
   │  + pgvector  │         │   (LLM + embeds) │       │   (objects)  │
   │  + FTS + RLS │         └─────────────────┘        └──────────────┘
   └──────────────┘
           ▲
           │  (async)
   ┌──────────────┐    broker     ┌──────────────┐
   │  Celery      │◀──────────────│    Redis     │
   │  workers     │               └──────────────┘
   │ (ingestion)  │
   └──────────────┘
```

Authentication is OIDC via **Keycloak** in real deployments; a header-based dev-auth shortcut
is used locally (see §6).

---

## 3. Technology Stack

| Layer | Technology | Where |
|-------|-----------|-------|
| API | Python 3.12, FastAPI, async SQLAlchemy 2 | `fixmate/api`, `fixmate/core` |
| Async workers | Celery (Redis broker), runs as the `worker` Compose service | `fixmate/ingestion/tasks.py`, `Dockerfile` |
| RDBMS | PostgreSQL 16 + Row-Level Security | `db/migrations`, `fixmate/core` |
| Vector search | pgvector (1024-dim, BGE-M3) | `fixmate/retrieval/vector.py` |
| Keyword search | PostgreSQL full-text search (tsvector) | `fixmate/retrieval/keyword.py` |
| Object storage | MinIO locally → S3 in cloud (boto3) | `fixmate/core/storage.py` |
| PDF/OCR | PyMuPDF; Claude vision for figure captions | `fixmate/ingestion` |
| LLM | Ollama (local: qwen3:4b + bge-m3) or Anthropic Claude | `fixmate/llm` |
| Auth | Keycloak OIDC (prod) / dev headers (local) | `fixmate/api/deps.py`, `auth_oidc.py` |
| Web client | React + Vite + TypeScript | `web/` |
| Local infra | Docker Compose | `docker-compose.yml` |

Dependencies are declared in [`../pyproject.toml`](../pyproject.toml); web deps in
[`../web/package.json`](../web/package.json).

---

## 4. Repository Layout

```
fixmate/                 Python backend (the modular monolith)
├── api/                 FastAPI app: HTTP boundary, routing, auth
│   ├── main.py          App assembly: includes all routers, /health, auth guard
│   ├── deps.py          AuthContext + get_current_user (dev headers / OIDC), require_role
│   ├── auth_oidc.py     Keycloak JWT validation (used when DEV_AUTH=false)
│   ├── schemas.py       Pydantic request/response models (the API contract)
│   └── routers/         One module per resource (see §5.1)
├── core/                Cross-cutting infrastructure
│   ├── settings.py      Pydantic-settings config (env vars / .env)
│   ├── db.py            Async engine + session_for_org() — the ONLY DB entry point
│   ├── models.py        SQLAlchemy ORM models (the data model, §7)
│   └── storage.py       S3/MinIO object storage (presigned URLs, per-org prefixes)
├── llm/                 LLM provider abstraction
│   ├── base.py          LLMProvider protocol + CompletionRequest/Response
│   ├── factory.py       get_provider() — selects ollama vs anthropic
│   ├── ollama_provider.py / anthropic_provider.py
│   └── embeddings.py    embed() — text → 1024-dim vectors
├── ingestion/           PDF → chunks + figures → embeddings → DB (async/Celery)
│   ├── pdf.py           PyMuPDF text + figure extraction
│   ├── chunking.py      Page text → bounded chunks
│   ├── figures.py       Vision-caption figures, store images
│   ├── pipeline.py      ingest_document() orchestrator (+ sync entry for Celery)
│   ├── tasks.py         Celery task wrapping the pipeline
│   └── registry.py      Document versioning (supersede prior version)
├── retrieval/           Hybrid search: BM25/FTS + vector → fuse → boost → rerank
│   ├── vector.py        pgvector similarity search
│   ├── keyword.py       Postgres full-text search
│   ├── fusion.py        Reciprocal-rank fusion + approved-fix boost
│   ├── rerank.py        Reranking of fused candidates
│   └── service.py       search() — orchestrates the whole pipeline → ScoredChunk[]
├── answers/             RAG answer composition + safety gating
│   ├── composer.py      compose_answer() — search → gate → LLM → validate → log
│   ├── confidence.py    Score → confidence band (low gates to escalation)
│   ├── groundedness.py  Verify claims trace to retrieved chunks
│   ├── prompts.py       System/user prompts, citation + abstention conventions
│   └── answer_log.py    Immutable answer logging
├── curation/            Approved-fix lifecycle (the moat)
│   ├── states.py        Fix state machine (legal transitions)
│   ├── prescreen.py     AI safety advisory for curators
│   └── service.py       submit/approve/reject/retire + field_fix indexing
├── feedback/            "Did it help?" + fix submission entry point
└── evals/               Safety + answer-regression test harness

db/migrations/           Alembic migrations (schema + RLS policies)
scripts/                 healthcheck.py, seed_demo.py, keycloak_bootstrap.py
web/                     React client (technician PWA + curator/admin console)
tests/                   Pytest suites, mirroring the package layout
docs/                    This file, product spec, per-phase build logs
```

---

## 5. Component Responsibilities & Interactions

### 5.1 API layer (`fixmate/api`)

The HTTP boundary. [`main.py`](../fixmate/api/main.py) assembles the app and includes one router
per resource:

| Router | Responsibility |
|--------|----------------|
| `conversations` | Create conversations, list messages |
| `ask` | `POST /conversations/{id}/ask` — the core Q&A endpoint |
| `equipment` | Equipment profiles CRUD |
| `documents` | Upload manuals → kicks off ingestion; poll ingestion status (`GET /documents/{task_id}`, returns live `stage`/`percent` while the worker runs); stream the original PDF back (`GET /documents/{document_id}/download`) |
| `feedback` | "Did it help?" + technician fix submission |
| `curation` | Review queue + fix lifecycle actions (curator/admin) |
| `admin` | User management |
| `dev` | Local-only helpers (auto-login) |

**Auth flow (every protected endpoint):** handlers depend on `get_current_user`
([`deps.py`](../fixmate/api/deps.py)), which returns an `AuthContext(org_id, user_id, role)`.
The `org_id` always comes from the authenticated identity, **never** from a query parameter.
`require_role("curator", "admin")` guards privileged endpoints. Handlers then call into the
service packages, never touching the DB except through `session_for_org(auth.org_id)`.

The request/response shapes are defined in [`schemas.py`](../fixmate/api/schemas.py) — that file
is the API contract the web client codes against.

### 5.2 `core` — infrastructure shared by everything

- **`db.py` → `session_for_org(org_id)`** is *the only way application code touches the
  database*. On every transaction it runs `SET LOCAL app.current_org_id = <org>`, which is what
  Postgres RLS policies key off. `SET LOCAL` reverts at transaction end, so a tenant's context
  can never leak into another request. The engine uses `NullPool` (asyncpg connections are bound
  to their creating event loop).
- **`models.py`** defines the ORM tables (§7). `EMBEDDING_DIM = 1024` and the `FIX_STATES` tuple
  are contracts shared with the embeddings layer and the fix state machine.
- **`storage.py`** wraps S3/MinIO. Object keys are prefixed with `org_id/` for isolation;
  figures are served to clients via presigned URLs.
- **`settings.py`** is the single config surface (Pydantic-settings, reads `.env`). Notable
  switches: `LLM_PROVIDER` (`ollama`/`anthropic`), `DEV_AUTH`, `ENV`.

### 5.3 `llm` — provider abstraction

`get_provider()` ([`factory.py`](../fixmate/llm/factory.py)) returns an `LLMProvider`
(`OllamaProvider` or `AnthropicProvider`) based on `settings.llm_provider`. All callers
(`answers`, `ingestion`, `curation`) depend on the `LLMProvider` protocol in `base.py`, not on a
concrete backend — so the local model and Claude are interchangeable. `embeddings.embed()`
turns text into 1024-dim vectors (BGE-M3) used by both ingestion and retrieval.

### 5.4 `ingestion` — getting manuals into the index (async)

Triggered when a document is uploaded; runs in a **Celery worker** (not in the request).
[`pipeline.py`](../fixmate/ingestion/pipeline.py) `ingest_document()`:

1. Read the PDF; `pdf.extract_pages()` + `chunking.chunk_pages()` → bounded text chunks.
2. `pdf.extract_figures()` → `figures.caption_and_store()` (Claude vision captions, image to S3).
3. `embeddings.embed()` → a vector per chunk.
4. `registry.latest_document()` decides the version; re-ingesting the same title supersedes the
   prior version (FR-9 versioning).
5. Persist `Document`, `Chunk` (`source_type='manual'`), and `Figure` rows in one transaction.

The Celery wrapper is [`tasks.py`](../fixmate/ingestion/tasks.py); it calls the sync entry point
which runs the async pipeline in its own event loop. The task is `bind=True` and publishes a
`PROGRESS` state (`{stage, percent}`) as the pipeline advances, which `GET /documents/{task_id}`
relays so the upload UI can render a live progress bar.

The worker runs as the **`worker` service in `docker-compose.yml`** (built from the repo
`Dockerfile`), so uploads are always processed — a missing worker previously left them stuck on
"Queued for ingestion…". Handoff is by *filename*, not absolute path: the API stages the PDF to
`settings.upload_dir` (`.fixmate-uploads`, bind-mounted to `/uploads` in the worker container) and
enqueues only the filename, which the worker re-resolves against its own `upload_dir`. This keeps
the host API (Windows paths) and the Linux worker container sharing one directory without passing
host-absolute paths across the OS boundary.

### 5.5 `retrieval` — hybrid search

[`service.py`](../fixmate/retrieval/service.py) `search(org_id, equipment_id, query, top_k)`:

1. Embed the query.
2. Run **vector search** (pgvector) and **keyword search** (Postgres FTS) in parallel within one
   tenant-scoped session.
3. **Reciprocal-rank fusion** merges the two ranked lists (`fusion.py`).
4. Rerank the top `CANDIDATE_POOL` (=20) candidates (`rerank.py`).
5. **Approved-fix boost** is applied to the *rerank* scores, so an approved `field_fix` chunk
   outranks comparably-relevant manual content — this is the moat, provable by the curation
   moat test.
6. Return the top `top_k` as `ScoredChunk` objects (id, source_type, page, text, score, fix_id).

### 5.6 `answers` — the RAG pipeline + safety gate

[`composer.py`](../fixmate/answers/composer.py) `compose_answer()` is the heart of the product:

1. `search()` for context; `confidence.confidence_band()` maps the top score to a band.
2. **Low confidence → escalate immediately** (no LLM call), log, return.
3. Otherwise build prompts (`prompts.py`), attach approved-fix badges (approver + date), and call
   the LLM provider.
4. Validate the result: every citation token `[chunk:<id>]` must resolve to a retrieved chunk,
   and `groundedness.check_groundedness()` must pass. If the model emits the abstention sentinel,
   escalate. If validation fails, **retry once** with the problems fed back; if it still fails,
   escalate.
5. Write an immutable `AnswerLog` (question, retrieved chunk ids, model/provider, confidence,
   citations, groundedness, tokens) and return an `Answer`.

This enforces CLAUDE.md's "groundedness over capability": an uncited or ungrounded answer is
never shown to a technician.

### 5.7 `curation` — the approved-fix moat

[`service.py`](../fixmate/curation/service.py) owns the fix lifecycle. The legal transitions live
in [`states.py`](../fixmate/curation/states.py):

```
submitted → pending_review → approved → retired
                           ├→ rejected
                           └→ unsafe
              approved → pending_review   (aging re-confirmation, FR-19)
```

- `review_queue()` gives curators everything to decide: original Q&A, proposed text, top manual
  chunks for context, and a **lazily-computed AI pre-screen** (`prescreen.py`) persisted to the
  fix so it runs once.
- **`approve()`** embeds the approved text into `chunks` as `source_type='field_fix'`
  (`_index_fix_text`) — *this is what makes a fix retrievable and able to outrank manual content*.
- **`retire()` / `delete()`** remove the `field_fix` chunks in the same transaction, so a retired
  fix vanishes from retrieval immediately. **The index is the single source of truth.**
- Every action writes an `AuditEvent` (actor, before/after) — the legal-defensibility trail.
- Humans approve; nothing is auto-served (CLAUDE.md §2.5).

### 5.8 `feedback`

Records whether an answer helped (incrementing `positive_signals` on cited chunks as a future
ranking signal) and is the entry point for technicians submitting a candidate fix, which lands in
`pending_review` for curation.

### 5.9 Web client (`web/`)

React + Vite. [`App.tsx`](../web/src/App.tsx) routes by role from the authenticated identity:
technicians get the phone-framed PWA (equipment picker → chat → feedback/fix submission); curators
and admins get the desktop **Console** (review queue, fixes, documents, equipment, users). All
calls go through `api.ts`; identity/auth is in `auth.ts`.

---

## 6. Authentication & Tenant Isolation

Two interacting mechanisms:

1. **Identity** (`api/deps.py`): in real deployments `DEV_AUTH=false` and a Keycloak-issued JWT
   is validated (`auth_oidc.py`) into an `AuthContext`. Locally, `DEV_AUTH=true` accepts
   `X-Org-Id`/`X-User-Id`/`X-Role` headers. `main.py` **refuses to boot** if `DEV_AUTH=true` while
   `ENV != local`, so spoofable headers can never reach production.
2. **Enforcement** (`core/db.py`): the `org_id` from the identity is passed to
   `session_for_org()`, which sets the RLS tenant per transaction. Even a buggy query cannot
   cross tenant boundaries — defense in depth. Object storage adds a third layer via `org_id/`
   path prefixes.

Every core table carries `organization_id`; RLS policies (in the Alembic migrations) scope reads
and writes to `app.current_org_id`.

---

## 7. Data Model

Defined in [`models.py`](../fixmate/core/models.py); all tables carry `organization_id` for RLS.

| Table | Purpose | Key relationships |
|-------|---------|-------------------|
| `organizations` | Tenants | root of isolation |
| `users` | tech / curator / admin | → organization |
| `equipment_profiles` | Equipment a tenant services | → organization |
| `documents` | Uploaded manuals, versioned | → equipment; `superseded_by` self-FK |
| `chunks` | Retrievable units (`manual` or `field_fix`); holds `embedding` (vector) + `tsv` (FTS) + `positive_signals` | → document and/or fix |
| `figures` | Extracted diagrams + captions + bbox | → document; image in storage |
| `conversations` | A technician troubleshooting session | → user, equipment |
| `messages` | user/assistant turns | → conversation; → answer_log |
| `answer_logs` | **Immutable** record of every answer | retrieved chunk ids, confidence, citations, groundedness |
| `fixes` | Candidate/approved field fixes; carries `state`, `ai_prescreen_report` | → equipment, submitter, reviewer, answer_log |
| `feedback` | "Did it help?" + optional fix link | → message, user |
| `audit_events` | **Immutable** before/after of state changes; `actor_id` is a plain UUID (survives user deletion) | polymorphic by entity |

The two append-only tables (`answer_logs`, `audit_events`) implement the 24-month audit
retention requirement.

---

## 8. End-to-End Flows

### 8.1 Asking a question (synchronous)

```
Technician → POST /conversations/{id}/ask  (api/routers/ask.py)
  → get_current_user → AuthContext(org_id, user_id, role)
  → persist user Message (session_for_org → RLS)
  → answers.compose_answer(org_id, equipment_id, question, history)
        → retrieval.search()  →  vector + keyword → RRF → boost → rerank
        → confidence gate (low → escalate)
        → llm provider.complete()  (prompts include approved-fix badges)
        → validate citations + groundedness (retry once, else escalate)
        → write immutable AnswerLog
  → persist assistant Message (links answer_log)
  → return AnswerOut { text, confidence, escalated, citations, figures }
```

### 8.2 Ingesting a manual (asynchronous)

```
Curator/admin → POST documents (upload PDF) → store original in MinIO/S3
  → enqueue Celery task (tasks.ingest_document_task) via Redis
  → worker runs pipeline.ingest_document():
       extract pages + figures → chunk → caption figures (vision) → embed
       → registry decides version (supersede prior) → persist Document/Chunk/Figure
```

### 8.3 The approved-fix loop (the moat)

```
Technician answer → "did it help / submit a fix" (feedback)
  → Fix(state=submitted/pending_review)
  → curation.review_queue(): AI pre-screen + manual context shown to curator
  → curator approve()  → embed approved text as field_fix Chunk (indexed)
  → retrieval.search() now boosts that fix above manual content on symptom match
  → retire()/delete() removes the chunk → fix leaves retrieval immediately
  (every step writes an AuditEvent)
```

---

## 9. Configuration

All config flows through [`settings.py`](../fixmate/core/settings.py) (env vars / `.env`); see
[`../.env.example`](../.env.example). The switches that change runtime behavior most:

- `LLM_PROVIDER` = `ollama` (local dev) | `anthropic` (production).
- `DEV_AUTH` = `true` (header auth, local only) | `false` (Keycloak OIDC).
- `ENV` — must be `local` for `DEV_AUTH=true` to be allowed.
- `DATABASE_APP_URL` — the non-superuser role the app connects as so RLS actually applies.

Most source and config files carry in-file documentation (CLAUDE.md §4.4). The two JSON
config files that **cannot** hold comments are documented here instead:

- [`../web/tsconfig.json`](../web/tsconfig.json) — TypeScript compiler options for the web
  client: strict mode on (with `noUnusedLocals`/`noUnusedParameters`), `react-jsx` transform,
  `ESNext` modules with bundler resolution, targeting `ES2022`; compiles `src/`.
- [`../web/package.json`](../web/package.json) — the web client's npm manifest: scripts
  (`dev`, `build` = `tsc` + Vite, `preview`, `test`, `lint`) and dependencies (React 18) /
  dev-dependencies (TypeScript, Vite, Vitest + Testing Library, ESLint, the PWA plugin).

---

## 10. Testing

`tests/` mirrors the package layout. Per CLAUDE.md §4.3, integration tests hit a **real**
Postgres/vector DB/storage (Docker Compose), not mocks — that's where data-model assumptions
live. Notable suites: `tests/db/test_rls.py` (cross-tenant isolation), `tests/curation/`
(state machine + moat behavior), `tests/answers/` (groundedness/citation gating), and
`fixmate/evals/` (safety cases + answer-regression baseline). Run with `pytest`; integration
tests are marked `@pytest.mark.integration`.

---

## 11. Where to Look First

- **"How does an answer get produced?"** → `answers/composer.py`, then `retrieval/service.py`.
- **"How is a tenant kept isolated?"** → `core/db.py` + the RLS migration in `db/migrations`.
- **"How does an approved fix become searchable?"** → `curation/service.py` `approve()` +
  `retrieval/fusion.py` boost.
- **"What's the API surface?"** → `api/routers/` + `api/schemas.py`.
- **"How do I run it?"** → [`../setup-instructions.md`](../setup-instructions.md).
