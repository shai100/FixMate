# FixMate — Setup From Scratch

How to bring a FixMate development environment up on a fresh machine. Reflects the
repository state through Phase 7 (infrastructure, schema/RLS, LLM provider abstraction, ingestion pipeline, hybrid retrieval, answer service, HTTP API, feedback + candidate-fix submission). Keep this file in sync
with the codebase — see [Keeping this document current](#keeping-this-document-current).

---

## 1. Prerequisites

Install these before starting:

| Tool | Version | Notes |
|------|---------|-------|
| **Python** | ≥ 3.12 | Matches `requires-python` in `pyproject.toml`. |
| **Docker + Docker Compose** | recent | Runs Postgres, Redis, MinIO, Ollama. |
| **Git** | any | To clone the repo. |
| **NVIDIA GPU + driver** (optional) | — | For local Ollama acceleration (spec §8.3). Without a GPU, Ollama runs on CPU (slower) or run Ollama natively on Windows — see note in `docker-compose.yml`. |

The local stack targets the spec §8 "full local-PC profile". A 4 GB GPU is enough for the
`qwen3:4b` (Q4 generation) + `bge-m3` (CPU embeddings) profile.

---

## 2. Clone and create a Python environment

```bash
git clone <repo-url> FixMate
cd FixMate

python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -e ".[dev]"
```

`pip install -e ".[dev]"` installs the `fixmate` package in editable mode plus the dev
extras (`pytest`, `pytest-asyncio`, `ruff`).

---

## 3. Configure environment variables

```bash
cp .env.example .env
```

`.env` is gitignored. The defaults match the Docker Compose services, so no edits are
required for a default local run. Key knobs (see `.env.example` / `fixmate/core/settings.py`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `...fixmate:fixmate@localhost:5432/fixmate` | Owner role. Used for migrations + org bootstrap. |
| `DATABASE_APP_URL` | `...fixmate_app:fixmate_app@localhost:5432/fixmate` | App role — **RLS enforced** (no BYPASSRLS). The application connects as this. |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker (Phase 3+). |
| `S3_ENDPOINT` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` / `S3_BUCKET` | MinIO defaults | Object storage. |
| `LLM_PROVIDER` | `ollama` | `ollama` (local) or `anthropic` (production). |
| `OLLAMA_GENERATION_MODEL` | `qwen3:4b` | Local generation model. |
| `OLLAMA_EMBEDDING_MODEL` | `bge-m3` | Local embedding model (1024-dim — matches `chunks.embedding`). |
| `ANTHROPIC_API_KEY` | _(empty)_ | Required only when `LLM_PROVIDER=anthropic`. Never commit. |
| `DEV_AUTH` | `true` | Phase 6 header auth. **Must be `false` outside local.** |
| `ENV` | `local` | Deployment environment. The API refuses to boot when `DEV_AUTH=true` and `ENV` is not `local`. |

---

## 4. Start the infrastructure

```bash
docker compose up -d
```

This starts the four MVP services: `postgres` (pgvector/pg16), `redis`, `minio`, `ollama`.
`keycloak` is behind the `auth` compose profile and is **not** started for MVP setup
(it comes online in Phase 9 via `docker compose --profile auth up -d`).

Confirm services are up and Postgres is healthy:

```bash
docker compose ps
```

Expect `postgres` to show `Up (healthy)`.

---

## 5. Pull the local LLM models

The Ollama container starts empty. Pull the two required models:

```bash
docker compose exec ollama ollama pull qwen3:4b
docker compose exec ollama ollama pull bge-m3
```

(If `OLLAMA_*` model names in `.env` differ, pull those instead. The healthcheck in the
next step prints the exact `ollama pull` command for any missing model.)

---

## 6. Apply database migrations

This creates the schema, the `vector` extension, indexes (HNSW + GIN), RLS policies, **and
the non-superuser `fixmate_app` role** that the application connects as:

```bash
alembic upgrade head
```

`alembic.ini` reads the DB URL from `fixmate.core.settings`, so no URL needs to be hardcoded.
There is no separate "create the app role" step — the migration provisions `fixmate_app`
(with its `LOGIN` password) and grants.

---

## 7. Verify the environment

`scripts/healthcheck.py` probes every Compose service and reports one status line each:

```bash
python scripts/healthcheck.py
```

Expected output (no `MISSING model` lines):

```
postgres OK PostgreSQL 16.x ...
redis OK
minio OK
ollama OK, models: ['bge-m3:latest', 'qwen3:4b']
```

If a model is missing, the script prints the exact `ollama pull` command to fix it.

---

## 8. Run the test suite

```bash
pytest tests/db -v
pytest tests/llm -v
pytest tests/ingestion -v
pytest tests/retrieval -v
pytest tests/answers -v
pytest tests/api -v
pytest tests/feedback -v
```

The `tests/answers` suite covers the answer service (Phase 5): pure-unit groundedness
and confidence-band tests, plus `@pytest.mark.integration` composer tests that drive the
full RAG pipeline against the live Ollama model — these are slow (minutes each on the CPU
profile), so keep `docker compose up -d` running.

The `migrated_db` fixture runs `alembic upgrade head` automatically, so tests work against a
real Postgres (no mocks — per CLAUDE.md §4.3). All schema + RLS tests should pass (8/8 as of
Phase 1). The `tests/llm` suite covers the LLM provider abstraction (Phase 2); its
`@pytest.mark.integration` cases hit the live Ollama container, so keep `docker compose up -d`
running. Run linting/formatting too:

```bash
ruff check
ruff format --check
```

Smoke-test the LLM provider abstraction end-to-end (Phase 2 standalone check):

```bash
python -m fixmate.llm.cli "Say OK"                 # uses LLM_PROVIDER (default: ollama)
python -m fixmate.llm.cli "Say OK" --provider anthropic   # requires ANTHROPIC_API_KEY
```

Expect a line like `[ollama/qwen3:4b] OK`.

Ingest a manual end-to-end (Phase 3 standalone check). This creates the org/equipment
if missing, parses the PDF, embeds chunks, captions + stores figures, and writes rows:

```bash
python -m fixmate.ingestion.cli tests/fixtures/sample-manual.pdf --org demo --equipment "Pump X"
```

Expect `ingested document <uuid>: 3 chunks, 1 figures`. Verify the chunks landed:

```bash
docker compose exec postgres psql -U fixmate -c "select count(*), source_type from chunks group by source_type;"
```

Figure captioning uses the configured LLM provider; the local `ollama` backend has no
vision (spec §8.3), so figures get a deterministic fallback caption. Set
`LLM_PROVIDER=anthropic` (with `ANTHROPIC_API_KEY`) for real Claude captions.

Ask a grounded, cited question end-to-end (Phase 5 standalone check). This runs hybrid
retrieval → confidence gate → LLM compose → citation + groundedness validation → answer
log:

```bash
python -m fixmate.answers.cli "How do I fix error E47?" --org demo --equipment "Pump X"
```

Expect a `[high]` or `[medium]` answer with inline citations and an `answer_log_id`. The
same command with `LLM_PROVIDER=anthropic` runs the identical code path on Claude (spec
§8.3 backend switch). An out-of-corpus question (e.g. "calibrate the flux capacitor")
prints `[low] ESCALATED` with no fabricated answer.

Run the HTTP API (Phase 6 standalone check). The API exposes conversations, the RAG
`ask` endpoint, equipment, and document upload behind dev-header auth:

```bash
uvicorn fixmate.api.main:app --reload      # serves on http://localhost:8000
```

With `DEV_AUTH=true` (the default), every request carries identity headers
(`X-Org-Id` / `X-User-Id` / `X-Role`). Org id always comes from these headers, never a query
param. The server **refuses to boot** if `DEV_AUTH=true` while `ENV` is not `local`. Example
round-trip (substitute real org/user UUIDs — create them with the seed in a later phase, or
insert an `organizations` + `users` row directly):

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/conversations \
  -H "X-Org-Id: <org-uuid>" -H "X-User-Id: <user-uuid>" -H "X-Role: tech" -d '{}'
curl -s -X POST localhost:8000/conversations/<conversation-id>/ask \
  -H "X-Org-Id: <org-uuid>" -H "X-User-Id: <user-uuid>" -H "X-Role: tech" \
  -H "Content-Type: application/json" -d '{"question":"How do I fix error E47?"}'
```

The `tests/api` suite covers this layer; its `@pytest.mark.integration` cases drive the full
RAG pipeline through `ask` (slow on the CPU profile) and enqueue a real Celery upload task
(needs Redis), so keep `docker compose up -d` running.

The API also exposes feedback (Phase 7): `POST /messages/{id}/feedback {helped, fix_text?, photos?}`.
A positive signal reinforces the cited chunks (`chunks.positive_signals`); a negative signal with
`fix_text` opens a candidate fix that lands in the curation queue (`state=pending_review`) with an
audit event — it is never indexed, so it cannot be served until a curator approves it. The
`tests/feedback` suite covers it; most cases are pure DB (fast), with one `@pytest.mark.integration`
case proving a submitted fix never surfaces in retrieval.

### Async ingestion via Celery (optional)

The `--async` flag enqueues ingestion on the Celery worker instead of running inline.
Start a worker (the `--pool=solo` pool is required on Windows):

```bash
celery -A fixmate.ingestion.tasks worker -l info --pool=solo
```

Then enqueue:

```bash
python -m fixmate.ingestion.cli tests/fixtures/sample-manual.pdf --org demo --equipment "Pump X" --async
```

The CLI prints the task id; the worker logs the resulting document id. Redis (already in
the Compose stack) is the broker and result backend.

---

## 9. Service endpoints reference

| Service | Endpoint | Credentials |
|---------|----------|-------------|
| Postgres | `localhost:5432` | `fixmate` / `fixmate` (owner); `fixmate_app` / `fixmate_app` (app) |
| Redis | `localhost:6379` | — |
| MinIO API | `localhost:9000` | `fixmate` / `fixmate123` |
| MinIO Console | `localhost:9001` | `fixmate` / `fixmate123` |
| Ollama | `localhost:11434` | — |
| Keycloak (Phase 9, `auth` profile) | `localhost:8080` | `admin` / `admin` |

---

## 10. Teardown

```bash
docker compose down          # stop services, keep data
docker compose down -v       # stop services AND delete volumes (pgdata, miniodata, ollamadata)
```

---

## Keeping this document current

Per CLAUDE.md §4.7, this file is part of the project's audit trail. **Whenever a change
affects how the system is set up from scratch, update this document in the same commit.**
That includes (non-exhaustive):

- New or removed Compose services / changed images or ports (`docker-compose.yml`).
- New required environment variables or changed defaults (`.env.example`, `fixmate/core/settings.py`).
- New setup steps: migrations, seed scripts, model pulls, role provisioning.
- New prerequisites (language/runtime versions, system tools), changed dependencies (`pyproject.toml`).
- Changes to verification commands (`scripts/healthcheck.py`, test invocation).
- A phase coming online that flips a previously-gated service on by default (e.g. Keycloak/`auth` profile in Phase 9).

If a change makes a step here obsolete, remove or correct it — don't leave stale instructions.
