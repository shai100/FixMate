# FixMate MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FixMate MVP (spec §6: text Q&A with citations + confidence, PDF ingestion with figures, equipment profiles, feedback loop, full curation workflow, basic admin, English) running entirely on a local PC per spec §8.

**Architecture:** Python/FastAPI monolith + Celery workers over Postgres (pgvector + FTS + RLS), MinIO, Redis, and Ollama, all in Docker Compose. LLM access goes through a provider-abstraction layer (`LLM_PROVIDER=ollama|anthropic`). One React PWA serves technician chat and curator/admin views with role-based routes (MVP simplification of the spec's two clients — same design system, fewer moving parts).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (async) + Alembic, Celery + Redis, pgvector, PyMuPDF, httpx (Ollama), `anthropic` SDK (Claude), React + Vite + TypeScript, pytest + testcontainers-style integration tests against the compose services.

**Source spec:** `docs/fixmate-product-spec.md` v1.1. **Architecture rules:** `CLAUDE.md`.

---

## How to use this plan

- Phases are ordered by dependency; each phase ends with **working, independently runnable software** and a "Run it standalone" section with exact commands.
- Within a phase, tasks follow TDD: failing test → minimal implementation → pass → commit. Commit at every ✅ step.
- This is the master plan. Phases 3, 5, 8, 10–11 are large; when starting one, expand it into a detailed task file `docs/superpowers/plans/2026-MM-DD-phase-N-<name>.md` using the same format, keeping the contracts defined here (Appendix A) verbatim.
- Integration tests hit the real compose services (CLAUDE.md §4.3 — no mocks for DB/vector/storage).

## Phase status board

| Phase | Deliverable | Standalone verification | Status |
|---|---|---|---|
| 0 | Repo scaffold + Compose infra | `docker compose up -d` + `python scripts/healthcheck.py` | ☐ |
| 1 | Schema, migrations, RLS tenancy | `pytest tests/db -v` | ☑ |
| 2 | LLM provider abstraction | `python -m fixmate.llm.cli "ping"` + `pytest tests/llm -v` | ☐ |
| 3 | Ingestion pipeline (PDF→chunks+figures→index) | `python -m fixmate.ingestion.cli <pdf> --org demo` | ☐ |
| 4 | Hybrid retrieval (vector+FTS+RRF+boost) | `python -m fixmate.retrieval.cli "E47" --org demo` | ☑ |
| 5 | Answer service (RAG, citations, confidence, groundedness, logging) | `python -m fixmate.answers.cli "How do I fix E47?" --org demo` | ☑ |
| 6 | HTTP API + dev auth + conversations | `uvicorn fixmate.api.main:app` + `pytest tests/api -v` | ☑ |
| 7 | Feedback + candidate-fix submission | `pytest tests/feedback -v` | ☑ |
| 8 | Curation workflow + pre-screen + audit + index sync | `pytest tests/curation -v` | ☐ |
| 9 | Keycloak OIDC (replace dev auth) | `pytest tests/auth -v` (live Keycloak) | ☐ |
| 10 | Technician PWA (chat) | `npm run dev` in `web/` | ☐ |
| 11 | Curator/Admin console views | `npm run dev`, role=curator | ☐ |
| 12 | Safety + answer-regression eval harness, demo seed | `python -m fixmate.evals.run` | ☐ |

Dependency graph: 0 → 1 → {2, 3*} ; 3 needs 1+2 (captioning/embeddings); 4 needs 3; 5 needs 4; 6 needs 5; 7 needs 6; 8 needs 7; 9 needs 6; 10 needs 6; 11 needs 8; 12 needs 5 (grows with 8).

## Repository layout (target)

```
fixmate/                  # Python package
  core/                   #   settings, db engine/session, tenancy context
  llm/                    #   provider abstraction: base.py, ollama_provider.py,
                          #   anthropic_provider.py, embeddings.py, cli.py
  ingestion/              #   pdf.py, chunking.py, figures.py, pipeline.py, tasks.py, cli.py
  retrieval/              #   vector.py, keyword.py, fusion.py, rerank.py, service.py, cli.py
  answers/                #   prompts.py, composer.py, groundedness.py, confidence.py,
                          #   answer_log.py, cli.py
  curation/               #   states.py, service.py, prescreen.py
  feedback/               #   service.py
  api/                    #   main.py, deps.py (auth), routers/{ask,conversations,feedback,
                          #   fixes,curation,equipment,documents,admin}.py
  evals/                  #   run.py, safety_cases.yaml, regression_baseline.jsonl
db/migrations/            # Alembic
scripts/                  # healthcheck.py, seed_demo.py
tests/                    # mirrors package: db/ llm/ ingestion/ retrieval/ answers/
                          #   api/ feedback/ curation/ auth/
web/                      # React PWA (Vite + TS): technician chat + admin routes
docker-compose.yml
.env.example
pyproject.toml
```

---

## Phase 0 — Repo scaffold + local infrastructure

**Files:** Create `docker-compose.yml`, `.env.example`, `pyproject.toml`, `fixmate/__init__.py`, `fixmate/core/settings.py`, `scripts/healthcheck.py`, `tests/conftest.py`, `.gitignore` (add `.env`, `.venv/`, `web/node_modules/`).

- [x] **0.1 Write `docker-compose.yml`** (spec §8.2):

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: fixmate
      POSTGRES_PASSWORD: fixmate
      POSTGRES_DB: fixmate
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck: { test: ["CMD-SHELL", "pg_isready -U fixmate"], interval: 5s, retries: 10 }
  redis:
    image: redis:7
    ports: ["6379:6379"]
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment: { MINIO_ROOT_USER: fixmate, MINIO_ROOT_PASSWORD: fixmate123 }
    ports: ["9000:9000", "9001:9001"]
    volumes: [miniodata:/data]
  ollama:
    image: ollama/ollama
    ports: ["11434:11434"]
    volumes: [ollamadata:/root/.ollama]
    # GPU passthrough (WSL2 + NVIDIA driver). Alternative: run Ollama natively on
    # Windows and set OLLAMA_BASE_URL=http://host.docker.internal:11434 (spec §8.2).
    deploy: { resources: { reservations: { devices: [{ driver: nvidia, count: 1, capabilities: [gpu] }] } } }
  keycloak:
    image: quay.io/keycloak/keycloak:26.0
    command: start-dev
    environment: { KEYCLOAK_ADMIN: admin, KEYCLOAK_ADMIN_PASSWORD: admin }
    ports: ["8080:8080"]
    profiles: ["auth"]   # not started until Phase 9: docker compose --profile auth up -d
volumes: { pgdata: {}, miniodata: {}, ollamadata: {} }
```

- [x] **0.2 Write `.env.example`** (copy to `.env` locally; never commit `.env`):

```env
DATABASE_URL=postgresql+asyncpg://fixmate:fixmate@localhost:5432/fixmate
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=fixmate
S3_SECRET_KEY=fixmate123
S3_BUCKET=fixmate
LLM_PROVIDER=ollama                # ollama | anthropic  (spec §8.3)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_GENERATION_MODEL=qwen3:4b
OLLAMA_EMBEDDING_MODEL=bge-m3
ANTHROPIC_API_KEY=                 # only when LLM_PROVIDER=anthropic
ANTHROPIC_MODEL=claude-opus-4-8
DEV_AUTH=true                      # Phase 6 header auth; must be false outside local
```

- [x] **0.3 Write `pyproject.toml`** — package `fixmate`, deps: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]>=2`, `asyncpg`, `alembic`, `pgvector`, `celery[redis]`, `redis`, `httpx`, `anthropic`, `boto3`, `pymupdf`, `pydantic-settings`, `python-multipart`; dev: `pytest`, `pytest-asyncio`, `ruff`. Install: `python -m venv .venv; .venv\Scripts\activate; pip install -e ".[dev]"`.

- [x] **0.4 Write `fixmate/core/settings.py`** — `class Settings(BaseSettings)` mirroring `.env.example` fields exactly (types: all `str` except `dev_auth: bool`); `settings = Settings()` module singleton reading `.env`.

- [x] **0.5 Write `scripts/healthcheck.py`** — connects to each service and prints one line per service:

```python
import asyncio, httpx, redis, boto3, asyncpg
from fixmate.core.settings import settings

async def main() -> None:
    conn = await asyncpg.connect(settings.database_url.replace("+asyncpg", ""))
    print("postgres OK", await conn.fetchval("select version()"))
    await conn.close()
    print("redis OK" if redis.from_url(settings.redis_url).ping() else "redis FAIL")
    s3 = boto3.client("s3", endpoint_url=settings.s3_endpoint,
                      aws_access_key_id=settings.s3_access_key,
                      aws_secret_access_key=settings.s3_secret_key)
    s3.list_buckets(); print("minio OK")
    r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
    models = [m["name"] for m in r.json().get("models", [])]
    print("ollama OK, models:", models)
    for required in (settings.ollama_generation_model, settings.ollama_embedding_model):
        if not any(required in m for m in models):
            print(f"  MISSING model {required} — run: ollama pull {required}")

asyncio.run(main())
```

- [ ] **0.6 Run it standalone:**

```powershell
docker compose up -d
docker exec $(docker compose ps -q ollama) ollama pull qwen3:4b
docker exec $(docker compose ps -q ollama) ollama pull bge-m3
python scripts/healthcheck.py
```
Expected: four `OK` lines, no `MISSING model` lines.

- [ ] **0.7 Commit:** `git add -A; git commit -m "feat: compose infrastructure + settings + healthcheck (phase 0)"`

**Exit criteria:** fresh clone + `.env` + the commands above = all services healthy.

---

## Phase 1 — Database schema, migrations, RLS tenancy

**Files:** Create `db/migrations/` (alembic init, async template), `fixmate/core/db.py` (async engine + `session_for_org(org_id)` context manager), `fixmate/core/models.py` (SQLAlchemy models), `tests/db/test_rls.py`, `tests/db/test_schema.py`.

Tables (every one carries `organization_id uuid not null` — CLAUDE.md §4.5): `organizations`, `users(role in ('tech','curator','admin'))`, `equipment_profiles`, `documents(version int, superseded_by uuid null, storage_key)`, `chunks(source_type in ('manual','field_fix'), content, page, fix_id uuid null, embedding vector(1024), tsv tsvector)`, `figures(page, caption, storage_key, bbox jsonb)`, `fixes` (fields per spec §5.4 incl. `state in ('submitted','pending_review','approved','rejected','unsafe','retired')`, `ai_prescreen_report jsonb`), `conversations`, `messages`, `answer_logs(retrieved_chunk_ids uuid[], model_version, provider, confidence, citations jsonb, groundedness jsonb, tokens_used)`, `feedback(helped bool, fix_id uuid null)`, `audit_events(actor_id, entity_type, entity_id, action, before jsonb, after jsonb)`.

Key migration details:
- `CREATE EXTENSION IF NOT EXISTS vector;`
- `embedding vector(1024)` — **BGE-M3 emits 1024-dim vectors; this dimension is a contract with Phase 2/3.**
- `tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED` — `'english'` config gives stemming ("valves" matches "valve"); if more launch languages are added later (FR-7), switch to `'simple'` or per-language configs and re-run this migration.
- Indexes: `USING hnsw (embedding vector_cosine_ops)` on chunks; `USING gin (tsv)`.
- RLS on every tenant table:

```sql
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON chunks
  USING (organization_id = current_setting('app.current_org_id')::uuid);
```
- App connects as non-superuser role `fixmate_app` (create in migration, grant CRUD, no BYPASSRLS). `session_for_org` opens a transaction and issues `SET LOCAL app.current_org_id = :org`.

- [x] **1.1 Write failing RLS test** `tests/db/test_rls.py`:

```python
import pytest
from fixmate.core.db import session_for_org
from fixmate.core.models import EquipmentProfile

@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_reads(two_orgs):   # fixture creates org_a, org_b
    org_a, org_b = two_orgs
    async with session_for_org(org_a) as s:
        s.add(EquipmentProfile(organization_id=org_a, name="Pump X"))
        await s.commit()
    async with session_for_org(org_b) as s:
        rows = (await s.execute(select(EquipmentProfile))).scalars().all()
        assert rows == []          # org_b must not see org_a's data

@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_insert(two_orgs):
    org_a, org_b = two_orgs
    async with session_for_org(org_b) as s:
        s.add(EquipmentProfile(organization_id=org_a, name="Sneaky"))
        with pytest.raises(Exception):   # RLS WITH CHECK violation
            await s.commit()
```

- [x] **1.2 Run:** `pytest tests/db -v` → FAIL (models/migrations missing).
- [x] **1.3 Implement models + initial Alembic migration + `db.py`.** `alembic upgrade head`.
- [x] **1.4 Run:** `pytest tests/db -v` → PASS.
- [x] **1.5 Commit:** `git commit -m "feat: schema + RLS tenant isolation (phase 1)"`

**Run it standalone:** `alembic upgrade head; pytest tests/db -v`. The RLS tests are the multi-org CI scenario CLAUDE.md §6 demands — they run on every PR from here on.

---

## Phase 2 — LLM provider abstraction

**Files:** Create `fixmate/llm/base.py`, `fixmate/llm/ollama_provider.py`, `fixmate/llm/anthropic_provider.py`, `fixmate/llm/embeddings.py`, `fixmate/llm/factory.py`, `fixmate/llm/cli.py`, `tests/llm/test_factory.py`, `tests/llm/test_ollama_integration.py`.

- [ ] **2.1 Define the contract** `fixmate/llm/base.py` (this is Appendix A.1 — later phases import these names exactly):

```python
from dataclasses import dataclass, field
from typing import Protocol

@dataclass
class CompletionRequest:
    system: str
    messages: list[dict]            # [{"role": "user"|"assistant", "content": str}]
    max_tokens: int = 2048
    json_response: bool = False     # provider must coax/enforce JSON output

@dataclass
class CompletionResult:
    text: str
    model_version: str              # e.g. "qwen3:4b" / "claude-opus-4-8"
    provider: str                   # "ollama" / "anthropic"
    tokens_used: int = 0

class LLMProvider(Protocol):
    async def complete(self, request: CompletionRequest) -> CompletionResult: ...
    async def caption_image(self, image: bytes, media_type: str, context: str) -> str: ...
```

- [ ] **2.2 Write failing factory test** `tests/llm/test_factory.py`: `get_provider()` returns `OllamaProvider` when `LLM_PROVIDER=ollama`, `AnthropicProvider` when `anthropic` (monkeypatch settings); unknown value raises `ValueError`.
- [ ] **2.3 Implement `OllamaProvider`** with `httpx.AsyncClient`: `complete` → `POST {base}/api/chat` (`stream: false`, `format: "json"` when `json_response`); `caption_image` → chat with base64 `images` (works only if a vision model is configured; raise `NotImplementedError` with message "use anthropic backend for captioning" when generation model lacks vision — spec §8.3 keeps captioning on Claude).
- [ ] **2.4 Implement `AnthropicProvider`** with the official SDK (CLAUDE.md §3.1; model from settings, default `claude-opus-4-8`):

```python
from anthropic import AsyncAnthropic

class AnthropicProvider:
    def __init__(self, api_key: str, model: str):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        msg = await self._client.messages.create(
            model=self._model,
            system=request.system,
            messages=request.messages,
            max_tokens=request.max_tokens,
            thinking={"type": "adaptive"},
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        return CompletionResult(text=text, model_version=self._model,
                                provider="anthropic",
                                tokens_used=msg.usage.input_tokens + msg.usage.output_tokens)

    async def caption_image(self, image: bytes, media_type: str, context: str) -> str:
        import base64
        msg = await self._client.messages.create(
            model=self._model, max_tokens=300,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                    "media_type": media_type, "data": base64.b64encode(image).decode()}},
                {"type": "text", "text": f"Caption this technical figure for search indexing. Context: {context}. One sentence, include figure number and page if visible."},
            ]}])
        return "".join(b.text for b in msg.content if b.type == "text").strip()
```

- [ ] **2.5 Implement `embeddings.py`**: `async def embed(texts: list[str]) -> list[list[float]]` → `POST {OLLAMA_BASE_URL}/api/embed` with `model=bge-m3` (embeddings always run on the Ollama/CPU path regardless of `LLM_PROVIDER` — spec §8.3; assert `len(vec) == 1024`).
- [ ] **2.6 Integration test** `tests/llm/test_ollama_integration.py` (marked `@pytest.mark.integration`, needs compose up): `complete()` returns non-empty text; `embed(["hello", "pump pressure too high"])` returns two 1024-dim vectors.
- [ ] **2.7 `cli.py`:** `python -m fixmate.llm.cli "Say OK" [--provider anthropic]` prints `[provider/model] text`.
- [ ] **2.8 Run:** `pytest tests/llm -v` → PASS; CLI prints a response. **Commit:** `"feat: LLM provider abstraction with ollama + anthropic backends (phase 2)"`

---

## Phase 3 — Ingestion pipeline

**Files:** Create `fixmate/ingestion/pdf.py` (PyMuPDF text+figure extraction), `fixmate/ingestion/chunking.py`, `fixmate/ingestion/figures.py` (caption via provider, upload to MinIO), `fixmate/ingestion/pipeline.py` (orchestrates: parse → chunk → embed → store), `fixmate/ingestion/tasks.py` (Celery wrapper), `fixmate/ingestion/cli.py`, `fixmate/core/storage.py` (boto3 MinIO helper, keys prefixed `org_id/` — CLAUDE.md §6), minimal CRUD for equipment profiles/documents in `fixmate/ingestion/registry.py`, tests in `tests/ingestion/`, fixture PDF `tests/fixtures/sample-manual.pdf` (generate with PyMuPDF in a fixture: 3 pages, known sentences incl. "Error E47: concentrate valve blocked", a torque spec "tighten to 12 Nm", one embedded image).

- [x] **3.1 Failing test — chunking** `tests/ingestion/test_chunking.py`:

```python
from fixmate.ingestion.chunking import chunk_pages

def test_chunks_carry_page_numbers_and_respect_size():
    pages = [(1, "A. " * 300), (2, "B. " * 300)]
    chunks = chunk_pages(pages, max_chars=800, overlap=120)
    assert all(len(c.text) <= 800 for c in chunks)
    assert {c.page for c in chunks} == {1, 2}
    assert chunks[1].text[:120] in chunks[0].text + chunks[1].text  # overlap preserved
```
Implement `chunk_pages` (sentence-boundary split, char budget ~800 ≈ <512 tokens — reranker stability constraint, CLAUDE.md §4.4). Run → PASS → commit.

- [x] **3.2 Failing test — PDF extraction:** parse fixture PDF → page texts contain "E47"; exactly 1 figure extracted with page + bbox. Implement `pdf.py` (`fitz.open`; `page.get_text()`; `page.get_images` + `Pixmap` bytes). Run → PASS → commit.
- [x] **3.3 Failing test — end-to-end ingest (integration):** `ingest_document(org_id, equipment_id, pdf_path)` →
  - a `documents` row (version 1), N `chunks` rows with non-null 1024-dim embeddings and `source_type='manual'`,
  - 1 `figures` row whose caption is non-empty and whose `storage_key` exists in MinIO,
  - re-ingesting same file bumps `version` to 2 and sets `superseded_by` on v1 (FR-9).
  Implement `pipeline.py` + `storage.py` + `registry.py`. Run → PASS → commit.
- [x] **3.4 Celery wrapper** `tasks.py`: `@app.task ingest_document_task(...)` calling the sync entry; worker boots with `celery -A fixmate.ingestion.tasks worker -l info --pool=solo` (`--pool=solo` is the Windows-compatible pool). Smoke test only (enqueue + poll result). Commit.
- [x] **3.5 CLI:** `python -m fixmate.ingestion.cli tests/fixtures/sample-manual.pdf --org demo --equipment "Pump X" [--async]` — creates org/equipment if missing (dev convenience), prints chunk/figure counts.

**Run it standalone:** the CLI command above, then verify:
`docker exec -it $(docker compose ps -q postgres) psql -U fixmate -c "select count(*), source_type from chunks group by source_type;"`

---

## Phase 4 — Hybrid retrieval

**Files:** Create `fixmate/retrieval/vector.py`, `keyword.py`, `fusion.py`, `rerank.py`, `service.py`, `cli.py`; tests `tests/retrieval/test_fusion.py`, `tests/retrieval/test_search_integration.py`.

- [x] **4.1 Failing test — RRF (pure unit):**

```python
from fixmate.retrieval.fusion import reciprocal_rank_fusion

def test_rrf_rewards_agreement():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]])
    assert fused[0] in ("a", "b") and set(fused) == {"a", "b", "c", "d"}

def test_field_fix_boost_promotes_fix():
    scores = {"manual1": 0.030, "fix1": 0.029}
    boosted = apply_field_fix_boost(scores, field_fix_ids={"fix1"}, boost=1.15)
    assert boosted["fix1"] > boosted["manual1"]
```

- [x] **4.2 Implement `fusion.py`:**

```python
from collections import defaultdict

RRF_K = 60  # standard RRF constant; rank discount flattens beyond top ~k results

def reciprocal_rank_fusion(result_lists: list[list[str]], k: int = RRF_K) -> list[str]:
    scores: dict[str, float] = defaultdict(float)
    for results in result_lists:
        for rank, cid in enumerate(results):
            scores[cid] += 1.0 / (k + rank + 1)
    return [cid for cid, _ in sorted(scores.items(), key=lambda x: -x[1])]

def apply_field_fix_boost(scores: dict[str, float], field_fix_ids: set[str],
                          boost: float = 1.15) -> dict[str, float]:
    # Approved-fix moat (spec §2.4 / FR-17): field fixes outrank manual content
    # on comparable relevance. 1.15 is an initial value; tune via Phase 12 evals.
    return {cid: s * boost if cid in field_fix_ids else s for cid, s in scores.items()}
```
Run → PASS → commit.

- [x] **4.3 Vector + keyword search** (integration test): `vector.py` = cosine KNN via pgvector (`ORDER BY embedding <=> :qvec LIMIT 20`); `keyword.py` = `WHERE tsv @@ plainto_tsquery('english', :q) ORDER BY ts_rank(...) LIMIT 20` (query config must match the `'english'` tsvector config from Phase 1). Test seeds chunks and asserts: query "E47" — keyword search finds the exact-code chunk even when vector search ranks it low (the hybrid justification, spec §5.2). All queries run inside `session_for_org` (RLS scopes tenancy automatically).
- [x] **4.4 Reranker** `rerank.py`: MVP = embed query + candidate texts with BGE-M3, re-sort by cosine similarity; return `(chunk, score∈[0,1])`. Interface: `async def rerank(query: str, chunks: list[Chunk]) -> list[tuple[Chunk, float]]`. (Cross-encoder `bge-reranker-v2-m3` is a drop-in upgrade later — same signature.) Test: known-relevant chunk ranks first on fixture data.
- [x] **4.5 `service.py`:** `async def search(org_id, equipment_id, query, top_k=8) -> list[ScoredChunk]` — embed query → vector + keyword in parallel → RRF → field-fix boost → rerank → top_k. `ScoredChunk = (chunk_id, document_id, source_type, page, text, score, fix_id|None)`.
- [x] **4.6 CLI:** `python -m fixmate.retrieval.cli "E47 error" --org demo` prints ranked table (score, source_type, page, first 80 chars). Run against Phase 3 ingested data. Commit.

---

## Phase 5 — Answer service

**Files:** Create `fixmate/answers/prompts.py`, `composer.py`, `groundedness.py`, `confidence.py`, `answer_log.py`, `cli.py`; tests `tests/answers/`.

- [ ] **5.1 Failing tests — groundedness post-check** (pure unit; this is the spec §8.4 / FR-4 safety gate, backend-independent):

```python
from fixmate.answers.groundedness import check_groundedness

CHUNKS = ["Tighten the valve bolts to 12 Nm.", "Use part AB-1234 for the seal."]

def test_grounded_numeric_and_part_claims_pass():
    ok, violations = check_groundedness("Tighten bolts to 12 Nm and fit part AB-1234.", CHUNKS)
    assert ok and violations == []

def test_fabricated_torque_is_rejected():
    ok, violations = check_groundedness("Tighten bolts to 25 Nm.", CHUNKS)
    assert not ok and "25 Nm" in violations[0]

def test_fabricated_part_number_is_rejected():
    ok, violations = check_groundedness("Order part ZZ-9999.", CHUNKS)
    assert not ok
```

- [ ] **5.2 Implement `groundedness.py`:**

```python
import re

NUMERIC_CLAIM = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:n·?m|nm|bar|psi|kpa|mpa|v|volts?|a|amps?|ohms?|°\s?[cf]|mm|cm|rpm|hz)\b",
    re.IGNORECASE)
PART_NUMBER = re.compile(r"\b[A-Z]{2,}-?\d{2,}[A-Z0-9-]*\b")

def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("·", ""))

def check_groundedness(answer: str, chunk_texts: list[str]) -> tuple[bool, list[str]]:
    corpus = _normalize(" ".join(chunk_texts))
    violations = [m.group(0) for rx in (NUMERIC_CLAIM, PART_NUMBER)
                  for m in rx.finditer(answer) if _normalize(m.group(0)) not in corpus]
    return (not violations, violations)
```
Run → PASS → commit.

- [ ] **5.3 Confidence** `confidence.py`: map top rerank score → `high (≥0.70) / medium (≥0.45) / low`; `low` ⇒ answer is replaced by the FR-4 "don't know" response (nearest sections + escalate action). Thresholds are initial values — calibrate in Phase 12; do not lower without eval evidence (CLAUDE.md §4.4 safety-critical comment goes on these constants). Unit tests for the three bands.
- [ ] **5.4 Prompts** `prompts.py`: system prompt for answer composition — answer ONLY from supplied chunks; structure: safety warnings first, diagnosis, numbered steps with exact values, required parts, citations as `[chunk:<id>]` markers after each claim; field-fix chunks must be presented with their verification badge text "Field-verified — approved by {approver} on {date}"; respond in English.
- [ ] **5.5 Composer (integration test):** `compose_answer(org_id, equipment_id, question, history=[])` → search (Phase 4) → if confidence low: return escalation answer (no LLM call for the body); else LLM `complete` → parse `[chunk:id]` citations → validate every cited id ∈ retrieved set → run `check_groundedness`; on failure retry once with violations appended to the prompt, then degrade to escalation answer → persist `answer_logs` row (retrieved_chunk_ids, model_version, provider, confidence, citations, groundedness, tokens_used — CLAUDE.md §4.5). Returns `Answer(text, confidence, citations[], figures[], escalated: bool, answer_log_id)`. Figures: any retrieved chunk's page with a `figures` row attaches the figure URL (FR-3c).
  - Integration test asserts: answer text non-empty, ≥1 citation, `answer_logs` row written, and a nonsense question ("How do I calibrate the flux capacitor?") yields `escalated=True`.
- [ ] **5.6 CLI:** `python -m fixmate.answers.cli "How do I fix error E47?" --org demo` prints answer, confidence, citations, log id. Commit.

**Run it standalone:** CLI above with `LLM_PROVIDER=ollama`; flip to `anthropic` and rerun — same code path, different backend (the spec §8.3 switch, demonstrably working).

---

## Phase 6 — HTTP API + dev auth + conversations

**Files:** Create `fixmate/api/main.py`, `fixmate/api/deps.py`, `fixmate/api/routers/{ask,conversations,equipment,documents}.py`; tests `tests/api/` (httpx `ASGITransport`).

- [x] **6.1 Dev auth dependency** `deps.py`: `get_current_user(request) -> AuthContext(org_id, user_id, role)`. When `DEV_AUTH=true`: read `X-Org-Id`/`X-User-Id`/`X-Role` headers. When false: defer to OIDC validator (Phase 9 fills this in; until then raise 501). **Guard:** at startup, refuse to boot if `DEV_AUTH=true` and `ENV=production`. Org id always comes from auth context, never from query params (CLAUDE.md §6).
- [x] **6.2 Endpoints (TDD each: failing httpx test → implement → pass → commit):**
  - `POST /conversations` / `GET /conversations/{id}` — create, fetch with messages.
  - `POST /conversations/{id}/ask {question}` → stores user message, calls `compose_answer` with conversation history (FR-5), stores assistant message, returns answer payload (text, confidence, citations with document title + page, figure URLs, escalated, message_id).
  - `POST /equipment` / `GET /equipment` — minimal profiles CRUD (FR-10).
  - `POST /documents/upload` (multipart) → save to MinIO → enqueue `ingest_document_task` → 202 + document id; `GET /documents/{id}` reports ingestion status (FR-8).
  - Tenancy test: org A's conversation 404s under org B's headers (RLS proves itself through the API).
- [x] **6.3 Run it standalone:** `uvicorn fixmate.api.main:app --reload` then:

```powershell
curl -X POST localhost:8000/conversations -H "X-Org-Id: <uuid>" -H "X-User-Id: <uuid>" -H "X-Role: tech"
curl -X POST localhost:8000/conversations/<id>/ask -H "..." -d '{"question":"How do I fix E47?"}'
```

---

## Phase 7 — Feedback + candidate-fix submission

**Files:** Create `fixmate/feedback/service.py`, `fixmate/api/routers/feedback.py`; tests `tests/feedback/`.

- [x] **7.1 TDD:** `POST /messages/{id}/feedback {helped: bool, fix_text?, photos?}`:
  - `helped=true` → `feedback` row; increments a `positive_signals` counter on the cited chunks (FR-13's reinforcement signal, stored now, used by ranking later).
  - `helped=false` + `fix_text` → `feedback` row **and** a `fixes` row in state `submitted` linked to question, answer_log, equipment, submitter (FR-12); immediately transitions to `pending_review` and writes an `audit_events` row.
  - Test: submitted fix is **not** retrievable via Phase 4 search (never serve unapproved fixes — spec §2.4).
- [x] **7.2 Commit.** Standalone: `pytest tests/feedback -v`.

---

## Phase 8 — Curation workflow (the moat)

**Files:** Create `fixmate/curation/states.py`, `service.py`, `prescreen.py`, `fixmate/api/routers/curation.py`; tests `tests/curation/`.

- [ ] **8.1 Failing tests — state machine** (pure unit):

```python
from fixmate.curation.states import can_transition

def test_legal_lifecycle():
    assert can_transition("submitted", "pending_review")
    assert can_transition("pending_review", "approved")
    assert can_transition("pending_review", "rejected")
    assert can_transition("pending_review", "unsafe")
    assert can_transition("approved", "retired")

def test_illegal_transitions_blocked():
    assert not can_transition("submitted", "approved")     # cannot skip review
    assert not can_transition("rejected", "approved")      # must resubmit
    assert not can_transition("unsafe", "approved")
```

- [ ] **8.2 Implement `states.py`:**

```python
ALLOWED_TRANSITIONS: set[tuple[str, str]] = {
    ("submitted", "pending_review"),
    ("pending_review", "approved"),   # includes curator-edited text (FR-16 Edit & Approve)
    ("pending_review", "rejected"),
    ("pending_review", "unsafe"),
    ("approved", "retired"),
    ("approved", "pending_review"),   # FR-19 aging-fix re-confirmation
}

def can_transition(src: str, dst: str) -> bool:
    return (src, dst) in ALLOWED_TRANSITIONS
```
Run → PASS → commit.

- [ ] **8.3 AI pre-screen** `prescreen.py` (FR-15): provider `complete(json_response=True)` with a prompt that evaluates the candidate fix against top retrieved manual chunks and returns `{"hazard_flags": [...categories: electrical|pressure|chemical|gas|lifting...], "contradictions": [...], "missing_safety_steps": [...], "overall_risk": "low|medium|high"}`. Validate JSON (retry once on parse failure, then store `{"error": "prescreen_failed"}` — **a failed pre-screen never blocks the queue and never auto-rejects; it advises humans only** (spec §2.5)). Integration test: a fix text containing "bypass the pressure relief valve" yields ≥1 hazard flag.
- [ ] **8.4 Curation service (TDD, integration):**
  - `review_queue(org_id)` — pending fixes with question, original answer, proposed text, top manual chunks, prescreen report (FR-15's side-by-side payload).
  - `approve(fix_id, curator, edited_text=None)` — guard `can_transition`; guard reviewer role ∈ (curator, admin) (FR-14); **index the fix**: chunk + embed approved text into `chunks` with `source_type='field_fix'`, `fix_id`; write audit event with before/after (FR-18).
  - `reject(fix_id, curator, reason)` / `flag_unsafe(...)` — state + audit + reason stored for submitter visibility.
  - `retire(fix_id, actor, reason)` — state + **delete its chunks rows in the same transaction** (index is the single source of truth, spec §2.4).
  - **The moat test:** approve fix → Phase 4 search for its symptom returns the field_fix chunk ranked above manual content (boost working) → retire → same search no longer returns it.
- [ ] **8.5 Routers:** `GET /curation/queue`, `POST /fixes/{id}/approve|reject|unsafe|retire`. Role guard tests (tech → 403).
- [ ] **8.6 Commit.** Standalone: `pytest tests/curation -v`.

---

## Phase 9 — Keycloak OIDC (replace dev auth)

**Files:** Create `fixmate/api/auth_oidc.py`, `scripts/keycloak_bootstrap.py` (create realm `fixmate`, client, roles tech/curator/admin, org-id user attribute → token claim), `tests/auth/test_oidc.py`.

- [ ] **9.1** `docker compose --profile auth up -d`; bootstrap script creates realm + test users.
- [ ] **9.2 TDD:** `auth_oidc.py` validates Bearer JWT against Keycloak JWKS (cache keys), maps claims → `AuthContext` (same dataclass as Phase 6 — handlers don't change). Tests: valid token passes, expired/garbage rejected (401), missing org claim rejected, role claim maps correctly.
- [ ] **9.3** `deps.py` switches on `DEV_AUTH`; integration test runs one real password-grant flow against local Keycloak. Commit.

---

## Phase 10 — Technician PWA (chat)

**Files:** Create `web/` (Vite + React + TS). Components: `EquipmentPicker`, `ChatView`, `AnswerCard` (safety warnings styled first; confidence chip; numbered steps; inline figures; citation links opening source page; **distinct field-fix verification badge** — spec pitfall table), `EscalationCard` (low-confidence path), `FeedbackBar` ("Did it help?" → No opens fix-submission form with photo attach). PWA: `vite-plugin-pwa` service-worker shell caching. Accessibility: WCAG 2.1 AA, ≥48px touch targets (gloves).

- [ ] **10.1** Scaffold + typed API client (`web/src/api.ts`) matching Phase 6/7 payloads; dev proxy to `:8000`; dev-auth headers injected from `localStorage` (replaced by Keycloak JS adapter when Phase 9 lands).
- [ ] **10.2** Build components against the live local API (vitest component tests for AnswerCard rendering: warnings-first ordering, badge shown only when `source_type=field_fix` citation present).
- [ ] **10.3 Run it standalone:** `cd web; npm install; npm run dev` → ask a question end-to-end against local Ollama. Commit per component.

---

## Phase 11 — Curator/Admin console views

**Files:** Add routes in `web/`: `ReviewQueue` (badge count, FR-14), `ReviewDetail` (side-by-side: question / answer given / proposed fix / manual excerpts / pre-screen advisory; Approve / Edit & Approve / Reject / Flag Unsafe actions — FR-15/16), `DocumentsAdmin` (upload + ingestion status + version list), `EquipmentAdmin`, `UsersAdmin` (role assignment). Route guard by role.

- [ ] **11.1–11.4** TDD per view against live API; verify approve-in-UI → fix appears in technician answers; reject → submitter sees reason. Commit per view.

---

## Phase 12 — Safety evals, answer regression, demo seed

**Files:** Create `fixmate/evals/safety_cases.yaml` (cases: fabricated-spec question, out-of-corpus question must escalate, unsafe-fix submission must be flagged by pre-screen, approved-fix badging accuracy), `fixmate/evals/run.py` (runs cases through `compose_answer`/curation services, prints pass/fail table, nonzero exit on failure), `fixmate/evals/baseline.jsonl` (questions + retrieved_chunk_ids snapshot; rerun and report drift — per backend, never compared across backends, spec §8.4), `scripts/seed_demo.py` (demo org, equipment, ingest fixture manual, one approved fix).

- [ ] **12.1** Implement safety runner + cases (CLAUDE.md §4.3 safety tests). `python -m fixmate.evals.run` → all pass on ollama backend.
- [ ] **12.2** Record regression baseline; wire `pytest -m "not integration"` + evals into CI later.
- [ ] **12.3** `python scripts/seed_demo.py` → 5-minute fresh-machine demo: compose up → seed → web chat answers with citations. Commit.

---

## Appendix A — Cross-phase contracts (do not drift)

1. **`LLMProvider` / `CompletionRequest` / `CompletionResult`** — defined in Phase 2.1, imported everywhere; never bypass the factory.
2. **Embedding dimension = 1024** (BGE-M3) — schema `vector(1024)` (Phase 1) ⇄ `embeddings.py` assertion (Phase 2).
3. **`session_for_org(org_id)`** — the only way application code touches the DB; it sets `app.current_org_id` for RLS. No raw sessions in business logic.
4. **`ScoredChunk`** from `retrieval.service.search` — consumed by composer (5), pre-screen (8).
5. **Fix states:** `submitted | pending_review | approved | rejected | unsafe | retired` — DB constraint (1) ⇄ `states.py` (8) ⇄ API payloads (8) ⇄ UI (11).
6. **`AuthContext(org_id, user_id, role)`** — produced by dev auth (6) and OIDC (9) interchangeably.
7. **Citation marker format `[chunk:<uuid>]`** — emitted by prompts (5), parsed by composer (5), rendered by AnswerCard (10).
8. **Safety constants** (`confidence thresholds 0.70/0.45`, `field-fix boost 1.15`) — change only with Phase 12 eval evidence; each carries a safety-critical comment in code.
