# Phase 0 — Repo scaffold + local infrastructure

**Commit:** `85351c5` — `feat: compose infrastructure + settings + healthcheck (phase 0)`
**Plan:** [superpowers/plans/2026-06-12-fixmate-mvp.md](superpowers/plans/2026-06-12-fixmate-mvp.md) (Phase 0)
**Date:** 2026-06-12

## What was built

- **`docker-compose.yml`** — local service stack per spec §8.2:
  - `postgres` (`pgvector/pgvector:pg16`) with healthcheck and persistent volume
  - `redis:7` (Celery broker, Phase 3+)
  - `minio` (S3-compatible object storage, console on :9001)
  - `ollama` with NVIDIA GPU passthrough (local LLM backend, spec §8.3)
  - `keycloak` behind the `auth` compose profile — not started until Phase 9
- **`.env.example`** — all runtime configuration knobs (DB/Redis/MinIO URLs, `LLM_PROVIDER=ollama|anthropic` switch, Ollama model names, dev-auth flag). Copied to `.env` locally; `.env` is gitignored.
- **`pyproject.toml`** — `fixmate` package, full dependency set (FastAPI, SQLAlchemy 2 async, Alembic, pgvector, Celery, httpx, anthropic SDK, boto3, PyMuPDF), pytest config with `integration` marker, ruff config.
- **`fixmate/core/settings.py`** — `Settings(BaseSettings)` singleton mirroring `.env.example`.
- **`scripts/healthcheck.py`** — connects to every compose service and prints one status line each; flags missing Ollama models with the exact `ollama pull` command to fix.
- **`tests/conftest.py`** — placeholder for shared fixtures (filled by Phase 1).
- **`.gitignore`** — `.env`, `.venv/`, `web/node_modules/`.

## Verification evidence

`docker compose ps` — all four MVP services up, postgres healthy:

```
fixmate-minio-1      minio/minio              Up
fixmate-ollama-1     ollama/ollama            Up
fixmate-postgres-1   pgvector/pgvector:pg16   Up (healthy)
fixmate-redis-1      redis:7                  Up
```

`python scripts/healthcheck.py` — four OK lines, no `MISSING model` lines (exit criteria met):

```
postgres OK PostgreSQL 16.14 (Debian 16.14-1.pgdg12+1) on x86_64-pc-linux-gnu, ...
redis OK
minio OK
ollama OK, models: ['bge-m3:latest', 'qwen3:4b']
```

Both required models (`qwen3:4b` generation, `bge-m3` embeddings) are pulled and served.
