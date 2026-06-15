# Phase 10 — Technician PWA (chat)

**Commit:** _(this commit)_ — `feat: technician PWA — chat, answer card, feedback + fix submission (phase 10)`
**Plan:** `docs/superpowers/plans/2026-06-12-fixmate-mvp.md` §Phase 10 (Appendix A.5/A.7; CLAUDE.md §3 client, §3.3)
**Date:** 2026-06-15

---

## What was built

The technician-facing Progressive Web App (`web/`): a React + Vite + TypeScript chat client that
talks to the Phase 6/7 API and renders grounded answers with the safety affordances the spec
demands. No API code changed — the PWA consumes the existing contracts.

### Files

- **`web/package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`** — Vite + React + TS
  scaffold. Strict TypeScript (`noUnusedLocals`/`noUnusedParameters`, `strict`). `vite-plugin-pwa`
  in `generateSW` mode caches **only the app shell** (`globPatterns: js/css/html/svg`) — answers
  are never cached because groundedness and freshness require a live API round-trip. Dev proxy
  forwards `/conversations`, `/equipment`, `/messages`, `/documents`, `/health` to `:8000`.
- **`web/src/types.ts`** — mirrors `fixmate/api/schemas.py`. `Confidence = "high"|"medium"|"low"`,
  `SourceType = "manual"|"field_fix"` (Appendix A.5/A.7).
- **`web/src/auth.ts`** — dev-auth identity in `localStorage`; `authHeaders()` emits
  `X-Org-Id`/`X-User-Id`/`X-Role` (Phase 6.1). Documented swap point for the Keycloak JS adapter
  (Phase 9 on the client) — only this module changes, call sites stay put.
- **`web/src/api.ts`** — typed fetch client: `listEquipment`, `createConversation`, `ask`,
  `submitFeedback`. Surfaces FastAPI `detail` strings via `ApiError`.
- **`web/src/components/AnswerCard.tsx`** — the safety-critical view:
  - **Safety warnings rendered first**, in a dominant red `role="alert"` block, regardless of
    where they appear in the answer body (spec pitfall: warnings-first presentation).
  - **Confidence chip** colour-coded by band.
  - **Distinct field-fix badge** ("✓ Includes field-verified fix") shown *only* when a citation
    has `source_type=field_fix`, plus a per-citation source badge — never blurring approved field
    knowledge with manual content (spec §2.4 / pitfall table).
  - Inline figures with accessible `alt` text; per-claim source list.
- **`web/src/components/EscalationCard.tsx`** — the low-confidence path (FR-4): shows the
  "don't know" body, nearest sections, and an explicit escalate action. Never dressed up as a
  confident answer.
- **`web/src/components/FeedbackBar.tsx` + `FixSubmitForm.tsx`** — "Did it help?" (FR-13). "No"
  opens the candidate-fix form (FR-12) with photo attach (base64 data URLs → `photos[]`); on
  submit the user sees that a curator must verify it before it reaches other technicians.
- **`web/src/components/EquipmentPicker.tsx`** — equipment profile selection (FR-10).
- **`web/src/components/ChatView.tsx`** — conversation orchestration: creates a conversation
  scoped to the equipment, sends questions with optimistic "Thinking…" turns, routes each answer
  to `AnswerCard` (with `FeedbackBar`) or `EscalationCard` based on `escalated`.
- **`web/src/components/DevLogin.tsx` + `App.tsx`** — dev identity entry → equipment pick → chat.
- **`web/src/styles.css`** — dark, high-contrast theme; **≥48px touch targets** (`--touch`,
  WCAG 2.1 AA 2.5.5 — glove-friendly); warnings/field-fix/confidence colour tokens.
- **Tests** `AnswerCard.test.tsx`, `EscalationCard.test.tsx` (vitest + Testing Library, jsdom):
  warnings-first DOM ordering, field-fix badge shown only with a `field_fix` citation, confidence
  band, figure alt text, escalation action.

---

## Verification evidence

Node.js was not installed on the machine; installed via winget (`OpenJS.NodeJS.LTS`, v24.16.0).

### `npm install`

```
added 447 packages, and audited 448 packages in 45s
```

### `npm run test` (vitest)

```
 ✓ src/components/AnswerCard.test.tsx (4 tests) 99ms
 ✓ src/components/EscalationCard.test.tsx (1 test) 149ms

 Test Files  2 passed (2)
      Tests  5 passed (5)
```

### `npm run build` (tsc strict + vite build + PWA)

```
✓ 40 modules transformed.
dist/registerSW.js              0.13 kB
dist/manifest.webmanifest       0.24 kB
dist/index.html                 0.58 kB │ gzip:  0.34 kB
dist/assets/index-DaDSHYuB.css  3.10 kB │ gzip:  1.12 kB
dist/assets/index-cXLae4Tp.js   152.61 kB │ gzip: 49.13 kB
✓ built in 870ms

PWA v0.20.5
mode      generateSW
precache  5 entries (152.79 KiB)
files generated
  dist/sw.js
  dist/workbox-9c191d2f.js
```

### `npm run dev` (standalone check — plan §10.3)

Port 5173 is in a Windows reserved range (EACCES on `::1`); started on 127.0.0.1:8123 instead.

```
HTTP 200
ROOT DIV PRESENT
ENTRY SCRIPT PRESENT
```

The dev server boots and serves the app shell with the React entry point. End-to-end Q&A
against the live local API/Ollama requires the compose stack + a seeded org (Phase 12
`seed_demo.py`); the UI is wired to the verified Phase 6/7 contracts.
