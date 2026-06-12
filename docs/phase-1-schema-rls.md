# Phase 1 — Database schema, migrations, RLS tenancy

**Commit:** `082e504` — `feat: schema + RLS tenant isolation (phase 1)`
**Plan:** [superpowers/plans/2026-06-12-fixmate-mvp.md](superpowers/plans/2026-06-12-fixmate-mvp.md) (Phase 1)
**Date:** 2026-06-12

## What was built

- **`fixmate/core/models.py`** — SQLAlchemy 2 models for all 12 tables: `organizations`, `users`, `equipment_profiles`, `documents`, `chunks`, `figures`, `fixes`, `conversations`, `messages`, `answer_logs`, `feedback`, `audit_events`. Every tenant table carries `organization_id` (CLAUDE.md §4.5). Key contracts:
  - `chunks.embedding vector(1024)` — BGE-M3 dimension, shared contract with Phases 2/3
  - `chunks.tsv tsvector` generated always as `to_tsvector('english', content)` (stemming for hybrid retrieval)
  - Check constraints: user roles (`tech|curator|admin`), fix states (`submitted|pending_review|approved|rejected|unsafe|retired`), chunk source types (`manual|field_fix`), message roles
  - `audit_events.actor_id` has no FK on purpose: audit rows must survive actor deletion (24-month retention)
- **`db/migrations/`** — Alembic (async template) + initial migration `0001`:
  - `CREATE EXTENSION vector`, all tables, HNSW index on embeddings, GIN index on `tsv`
  - RLS **enabled and forced** on every table with a `tenant_isolation` policy on `current_setting('app.current_org_id')::uuid`
  - Creates non-superuser `fixmate_app` role (no BYPASSRLS) with CRUD grants — the role the application connects as
- **`fixmate/core/db.py`** — `session_for_org(org_id)`, the only sanctioned DB entry point. Applies `app.current_org_id` as a transaction-local GUC (`set_config(..., true)`) on every transaction via an `after_begin` listener, so tenant context survives mid-flow commits and can never leak across pooled connections.
- **`fixmate/core/settings.py`** — added `database_app_url` (the `fixmate_app` connection; RLS only bites for non-owner roles). `.env.example` updated to match.
- **`tests/conftest.py`** — `migrated_db` (runs `alembic upgrade head`) and `two_orgs` fixtures.
- **`tests/db/test_rls.py` + `tests/db/test_schema.py`** — cross-tenant read/insert blocking, same-org positive control, table inventory, 1024-dim enforcement, English stemming, state/role constraint rejection. These are the multi-org CI scenario CLAUDE.md §6 demands.

## Verification evidence

TDD sequence followed: tests written first and confirmed failing (`ModuleNotFoundError: fixmate.core.db`), then implementation, then green.

`pytest tests/db -v` — 8/8 pass:

```
tests/db/test_rls.py::test_rls_blocks_cross_tenant_reads PASSED
tests/db/test_rls.py::test_rls_blocks_cross_tenant_insert PASSED
tests/db/test_rls.py::test_same_org_reads_back_its_own_rows PASSED
tests/db/test_schema.py::test_all_tables_exist PASSED
tests/db/test_schema.py::test_chunk_embedding_rejects_wrong_dimension PASSED
tests/db/test_schema.py::test_tsv_is_generated_with_english_stemming PASSED
tests/db/test_schema.py::test_fix_state_constraint_rejects_unknown_state PASSED
tests/db/test_schema.py::test_user_role_constraint PASSED
============================== 8 passed in 3.36s ==============================
```

Verified directly in Postgres:

- `pg_roles`: `fixmate_app` has `rolsuper = f`, `rolbypassrls = f` (RLS cannot be bypassed by the app)
- `pg_class`: all 12 tables show `relrowsecurity = t` **and** `relforcerowsecurity = t`

Migration round-trip verified: `alembic downgrade base` → `alembic upgrade head` → full suite green. (First downgrade attempt exposed a real bug — `DROP ROLE fixmate_app` failed because the role retained privileges on `alembic_version`; fixed with an explicit `REVOKE ALL ON ALL TABLES` in `downgrade()`.)

`ruff check` and `ruff format` clean.
