# Phase 11 — Curator / Admin console views

**Plan:** `docs/superpowers/plans/2026-06-12-fixmate-mvp.md` §Phase 11 (lines 542–546)
**Date:** 2026-06-16
**Status board target:** Phase 11 → ☑ (`npm run dev`, role=curator)

---

## What was built

Phase 11 adds the curator/admin console to the existing React PWA (`web/`, Phase 10).
Role decides the route: a `tech` keeps the chat flow; a `curator`/`admin` lands in the
console. Two small backend read/write endpoints were added so the admin views talk to a
real API rather than placeholders.

### Backend (FastAPI)

- **`GET /documents`** — `fixmate/api/routers/documents.py`. Lists the tenant's documents
  newest-first with `version` and `superseded_by`, backing the DocumentsAdmin version
  history (FR-9). RLS scopes the query to the caller's org.
- **`fixmate/api/routers/admin.py`** (new router, mounted in `main.py`):
  - **`GET /admin/users`** — admin-only list of users in the org.
  - **`POST /admin/users/{id}/role`** — admin-only role assignment (FR-14). Validates the
    role against `ROLES`, writes an `audit_events` row (before/after), returns the updated
    user. Cross-tenant ids read as 404 (RLS), never a leak.
- **Schemas** — `DocumentOut`, `UserOut`, `SetRoleRequest` in `fixmate/api/schemas.py`.

Role guarding reuses the existing `require_role(...)` dependency (Phase 8); user/role
management is `require_role("admin")`. The org id always comes from the auth context,
never a query param (CLAUDE.md §6).

### Frontend (`web/src`)

- **`components/Console.tsx`** — console shell with role-guarded tabs. The **Users** tab
  is rendered only for `admin`; curators see Review queue / Documents / Equipment.
- **`components/ReviewQueue.tsx`** — pending-fix list with a badge count; clicking an item
  opens the detail view. Refresh + empty state.
- **`components/ReviewDetail.tsx`** — side-by-side review (FR-15/16): question, answer
  given, manual excerpts, editable proposed text, and the AI pre-screen advisory. Actions:
  Approve / **Edit & Approve** (sends `edited_text` only when the text changed) / Reject /
  Flag Unsafe. Reject and Flag Unsafe require a reason. The pre-screen is rendered as
  **advisory only** — it never gates the buttons, and a failed pre-screen shows a
  "review manually" note while Approve stays enabled (spec §2.5 / CLAUDE.md §2.5).
- **`components/DocumentsAdmin.tsx`** — upload a PDF (multipart) + ingestion task status +
  version history with live/superseded badges (FR-8/9).
- **`components/EquipmentAdmin.tsx`** — list + create equipment profiles (FR-10).
- **`components/UsersAdmin.tsx`** — list users, change role via a select (admin-only view).
- **`App.tsx`** — routes curators/admins to `<Console>`; techs keep the Phase 10 flow.
- **`api.ts` / `types.ts`** — added the curation/admin/documents methods and types;
  `request()` now skips the JSON `Content-Type` for `FormData` so uploads keep their
  multipart boundary; `requestVoid()` handles the 204 curation actions.
- **`vite.config.ts`** — dev proxy extended with `/curation`, `/fixes`, `/admin`.
- **`styles.css`** — console layout, risk chips, pre-screen panel, doc/version badges.

### Cross-phase contracts honored (Appendix A)

- Fix states (A.5) and `source_type` field-fix badging drive the queue/detail UI.
- `AuthContext` role (A.6) is the single source for route guarding, client and server.

---

## Verification evidence

### Backend tests (new endpoints) — PASS

```
$ .venv/Scripts/python.exe -m pytest tests/api/test_admin.py -v
tests/api/test_admin.py::test_admin_lists_users PASSED                   [ 16%]
tests/api/test_admin.py::test_non_admin_forbidden_from_users PASSED      [ 33%]
tests/api/test_admin.py::test_admin_sets_role_and_audits PASSED          [ 50%]
tests/api/test_admin.py::test_set_role_rejects_unknown_role PASSED       [ 66%]
tests/api/test_admin.py::test_set_role_cross_tenant_is_404 PASSED        [ 83%]
tests/api/test_admin.py::test_documents_list_is_tenant_scoped PASSED     [100%]
============================== 6 passed in 4.80s ==============================
```

These cover: admin lists users, non-admins get 403, role assignment succeeds + the
promoted tech can then reach `/curation/queue`, unknown role → 422, cross-tenant role
change → 404 (RLS), and `/documents` listing is tenant-scoped.

### Frontend static check

This machine has **no Node/npm installed** — only a Playwright-bundled standalone
`node.exe v24.11.1` (no `npm`, no `corepack`). The vitest suite and `tsc` therefore could
**not** be executed here. As a partial check, the pure-TS modules were parsed with node's
native type-stripping (no JSX):

```
$ node --experimental-strip-types --check web/src/types.ts  → PARSE OK
$ node --experimental-strip-types --check web/src/api.ts     → PARSE OK
$ node --experimental-strip-types --check web/src/auth.ts    → PARSE OK
```

The `.tsx` components and their vitest tests were authored against the Phase 10 patterns
(`AnswerCard.test.tsx`) and are ready to run. On a machine with Node ≥ 20:

```bash
cd web
npm install
npm run test     # Console role-guard, ReviewQueue, ReviewDetail, UsersAdmin + Phase 10
npm run build    # tsc strict + production build
```

Tests authored this phase:
- `Console.test.tsx` — Users tab hidden from curators, shown to admins.
- `ReviewQueue.test.tsx` — badge count, opens detail, empty state.
- `ReviewDetail.test.tsx` — pre-screen advisory render, approve vs Edit & Approve payload,
  reject requires a reason, failed pre-screen never gates approval.
- `UsersAdmin.test.tsx` — role change calls `setUserRole` and reflects the new role.

**Note for the reviewer:** to flip the Phase 11 status-board box to ☑, run the two
`web/` commands above on a Node-equipped machine; the backend half is verified above.
