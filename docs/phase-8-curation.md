# Phase 8 — Curation workflow (the moat)

**Commit:** `feat: curation workflow — state machine + pre-screen + audit + index sync (phase 8)`
**Plan:** `docs/superpowers/plans/2026-06-12-fixmate-mvp.md` §Phase 8 (FR-14–FR-19; spec §2.4–2.5)
**Date:** 2026-06-15

---

## What was built

The human-in-the-loop curation workflow — the approved-fix moat. Curators review pending
candidate fixes (opened in Phase 7), see an AI safety pre-screen advisory, and approve / reject /
flag-unsafe / retire them through a guarded state machine. Approval indexes the fix into the
per-tenant vector index so it becomes retrievable and outranks manual content on symptom match;
retirement deletes those chunks atomically. Every transition is audited.

### Files

- **`fixmate/curation/states.py`** — `ALLOWED_TRANSITIONS` + `can_transition(src, dst)`. The single
  authority on the fix lifecycle (Appendix A.5). Legal edges only:
  `submitted→pending_review`, `pending_review→{approved,rejected,unsafe}`, `approved→retired`,
  `approved→pending_review` (FR-19 aging re-confirmation). Review cannot be skipped; rejected/unsafe
  fixes must be resubmitted, never flipped to approved.
- **`fixmate/curation/prescreen.py`** — `prescreen(fix_text, manual_chunks, provider?)` (FR-15).
  Calls the provider with `json_response=True` and a conservative safety-reviewer prompt; returns a
  normalized advisory `{hazard_flags[], contradictions[], missing_safety_steps[], overall_risk}`.
  On JSON parse failure it retries once, then returns `{"error": "prescreen_failed"}` — **a failed
  pre-screen never blocks the queue and never auto-rejects** (spec §2.5: AI assists, humans approve).
- **`fixmate/curation/service.py`** —
  - `review_queue(org_id)` — pending fixes with question, original answer (from `answer_logs`),
    proposed text, top manual chunks (retrieval, `source_type=manual` only), and the pre-screen.
    The pre-screen is generated **lazily on first view** and persisted to `fixes.ai_prescreen_report`
    (+ a `prescreen` audit row), so it is computed once per fix rather than on every fetch.
  - `approve(org_id, fix_id, curator_id, role, edited_text?)` — guards `can_transition` and reviewer
    role; chunks + embeds the final text (curator edit wins — FR-16) into `chunks` as
    `source_type=field_fix, fix_id=…`; sets `state=approved`, `reviewed_by`, `approved_at`; writes a
    before/after audit row (FR-18). Indexing is what makes the fix part of the moat (spec §2.4).
  - `reject` / `flag_unsafe` — set state + `reviewed_by` + `review_notes` (reason visible to the
    submitter) + audit row.
  - `retire(org_id, fix_id, actor_id, role, reason)` — sets `state=retired` and **deletes the fix's
    `chunks` rows in the same transaction** — the index is the single source of truth, so a retired
    fix vanishes from retrieval immediately.
  - Exceptions: `FixNotFound`, `IllegalTransition`, `NotAuthorized`.
- **`fixmate/api/routers/curation.py`** — `GET /curation/queue` and
  `POST /fixes/{id}/approve|reject|unsafe|retire`. All four guarded by `require_role("curator",
  "admin")` (technician → 403, FR-14). `IllegalTransition` → 409, `FixNotFound` → 404. Org id comes
  from `AuthContext`; RLS hides another tenant's fix, so cross-tenant resolution 404s.
- **`fixmate/api/schemas.py`** — `ReviewItemOut`, `ManualChunkOut`, `ApproveRequest`, `ResolveRequest`.
- **`fixmate/api/main.py`** — registers the two curation routers.
- **`tests/curation/`** — state-machine unit tests, prescreen integration test, service integration
  tests (queue/approve/edit-approve/reject/unsafe/role-guard + the moat test), and API tests.

### Design decisions

- **Lazy, persisted pre-screen.** Phase 7 moves a submission to `pending_review` without running the
  LLM; the pre-screen is generated when a curator first opens the queue and cached on the fix. This
  keeps the negative-feedback hot path cheap and the advisory available exactly when a human needs it.
- **The index is the single source of truth.** Approve writes `field_fix` chunks; retire deletes
  them. Retrieval never filters on fix state — visibility follows directly from chunk existence
  (same invariant Phase 7 relies on for the "never serve an unapproved fix" guarantee).
- **Double role guard (defense in depth).** The router rejects non-reviewers with 403; the service
  re-checks the role and raises `NotAuthorized`, so the lifecycle is safe even if called directly.
- **Pre-screen advises, never decides.** A parse failure degrades to `{"error": "prescreen_failed"}`
  and the fix still appears in the queue — the human decision is never automated away (spec §2.5).

---

## Verification evidence

Full Phase 8 suite (the plan's standalone check, `pytest tests/curation -v`; integration cases hit
live Ollama on the CPU profile):

```
tests/curation/test_curation_api.py::test_tech_forbidden_from_queue PASSED
tests/curation/test_curation_api.py::test_tech_forbidden_from_approve PASSED
tests/curation/test_curation_api.py::test_curator_queue_returns_pending_fix PASSED
tests/curation/test_curation_api.py::test_curator_can_approve PASSED
tests/curation/test_curation_api.py::test_curator_reject_records_reason PASSED
tests/curation/test_curation_api.py::test_illegal_transition_returns_409 PASSED
tests/curation/test_curation_api.py::test_cross_tenant_fix_not_found PASSED
tests/curation/test_prescreen_integration.py::test_unsafe_fix_raises_hazard_flag PASSED
tests/curation/test_service_integration.py::test_review_queue_returns_context_and_prescreen PASSED
tests/curation/test_service_integration.py::test_approve_indexes_field_fix_and_audits PASSED
tests/curation/test_service_integration.py::test_edit_and_approve_persists_curator_text PASSED
tests/curation/test_service_integration.py::test_tech_cannot_approve PASSED
tests/curation/test_service_integration.py::test_cannot_approve_already_rejected PASSED
tests/curation/test_service_integration.py::test_reject_records_reason PASSED
tests/curation/test_service_integration.py::test_flag_unsafe_records_reason PASSED
tests/curation/test_service_integration.py::test_moat_approved_fix_outranks_manual_then_disappears_on_retire PASSED
tests/curation/test_states.py::test_legal_lifecycle PASSED
tests/curation/test_states.py::test_illegal_transitions_blocked PASSED

======================= 18 passed in 157.08s (0:02:37) ========================
```

The moat test (`test_moat_…`) proves the business-critical behaviour end-to-end: approve a fix →
hybrid search for its symptom returns the `field_fix` chunk ranked **first** (boost working) →
retire → the same search no longer returns any field fix.

No regressions in the touched layers (`main.py`, `schemas.py` changes are additive):

```
$ python -m pytest tests/api tests/feedback -v -m "not integration"
20 passed, 6 deselected in 6.94s
```

No new migration, Docker service, or env var: Phase 8 reuses the `fixes` columns from Phase 1
(`ai_prescreen_report`, `reviewed_by`, `review_notes`, `approved_at`) and the existing Ollama
backend for the pre-screen, so `setup-instructions.md` needed only documentation updates (per-suite
test command + a curation workflow section).
