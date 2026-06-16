# Build log — Dev auto-login, full admin access, fix & user management

**Date:** 2026-06-16
**Commit:** _(to be filled on commit)_ — "feat: dev auto-login + admin user/fix management"
**Relates to:** CLAUDE.md §6 (tenant isolation / identity from token), §2.4–2.5 (approved-fix
moat, human-in-the-loop), §4.5/§8.2 (audit logging); Phase 8 (curation) and Phase 11
(curator/admin console).

## What was built

Four requested capabilities, all gated on the authenticated identity and audited.

### 1. Dev auto-login as admin (config key)
- `fixmate/core/settings.py`: new `dev_auto_login` (default `false`) and `dev_demo_org`
  (default `"FixMate Demo"`). Honoured only alongside `dev_auth`.
- `fixmate/api/routers/dev.py` (new): `GET /dev/auto-login`. Returns `404` unless both
  `dev_auth` **and** `dev_auto_login` are on. Resolves the demo org on the owner connection
  (bootstrap operation outside any tenant context, mirroring `ingestion.registry`) and
  provisions/reuses an admin user "Auto Admin". `main._guard_auth_config()` already forbids
  `DEV_AUTH=true` outside `ENV=local`, so this is unreachable in a real deployment.
- Web: `DevLogin.tsx` calls `api.devAutoLogin()` on mount; on success it stores the identity
  and routes straight into the admin console, on `404` it falls back to the manual form.

### 2. Admin full access as creator
- Admins already reach the console and pass the `require_role("curator","admin")` reviewer
  guard. This change extends that surface: admins (and curators) can now create/edit/delete
  fixes, and admins get full user management — so "admin" is a true superset creator role.

### 3. Review queue / all-fixes management
- `fixmate/curation/service.py`: `list_fixes` (all states, with submitter/reviewer names),
  `create_fix` (curator/admin opens a candidate fix → `pending_review`, never auto-indexed),
  `update_fix` (edits text/question; **re-indexes field_fix chunks when the fix is approved**
  so the moat/index stays the single source of truth), `delete_fix` (row delete cascades its
  chunks; audit row written before deletion). Indexing was factored into `_index_fix_text`,
  reused by `approve`.
- `fixmate/api/routers/curation.py`: `GET /curation/fixes?state=`, `POST /fixes`,
  `PATCH /fixes/{id}`, `DELETE /fixes/{id}` (all reviewer-guarded).
- Web: `FixesAdmin.tsx` (new) — an "All fixes" console tab showing a table with question,
  state chip, creator, created date, approved date, plus New issue / Edit / Delete. Approve
  & reject still flow through the AI-pre-screened review queue.

### 4. Full user management
- `fixmate/api/routers/admin.py`: `POST /admin/users`, `PATCH /admin/users/{id}`,
  `DELETE /admin/users/{id}` (admin-only). Every change is an `AuditEvent`. Self-deletion is
  rejected (409) to avoid orphaning the tenant.
- Web: `UsersAdmin.tsx` rewritten with an add-user form and per-row name/email edit, role
  select, and delete.
- Demo seed: `evals/fixtures.build_demo_tenant` now provisions an "Auto Admin" admin user
  (reconciling with the auto-login endpoint); `DemoTenant.admin_id` and `seed_demo.py` output
  updated.

No DB migration required — all columns already existed.

## Verification evidence

Backend integration tests (real Postgres) + lint:

```
$ .venv/Scripts/python.exe -m pytest tests/curation/test_service_integration.py tests/api/test_admin.py tests/curation/test_curation_api.py -q
.....................                                                     [100%]
21 passed in 85.68s (0:01:25)

$ .venv/Scripts/python.exe -m ruff check fixmate/ scripts/
All checks passed!
```

Web build, typecheck, eslint, unit tests:

```
$ npm run -s build
✓ 36 modules transformed.
✓ built in 241ms

$ npx tsc --noEmit
(no output — clean)

$ npm run -s lint
(no output — clean)

$ npx vitest run
 Test Files  6 passed (6)
      Tests  16 passed (16)
```
