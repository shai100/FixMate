# Phase 7 — Feedback + candidate-fix submission

**Commit:** `feat: feedback + candidate-fix submission (phase 7)`
**Plan:** `docs/superpowers/plans/2026-06-12-fixmate-mvp.md` §Phase 7 (FR-12, FR-13; spec §2.4–2.5)
**Date:** 2026-06-15

---

## What was built

The "Did it help?" loop that closes the technician → curator feedback cycle. A single
endpoint records the helpfulness signal and, on a negative signal, opens a candidate fix
that enters the curation queue — never indexed, never served until a human approves it.

### Files

- **`db/migrations/versions/0002_chunk_positive_signals.py`** — adds
  `chunks.positive_signals integer not null default 0`. This is FR-13's reinforcement
  counter, stored now and consumed by ranking later.
- **`fixmate/core/models.py`** — `Chunk.positive_signals` mapped column (matches the migration).
- **`fixmate/feedback/service.py`** — `record_feedback(org_id, message_id, user_id, helped, fix_text?, photos?)`:
  - `helped=True` → a `feedback` row; increments `positive_signals` on the chunks the
    answer **cited** (read from `answer_logs.citations`, not the full retrieved set — the
    technician acted on what was shown).
  - `helped=False` + `fix_text` → a `feedback` row **and** a `fixes` row created in state
    `submitted` (linked to question text, answer log, equipment, submitter), then advanced
    immediately to `pending_review` with an `audit_events` row (`before/after` state). The
    fix text is **not** chunked/embedded, so it cannot be retrieved (spec §2.4 — never serve
    an unapproved fix).
  - `helped=False` with no `fix_text` → feedback row only.
  - Guards: unknown message → `MessageNotFound`; a fix on an equipment-less conversation →
    `EquipmentRequired` (a candidate fix must attach to equipment to be reviewable/indexable).
- **`fixmate/api/routers/feedback.py`** — `POST /messages/{id}/feedback`; maps the two service
  exceptions to 404/422. Org id comes from `AuthContext`, never a param (CLAUDE.md §6); RLS
  hides another tenant's message, so cross-tenant feedback 404s.
- **`fixmate/api/schemas.py`** — `FeedbackRequest` / `FeedbackOut`.
- **`fixmate/api/main.py`** — registers the feedback router.
- **`tests/feedback/`** — service tests (DB, fast), API tests (ASGI), and one
  `@pytest.mark.integration` test proving a submitted fix never surfaces in Phase 4 search.

### Design decisions

- **Submitted fixes are invisible by construction, not by filtering.** Retrieval reads only
  the `chunks` table; a pending fix is a `fixes` row with no chunk, so the "not retrievable"
  guarantee holds without any source-state filter in the hot path. The Phase 8 approve step is
  what writes the `field_fix` chunk.
- **Immediate `submitted → pending_review` transition with an audit event** realises "AI
  assists, humans approve" (spec §2.5): submissions land in the queue, never auto-approved.
- **Reinforce cited, not retrieved, chunks** — the signal reflects the answer the technician
  saw and confirmed.

---

## Verification evidence

Migration applied:

```
$ python -m alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, chunks.positive_signals reinforcement counter (phase 7)
```

Phase 7 suite (the plan's standalone check, `pytest tests/feedback -v`):

```
tests/feedback/test_feedback_api.py::test_positive_feedback_endpoint PASSED
tests/feedback/test_feedback_api.py::test_negative_feedback_with_fix_endpoint PASSED
tests/feedback/test_feedback_api.py::test_cross_tenant_message_404 PASSED
tests/feedback/test_feedback_service.py::test_helped_records_feedback_and_reinforces_cited_chunks PASSED
tests/feedback/test_feedback_service.py::test_not_helped_with_fix_text_opens_pending_review_fix PASSED
tests/feedback/test_feedback_service.py::test_submitted_fix_is_not_indexed_so_never_retrievable PASSED
tests/feedback/test_feedback_service.py::test_not_helped_without_fix_text_records_feedback_only PASSED
tests/feedback/test_feedback_service.py::test_unknown_message_raises PASSED
tests/feedback/test_feedback_service.py::test_fix_without_equipment_is_rejected PASSED
tests/feedback/test_fix_not_retrievable_integration.py::test_submitted_fix_never_surfaces_in_retrieval PASSED

============================= 10 passed in 17.33s =============================
```

No regressions in schema/API (model change is additive):

```
$ python -m pytest tests/db tests/api -m "not integration" -q
19 passed, 5 deselected in 17.38s
```

Lint clean:

```
$ python -m ruff check fixmate/feedback fixmate/api/routers/feedback.py tests/feedback
All checks passed!
```
