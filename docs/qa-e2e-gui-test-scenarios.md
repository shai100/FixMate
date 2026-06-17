# FixMate — End-to-End GUI QA Test Scenarios

**Last updated:** June 17, 2026
**Scope:** Full end-to-end QA of the FixMate web GUI (React PWA at `web/`), exercised through the
real local stack (Docker services + FastAPI API + Vite dev server).
**Audience:** Human QA engineers **and** automated AI GUI-testing systems.

---

## 0. How to use this document

This document is written so it can be consumed by either a person or an automated GUI agent
(e.g. a Playwright/Selenium-driven AI). Each test case follows a fixed, machine-parseable shape:

| Field | Meaning |
|-------|---------|
| **ID** | Stable identifier (e.g. `TC-CHAT-01`). Never reuse or renumber. |
| **Title** | One-line human summary. |
| **Priority** | `P0` (safety / blocker), `P1` (core flow), `P2` (secondary), `P3` (cosmetic). |
| **Preconditions** | State that must hold before steps run (role, seed data, current screen). |
| **Steps** | Ordered, deterministic UI actions. Each step is a single user action. |
| **Expected** | Observable post-conditions. Each assertion is independently checkable. |
| **Selectors** | Stable hooks (`data-testid`, `aria-label`, roles, visible text) an automation agent should target. |

**Locator priority for automation agents** (most to least stable):
1. `data-testid` attributes (listed per case where they exist in the code).
2. ARIA roles + accessible names (`aria-label`, `role`, `aria-current`, `aria-pressed`).
3. Associated `<label>` text → form control.
4. Visible button/heading text (exact, case-sensitive).
5. CSS class names — **last resort only** (they are styling, not contracts).

**Determinism rules for automation:**
- Always wait on a state assertion, never a fixed sleep, except where a backend poll is explicitly
  noted (document ingestion).
- The LLM answer **text** is non-deterministic. Never assert exact answer wording. Assert on
  *structure* (a card rendered, a confidence chip present, ≥1 citation, warnings block ordering)
  and on *deterministic seed facts* (e.g. the demo manual mentions error code `E47`).
- Treat every test as independent: each should sign in fresh and not depend on residual state from a
  prior case unless its Preconditions say so.

---

## 1. Environment & test data setup

### 1.1 Bring the system up

Run these once before the suite (see [docs/how_to_run.md](how_to_run.md)):

```powershell
docker compose up -d                       # Postgres, Redis, MinIO, Ollama
docker exec $(docker compose ps -q ollama) ollama pull qwen3:4b
docker exec $(docker compose ps -q ollama) ollama pull bge-m3
uvicorn fixmate.api.main:app --reload      # API on http://localhost:8000
cd web; npm install; npm run dev           # GUI on http://localhost:5173
```

### 1.2 Seed the demo tenant

```powershell
python scripts/seed_demo.py
```

This prints the identifiers the suite needs. Capture them into the variables below; **every test
references these symbolic names, never literal UUIDs:**

| Symbol | Source (printed by seed script) | Notes |
|--------|----------------------------------|-------|
| `ORG_ID` | `organization_id` | The demo tenant. |
| `EQUIPMENT_ID` | `equipment_id` | Maps to **"Pump X"**. |
| `ADMIN_ID` | `admin_id` | Role `admin`. |
| `CURATOR_ID` | `curator_id` | Role `curator`. |
| `TECH_ID` | `tech_id` | Role `tech`. |
| `DOCUMENT_ID` | `document_id` | The ingested Pump X manual. |
| `APPROVED_FIX_ID` | `approved_fix_id` | A pre-approved field fix for error `E47`. |

Known seed facts the suite asserts against (deterministic):
- The demo manual contains **error code `E47`** ("concentrate valve blocked"), a torque spec
  (**`12 Nm`**), and at least **one figure**.
- One **approved field fix** for E47 exists, so an E47 answer should surface a **field-verified** badge.
- The flux-capacitor / out-of-corpus question is the canonical **escalation** trigger.

### 1.3 A second tenant (for isolation tests)

Tenant-isolation cases (`TC-SEC-*`) need a second org with its own data. Create it by running the
seed/equipment flow again for a second organization, or via the API, and capture:

| Symbol | Notes |
|--------|-------|
| `ORG2_ID` | A different organization. |
| `ORG2_USER_ID` | Any user in `ORG2`. |
| `ORG2_EQUIPMENT_ID` | Equipment owned by `ORG2`. |

### 1.4 How the GUI authenticates (important for automation)

The GUI uses **dev-auth header identity** stored in `localStorage`. There are two entry paths:

1. **Auto-login** — if the backend has `DEV_AUTO_LOGIN` enabled, the login screen spins briefly and
   drops straight into the demo tenant **as admin** (no form). The login form will **not** appear.
2. **Manual dev login** — the form asks for Organization ID, User ID, and Role.

An automation agent can sign in as a chosen role in one of two ways:
- Fill the `DevLogin` form (Organization ID + User ID + Role) and click **Continue**, **or**
- Seed `localStorage` directly with the identity object before loading the app (faster, more stable).
  Use the same shape the app stores (`{ orgId, userId, role }`).

> **Automation note:** Because auto-login can bypass the form and always lands as **admin**, tests
> that need a specific role (`tech`/`curator`) should set `localStorage` identity directly, then
> reload — this is deterministic regardless of `DEV_AUTO_LOGIN`.

---

## 2. Role → view routing map

The whole app routes by authenticated role (`web/src/App.tsx`). Automation should assert the correct
shell renders per role:

| Role | Lands in | Top-level marker |
|------|----------|------------------|
| `tech` | Phone-framed Technician app | Bottom `TabBar` with Equipment / Packs / Profile tabs |
| `curator` | Desktop Curation Console | `console-nav` with Review queue / All fixes / Documents / Equipment (no Users) |
| `admin` | Desktop Curation Console | Same as curator **plus** a Users tab |

---

## 3. Authentication & routing tests

### TC-AUTH-01 — Manual dev login as technician
- **Priority:** P1
- **Preconditions:** `DEV_AUTO_LOGIN` off (or `localStorage` cleared and auto-login 404s). App at `/`.
- **Steps:**
  1. Load the app. The sign-in form is shown.
  2. Enter `ORG_ID` into **Organization ID** (`#org`).
  3. Enter `TECH_ID` into **User ID** (`#user`).
  4. Select role **`tech`** in the **Role** select (`#role`).
  5. Click **Continue**.
- **Expected:**
  - The **Continue** button is disabled until both ID fields are non-empty.
  - After submit, the Technician app renders: a bottom navigation bar (`nav[aria-label="Main navigation"]`)
    with **Equipment**, **Packs**, **Profile**.
  - The **Select equipment** screen is the initial screen (`hdTitle` = "Select equipment").
- **Selectors:** `#org`, `#user`, `#role`, button text "Continue", `nav[aria-label="Main navigation"]`.

### TC-AUTH-02 — Dev login as curator routes to console
- **Priority:** P1
- **Preconditions:** As above.
- **Steps:** Sign in with `ORG_ID` / `CURATOR_ID` / role **`curator`**.
- **Expected:**
  - Desktop console renders (`.console`), topbar subtitle contains `CURATION CONSOLE · CURATOR`.
  - Console nav (`nav[aria-label="Console sections"]`) shows **Review queue, All fixes, Documents,
    Equipment** and **does NOT** show a **Users** tab.
- **Selectors:** `nav[aria-label="Console sections"]`, tab text "Users" (must be absent).

### TC-AUTH-03 — Dev login as admin shows Users tab
- **Priority:** P1
- **Preconditions:** As above.
- **Steps:** Sign in with `ORG_ID` / `ADMIN_ID` / role **`admin`**.
- **Expected:** Console renders with subtitle `... · ADMIN`; nav includes a **Users** tab in addition
  to the curator tabs.
- **Selectors:** Console nav tab text "Users" (must be present).

### TC-AUTH-04 — Continue disabled with empty fields
- **Priority:** P2
- **Preconditions:** Login form visible.
- **Steps:** Leave Organization ID and/or User ID empty.
- **Expected:** **Continue** button is `disabled`. No navigation occurs.

### TC-AUTH-05 — Sign out returns to login
- **Priority:** P2
- **Preconditions:** Signed in as `tech`.
- **Steps:** Open **Settings** (gear icon, `aria-label="Settings"`) → tap **Sign out**.
- **Expected:** Identity cleared; the app returns to the dev login screen.
- **Selectors:** `button[aria-label="Settings"]`, row text "Sign out".

### TC-AUTH-06 — Console sign out (curator/admin)
- **Priority:** P2
- **Preconditions:** Signed in as `admin`.
- **Steps:** Click **Sign out** in the console topbar (`.console-signout`).
- **Expected:** Returns to login screen.

### TC-AUTH-07 — Identity persists across reload
- **Priority:** P2
- **Preconditions:** Signed in as `tech`.
- **Steps:** Reload the page.
- **Expected:** App restores the technician session from `localStorage` without re-prompting (unless
  auto-login overrides to admin — note that distinction).

---

## 4. Technician — Equipment selection

### TC-EQUIP-01 — Equipment list loads
- **Priority:** P1
- **Preconditions:** Signed in as `tech`. Demo seeded.
- **Steps:** Observe the **Select equipment** screen.
- **Expected:**
  - A **General** card (no specific equipment) is always present and first.
  - At least one equipment card labelled **"Pump X"** is shown with manufacturer/model meta.
  - While loading, "Loading equipment…" hint shows; it disappears once loaded.
- **Selectors:** card text "General", "Pump X", `input[aria-label="Search equipment"]`.

### TC-EQUIP-02 — Search filters equipment
- **Priority:** P2
- **Steps:**
  1. Type `Pump` into **Search equipment**.
  2. Then type a non-matching string e.g. `zzzzz`.
- **Expected:**
  - With `Pump`, the Pump X card remains.
  - With `zzzzz`, "No equipment matches your search." hint is shown.
- **Selectors:** `input[aria-label="Search equipment"]`, text "No equipment matches your search."

### TC-EQUIP-03 — Selecting equipment opens chat scoped to it
- **Priority:** P1
- **Steps:** Click the **Pump X** card.
- **Expected:**
  - Chat screen opens; header title shows **"Pump X"** and the sub-line shows manufacturer · model.
  - The empty-state hello ("Ask about this unit") and suggestion chips are present.
- **Selectors:** header `.hdTitle` = "Pump X", text "Ask about this unit".

### TC-EQUIP-04 — Selecting "General" opens unscoped chat
- **Priority:** P2
- **Steps:** From equipment screen, click **General**.
- **Expected:** Chat header title shows **"General"**, sub-line "No specific equipment".

### TC-EQUIP-05 — Back from chat returns to equipment list
- **Priority:** P2
- **Steps:** In chat, click the **Back** button (`aria-label="Back"`).
- **Expected:** Equipment selection screen is shown again.

---

## 5. Technician — Chat / Q&A (core RAG flow)

> **LLM non-determinism:** assert structure & seed facts only, never exact wording.

### TC-CHAT-01 — Ask a grounded question, get an AnswerCard with citations
- **Priority:** P0
- **Preconditions:** In chat scoped to **Pump X**.
- **Steps:**
  1. Type `How do I fix error E47?` into the composer (`#question`).
  2. Click **Send** (`button[aria-label="Send"]`).
- **Expected:**
  - The question appears immediately as a user message (`.uMsg`).
  - A typing indicator (`.typing`) shows while the request is in flight.
  - An **AnswerCard** (`article[aria-label="Answer"]`) replaces the indicator.
  - A **confidence chip** is present (`[data-testid="confidence-chip"]`) reading High/Medium/Low.
  - A **Sources** footer lists ≥1 citation (`.citation` items), each badged **Manual** or **Field fix**
    (`[data-testid="citation-source-manual"]` / `[data-testid="citation-source-field_fix"]`).
  - A **FeedbackBar** ("Did it help?") renders under the answer.
- **Selectors:** `#question`, `button[aria-label="Send"]`, `article[aria-label="Answer"]`,
  `[data-testid="confidence-chip"]`, `[data-testid^="citation-source-"]`.

### TC-CHAT-02 — Field-verified fix badge appears for E47
- **Priority:** P0
- **Preconditions:** Demo seed includes an approved field fix for E47.
- **Steps:** Ask `How do I fix error E47?` (as TC-CHAT-01).
- **Expected:**
  - The answer surfaces a **field fix** citation, and the **"Field-verified fix"** badge
    (`[data-testid="fieldfix-badge"]`) is shown in the card meta.
  - The badge is visually distinct from a plain manual citation (spec pitfall: never blur approved
    vs. unapproved trust level).
- **Selectors:** `[data-testid="fieldfix-badge"]`, `[data-testid="citation-source-field_fix"]`.

### TC-CHAT-03 — Safety warnings render first (warnings-first ordering)
- **Priority:** P0
- **Preconditions:** Ask a question whose grounded answer includes a safety/warning line.
- **Steps:** Ask a question that triggers a safety note (e.g. a procedure involving pressure/electrical).
- **Expected:**
  - If the answer contains warning lines, a **Safety** alert block (`section.safety[role="alert"]`,
    `aria-label="Safety warnings"`) renders **above** the answer body (`.answer-card__body`) in DOM order.
  - The block has heading "Safety" and a bulleted list of warnings.
- **Selectors:** `section[aria-label="Safety warnings"]`, heading "Safety". Assert it precedes
  `.answer-card__body` in document order.
- **Note for automation:** This is conditional on content. If the chosen question yields no warnings,
  mark as N/A rather than fail — but a P0 regression is a warning that appears *below* the body.

### TC-CHAT-04 — Out-of-corpus question escalates (does NOT fabricate)
- **Priority:** P0
- **Preconditions:** In chat (any scope).
- **Steps:** Ask `How do I calibrate the flux capacitor?`.
- **Expected:**
  - An **EscalationCard** renders (`article[aria-label="Escalation"]`, `role="alert"`), NOT an AnswerCard.
  - Heading reads **"Not confident enough to answer"**.
  - An **"Escalate to a senior technician"** action button is present.
  - No FeedbackBar (escalation path has none).
- **Selectors:** `article[aria-label="Escalation"]`, text "Not confident enough to answer",
  button text "Escalate to a senior technician".

### TC-CHAT-05 — Suggestion chip sends a question
- **Priority:** P2
- **Preconditions:** Fresh chat (no turns yet).
- **Steps:** Click a suggestion chip (e.g. "What does this error code mean?").
- **Expected:** The chip text is sent as a question; a turn is appended and answered (Answer or
  Escalation card).
- **Selectors:** `.suggChip` buttons.

### TC-CHAT-06 — Composer disabled states
- **Priority:** P2
- **Steps:**
  1. Observe Send button while the input is empty.
  2. Type text, observe Send enabled.
  3. Submit and observe the composer during the in-flight request.
- **Expected:**
  - Send is disabled when input is empty (icon shows `mic`); enabled (icon `send`) when there is text.
  - During an in-flight request, the input and Send button are disabled (no double-submit).
- **Selectors:** `#question[disabled]`, `button[aria-label="Send"][disabled]`.

### TC-CHAT-07 — Multi-turn conversation keeps history
- **Priority:** P1
- **Steps:** Ask two questions in sequence in the same chat.
- **Expected:** Both turns render stacked (each `.chat-turn` has a user message + an answer/escalation).
  The view auto-scrolls to the newest turn.

### TC-CHAT-08 — Figures render when the answer cites a page with a figure
- **Priority:** P1
- **Preconditions:** Ask a question whose retrieved chunk's page has an extracted figure (demo manual
  has ≥1 figure).
- **Expected:** If figures are attached, each renders as a `<figure class="figBox">` with an `<img>`
  and (if present) a `<figcaption>`. Image `alt` is the caption or "Figure on page N".
- **Selectors:** `figure.figBox img`.
- **Note:** Conditional on retrieval; mark N/A if the answer cited no figure page.

### TC-CHAT-09 — Citation shows document title and page
- **Priority:** P2
- **Steps:** Inspect a citation in an AnswerCard Sources list.
- **Expected:** Each citation label reads `<document title>, p.<n>` (page omitted if null). Manual
  citations show a "Manual" badge; field-fix citations show a "Field fix" badge.

### TC-CHAT-10 — API failure surfaces an error, rolls back the turn
- **Priority:** P2
- **Preconditions:** Simulate a backend failure (stop the API, or force a 500 on `ask`).
- **Steps:** Ask a question.
- **Expected:** An error message (`.chatError`) appears, and the optimistic in-flight turn is removed
  (no orphan typing indicator). The composer becomes usable again.

---

## 6. Technician — Feedback & fix submission (the curation feedback loop)

### TC-FB-01 — "Yes, it helped" records positive feedback
- **Priority:** P1
- **Preconditions:** An answered (non-escalated) turn with a FeedbackBar.
- **Steps:** Click **Yes** (`.fbYes`).
- **Expected:** The bar transitions to a thank-you state: "Logged as helpful — thanks!".
- **Selectors:** `.fbYes`, text "Logged as helpful".

### TC-FB-02 — "No" opens the fix-submission form
- **Priority:** P1
- **Steps:** Click **No** (`.fbNo`).
- **Expected:**
  - The `FixSubmitForm` renders: a notice ("Your fix helps the next technician…"), a required
    **What actually fixed it?** textarea (`#fix-text`), an optional **Add photos** control, and
    **Cancel** / **Submit fix for review** buttons.
  - **Submit** is disabled while the textarea is empty.
- **Selectors:** `#fix-text`, label "What actually fixed it?", button text "Submit fix for review".

### TC-FB-03 — Submit a candidate fix → queued for review
- **Priority:** P0
- **Steps:**
  1. Click **No**.
  2. Enter fix text, e.g. `Replaced the concentrate valve and reseated the connector.`
  3. Click **Submit fix for review**.
- **Expected:**
  - Confirmation renders: "Fix submitted for review. A curator verifies it before other technicians
    see it."
  - **Cross-check (P0):** the submitted fix is **NOT** retrievable by technicians until approved —
    asking the same symptom again must not return this unapproved text as a field-verified fix
    (verify in TC-CUR flow that it appears in the curator queue, not in technician answers).
- **Selectors:** text "Fix submitted for review".

### TC-FB-04 — Attach photos to a fix
- **Priority:** P2
- **Steps:** In the fix form, choose one or more image files via **Add photos** (`input[type=file][accept="image/*"]`).
- **Expected:** The control label updates to "N photo(s) attached". Submitting includes the photos
  (base64) in the payload.

### TC-FB-05 — Cancel fix form returns to idle feedback bar
- **Priority:** P3
- **Steps:** Open the fix form, click **Cancel**.
- **Expected:** Returns to the "Did it help?" idle bar.

### TC-FB-06 — Feedback submission failure shows an error
- **Priority:** P2
- **Preconditions:** Force the feedback endpoint to fail.
- **Steps:** Click **Yes** (or submit a fix).
- **Expected:** An error message renders (`.fbError`) and the bar/form returns to an actionable state.

---

## 7. Technician — Secondary screens

### TC-PACKS-01 — Offline packs preview is clearly non-functional
- **Priority:** P3
- **Steps:** Tap the **Packs** tab.
- **Expected:** Header "Offline packs · preview"; an info notice states pack building ships in Phase 2;
  each equipment shows a non-actionable "not downloaded" pack card. (Intentionally a preview — must
  not look like a working feature.)

### TC-PROFILE-01 — Profile shows real identity, placeholder stats
- **Priority:** P3
- **Steps:** Tap the **Profile** tab.
- **Expected:** Shows the signed-in `ORG_ID` and `TECH_ID` under "Identity"; usage stats are dashes
  (`—`), explicitly labelled as Phase 2 — **no fabricated numbers**.

### TC-SET-01 — Text size slider scales the UI
- **Priority:** P2
- **Steps:** Open **Settings**, drag **Text size** (`input[aria-label="Text size"]`) from 100% to 130%.
- **Expected:** The root font-size changes accordingly (document `html` font-size becomes `130%`);
  the slider value label updates.
- **Selectors:** `input[aria-label="Text size"]`.

### TC-SET-02 — Cosmetic toggles flip
- **Priority:** P3
- **Steps:** Toggle **Voice input** and **Notifications** rows.
- **Expected:** Each `switch` toggles its `aria-pressed` state (cosmetic only; no backend effect).

### TC-SET-03 — Settings back button returns to prior tab
- **Priority:** P3
- **Steps:** From Profile, open Settings, click **Back**.
- **Expected:** Returns to the Profile screen (the tab you came from).

---

## 8. Curator/Admin — Review queue & curation (the moat)

### TC-CUR-01 — Review queue lists pending fixes with risk chips
- **Priority:** P0
- **Preconditions:** Signed in as `curator`. At least one fix is `pending_review` (e.g. from TC-FB-03).
- **Steps:** Open the **Review queue** tab (default).
- **Expected:**
  - Heading "Review queue" with a count badge (`[data-testid="queue-badge"]`) equal to the number of
    pending items.
  - Each item shows the originating question and, if the pre-screen produced one, a **risk chip**
    (`[data-testid="risk-<fix_id>"]`) reading "low/medium/high risk".
  - Empty state: "Nothing awaiting review. 🎉" when zero.
- **Selectors:** `[data-testid="queue-badge"]`, `.review-queue__item`, `[data-testid^="risk-"]`.

### TC-CUR-02 — Open a fix → side-by-side review detail
- **Priority:** P0
- **Steps:** Click a queue item.
- **Expected:** `ReviewDetail` (`section[aria-label="Review fix"]`) renders with:
  - Left panel: **Question**, **Answer given**, **Manual excerpts** (or "No supporting manual content").
  - Right panel: an **editable Proposed fix** textarea (`#proposed`), the **AI pre-screen advisory**
    (`[data-testid="prescreen"]`), a **Reason** box, and three actions.
  - The pre-screen note "Advisory only — a human decides…" is present.
- **Selectors:** `section[aria-label="Review fix"]`, `#proposed`, `[data-testid="prescreen"]`.

### TC-CUR-03 — Pre-screen advisory renders risk and findings
- **Priority:** P1
- **Steps:** Open a fix whose pre-screen ran.
- **Expected:** When present, a risk chip (`[data-testid="prescreen-risk"]`) and any **Hazard flags /
  Contradictions / Missing safety steps** lists show. If the pre-screen errored, the advisory shows
  "Pre-screen could not run — review manually." and **never blocks** the action buttons.
- **Selectors:** `[data-testid="prescreen-risk"]`.

### TC-CUR-04 — Approve a fix → it leaves the queue and reaches technicians
- **Priority:** P0
- **Steps:**
  1. Open a pending fix without editing.
  2. Click **Approve**.
- **Expected:**
  - On success, the view returns to the queue and the count badge decrements (item resolved).
  - **Moat cross-check (P0):** as a technician, ask the fix's symptom — the approved text now appears
    as a **field-verified fix** citation (`[data-testid="fieldfix-badge"]`) ranked above manual content.
- **Selectors:** button text "Approve".

### TC-CUR-05 — Edit & Approve relabels the action and stores edited text
- **Priority:** P1
- **Steps:**
  1. Open a pending fix.
  2. Modify the **Proposed fix** textarea (`#proposed`).
- **Expected:**
  - An **"edited"** flag (`[data-testid="edited-flag"]`) appears next to "Proposed fix".
  - The approve button relabels from **Approve** to **Edit & Approve**.
  - Approving stores the edited text (verify the technician sees the edited version).
- **Selectors:** `[data-testid="edited-flag"]`, button text "Edit & Approve".

### TC-CUR-06 — Reject requires a reason
- **Priority:** P0
- **Steps:**
  1. Open a pending fix.
  2. Click **Reject** with the Reason box empty.
- **Expected:** Inline error "A reason is required so the submitter sees why." No state change occurs.
  Filling the reason and re-clicking **Reject** resolves the item.
- **Selectors:** `#reason`, button text "Reject".

### TC-CUR-07 — Flag Unsafe requires a reason and blocks indexing
- **Priority:** P0
- **Steps:** Open a pending fix, click **Flag Unsafe** without a reason, then with a reason.
- **Expected:** Same reason-required guard as reject. After flagging, the fix is `unsafe` and is
  **never** served to technicians.
- **Selectors:** button text "Flag Unsafe".

### TC-CUR-08 — Back to queue without acting
- **Priority:** P3
- **Steps:** In review detail, click **← Back to queue**.
- **Expected:** Returns to the queue unchanged.

### TC-CUR-09 — Refresh reloads the queue
- **Priority:** P3
- **Steps:** Click **Refresh** in the queue header.
- **Expected:** Queue re-fetches; newly submitted fixes appear.

### TC-CUR-10 — Approved fix surfaced then retired disappears (end-to-end moat)
- **Priority:** P0
- **Preconditions:** An approved fix exists (e.g. `APPROVED_FIX_ID` or one approved via TC-CUR-04).
- **Steps:**
  1. As technician, confirm the symptom returns the field-verified fix.
  2. As curator/admin, go to **All fixes**, delete/retire that fix.
  3. As technician, ask the symptom again.
- **Expected:** After retirement the fix is **no longer** returned in technician answers (the index is
  the single source of truth). 

---

## 9. Curator/Admin — All fixes table

### TC-FIX-01 — Fixes table lists all lifecycle states
- **Priority:** P1
- **Steps:** Open **All fixes**.
- **Expected:** A table (`[data-testid="fixes-table"]`) with columns Question/Issue, State, Creator,
  Created, Approved. State shows a chip (`.state-chip--<state>`) for submitted/pending_review/approved/
  rejected/unsafe/retired. Count badge equals row count.
- **Selectors:** `[data-testid="fixes-table"]`.

### TC-FIX-02 — Author a new issue/fix into the review queue
- **Priority:** P1
- **Steps:**
  1. Click **New issue**.
  2. Select equipment, enter a question and proposed fix.
  3. Click **Add to review queue**.
- **Expected:** Form (`form[aria-label="New issue"]`) submits; the new fix appears and is routed to the
  Review queue (subject to pre-screen). Submit is disabled until equipment + fix text are set.
- **Selectors:** button text "New issue", `form[aria-label="New issue"]`, "Add to review queue".

### TC-FIX-03 — Edit a fix's text inline
- **Priority:** P2
- **Steps:** Click **Edit** on a row, change the proposed text, **Save**.
- **Expected:** Row exits edit mode; updated text persists on reload.

### TC-FIX-04 — Delete a fix removes it from retrieval
- **Priority:** P1
- **Steps:** Click **Delete** on an approved fix, confirm the dialog.
- **Expected:** Confirmation dialog: "Delete this fix? It will be removed from retrieval immediately."
  After confirm, the row disappears and the fix no longer appears in technician answers.

---

## 10. Curator/Admin — Documents (ingestion)

### TC-DOC-01 — Upload a PDF and watch ingestion progress
- **Priority:** P0
- **Preconditions:** On the **Documents** tab. A valid PDF available.
- **Steps:**
  1. Select **Equipment** (e.g. Pump X) in the upload form.
  2. (Optional) enter a **Title**.
  3. Choose a PDF in **PDF manual** (`#doc-file`, `accept="application/pdf"`).
  4. Click **Upload & ingest**.
- **Expected:**
  - The form clears and the button re-enables immediately (upload accepted = HTTP 202).
  - A status line (`.console-status`, `role="status"`) cycles through "Queued for ingestion…" →
    "Processing — extracting text, figures, and embeddings…" → "Ingestion complete — manual is now live."
  - On completion, the new document appears in **Version history** marked **live**.
- **Selectors:** `#doc-eq`, `#doc-file`, button text "Upload & ingest", `.console-status`,
  `[data-testid="doc-list"]`.
- **Automation note:** This is the **one** case where polling a backend is expected. Wait on the
  status text "Ingestion complete" with a generous timeout (the SLO is <10 min for a 500-page manual;
  the demo PDF is small — allow up to ~60s). Poll, do not fixed-sleep.

### TC-DOC-02 — Upload disabled until equipment + file chosen
- **Priority:** P2
- **Steps:** Observe **Upload & ingest** with no file and/or no equipment selected.
- **Expected:** Button is `disabled` until both are set.

### TC-DOC-03 — Ingestion failure shows an explicit error
- **Priority:** P1
- **Preconditions:** Upload a corrupt/non-PDF or force a failure.
- **Steps:** Upload the bad file.
- **Expected:** Status clears and an error (`.console-error`, `role="alert"`): "Ingestion failed — the
  file could not be processed. Please try again."

### TC-DOC-04 — Re-uploading a manual versions it (live vs superseded)
- **Priority:** P1
- **Steps:** Upload a second version of an existing manual for the same equipment.
- **Expected:** The newest is badged **live** (`.doc-badge--live`); prior revisions are **superseded**
  (`.doc-badge--superseded`). Version numbers increment (`v1`, `v2`).

### TC-DOC-05 — Download a document
- **Priority:** P2
- **Steps:** Click **Download** on a doc row.
- **Expected:** The auth-gated PDF downloads as a file named after the title (`.pdf` appended if
  missing). No console error.

### TC-DOC-06 — Rename a document
- **Priority:** P2
- **Steps:** Click **Rename**, change the title, **Save**.
- **Expected:** Row shows the new title after reload; **Cancel** discards changes.

### TC-DOC-07 — Delete a document removes it from retrieval
- **Priority:** P1
- **Steps:** Click **Delete**, confirm "Delete "<title>"? It is removed from retrieval immediately."
- **Expected:** Row disappears; its chunks no longer back technician answers.

### TC-DOC-08 — Empty state
- **Priority:** P3
- **Expected:** With no documents, "No documents yet." shows.

---

## 11. Curator/Admin — Equipment management

### TC-EQADM-01 — Create equipment profile
- **Priority:** P1
- **Steps:** On **Equipment** tab, enter **Name** (required), optional Manufacturer/Model, click
  **Add equipment**.
- **Expected:** New row appears in `[data-testid="equipment-list"]`; **Add equipment** disabled until
  Name is non-empty.
- **Selectors:** `#eq-name`, `[data-testid="equipment-list"]`.

### TC-EQADM-02 — Edit equipment
- **Priority:** P2
- **Steps:** Click **Edit** on a row, change fields, **Save**.
- **Expected:** Row reflects updated values; **Cancel** discards.

### TC-EQADM-03 — Manage equipment files (expand)
- **Priority:** P2
- **Steps:** Click **Files** on a row to expand the `[data-testid="equipment-files"]` panel; upload a
  PDF; remove a file.
- **Expected:** Upload queues for ingestion (status "Queued for ingestion (task …)"); files list and
  remove works.

### TC-EQADM-04 — Delete equipment cascades (strong confirmation)
- **Priority:** P1
- **Steps:** Click **Delete**; read the confirmation.
- **Expected:** Dialog warns "Its manuals, indexed content and fixes are removed immediately." On
  confirm the row disappears and its manuals/fixes are gone from retrieval. Cancelling makes no change.

### TC-EQADM-05 — Empty state
- **Priority:** P3
- **Expected:** "No equipment yet." when none exist.

---

## 12. Admin — Users & role management

### TC-USR-01 — Users tab is admin-only
- **Priority:** P0
- **Steps:** Sign in as `curator`; inspect console nav.
- **Expected:** **No Users tab** for curator. Sign in as `admin`: Users tab present. (UI guard on top
  of backend role checks — defense in depth.)

### TC-USR-02 — Create a user
- **Priority:** P1
- **Steps:** In the **Add user** form (`form[aria-label="Add user"]`), enter Name (required), optional
  email, pick a role, click **Add user**.
- **Expected:** New user appears in `[data-testid="user-list"]`.

### TC-USR-03 — Change a user's role (promote tech → curator)
- **Priority:** P0
- **Steps:** Change a tech user's **Role** select to `curator`.
- **Expected:** Update persists (optimistic list update). The promoted user, on next sign-in as
  curator, gains access to the Review queue. (This is the sensitive privilege grant — audited
  server-side.)
- **Selectors:** per-row `select#role-<userId>`.

### TC-USR-04 — Edit user name/email
- **Priority:** P2
- **Steps:** Change a user's name/email; **Save** (enabled only when dirty).
- **Expected:** Updated values persist.

### TC-USR-05 — Delete a user
- **Priority:** P2
- **Steps:** Click **Delete** for a user, confirm "Delete user "<name>"? This cannot be undone."
- **Expected:** Row removed.

---

## 13. Tenant isolation (security — high impact)

> These verify the product's non-negotiable **tenant isolation** through the GUI. A cross-tenant leak
> is catastrophic; treat all as P0.

### TC-SEC-01 — Technician sees only their org's equipment
- **Priority:** P0
- **Preconditions:** `ORG2` exists with its own equipment (`ORG2_EQUIPMENT_ID`).
- **Steps:** Sign in as `tech` in `ORG_ID`. View the equipment list.
- **Expected:** Only `ORG_ID`'s equipment (Pump X etc.) is listed. **`ORG2`'s equipment never appears.**

### TC-SEC-02 — Answers are scoped to the signed-in org
- **Priority:** P0
- **Steps:** As `ORG_ID` tech, ask about content that exists only in `ORG2`'s manuals.
- **Expected:** The system does **not** answer from `ORG2`'s data; it escalates or answers only from
  `ORG_ID` content.

### TC-SEC-03 — Curator queue shows only own-org fixes
- **Priority:** P0
- **Steps:** Sign in as `ORG_ID` curator; open Review queue and All fixes.
- **Expected:** Only `ORG_ID` fixes are listed; no `ORG2` fixes appear.

### TC-SEC-04 — Documents/users lists are org-scoped
- **Priority:** P0
- **Steps:** As `ORG_ID` admin, open Documents and Users.
- **Expected:** Only `ORG_ID` documents and users appear; `ORG2`'s never do.

### TC-SEC-05 — Forged identity cannot read another org's data
- **Priority:** P0
- **Steps (automation, direct):** With the `ORG_ID` session, attempt to load a known `ORG2` resource
  (e.g. open a conversation/document id belonging to `ORG2` via the app's API client).
- **Expected:** The backend returns 404/403 (RLS enforced); the GUI shows an error/empty, never
  `ORG2` content.

---

## 14. Accessibility & responsive (WCAG 2.1 AA, glove-friendly)

### TC-A11Y-01 — Touch targets are glove-sized
- **Priority:** P1
- **Expected:** Primary interactive controls (tab bar buttons, equipment cards, composer Send,
  feedback buttons) are ≥ 48×48px effective hit area.

### TC-A11Y-02 — Landmarks & labels
- **Priority:** P1
- **Expected:** Navigation has accessible names (`nav[aria-label="Main navigation"]`,
  `nav[aria-label="Console sections"]`); icon-only buttons carry `aria-label` (Back, Settings, Send);
  the safety block uses `role="alert"`; the chat log is `aria-live="polite"`.

### TC-A11Y-03 — Keyboard operability
- **Priority:** P2
- **Expected:** All actions reachable and operable by keyboard (Tab/Enter); focus order is logical;
  visible focus indicators present.

### TC-A11Y-04 — Text scaling does not break layout
- **Priority:** P2
- **Steps:** Set text size to 130% (TC-SET-01).
- **Expected:** No clipped/overlapping content; layout holds per the documented 130% support.

### TC-A11Y-05 — Color is not the only signal
- **Priority:** P2
- **Expected:** Confidence, risk, live/superseded, and fix-state are conveyed by text/icon, not color
  alone.

---

## 15. Cross-cutting / regression checklist

| # | Check | Tie to principle |
|---|-------|------------------|
| R1 | No answer ever shows a numeric spec/part number absent from its citations | Groundedness / fabrication detection |
| R2 | Low-confidence answers always escalate (never a confident-looking guess) | Safety gating |
| R3 | Field-verified badge appears **only** when a field_fix source is cited | Approved-fix trust separation |
| R4 | Unapproved fixes never appear in technician answers | Curation moat |
| R5 | Retired/rejected/unsafe fixes immediately leave retrieval | Index is source of truth |
| R6 | No cross-tenant data ever appears in any list or answer | Tenant isolation |
| R7 | Safety warnings always render above the answer body | Warnings-first |
| R8 | Deleting a document/equipment/fix removes it from answers at once | Index sync |
| R9 | Reject/Flag-Unsafe require a reason (submitter visibility) | Audit trail |
| R10 | Curators cannot see the Users tab; only admins manage roles | Role separation |

---

## 16. Suggested automation execution order

1. **Setup:** §1 (services up, seed demo, capture symbols, create ORG2).
2. **Smoke (P0):** TC-AUTH-01/02/03, TC-CHAT-01, TC-CHAT-04, TC-CUR-01, TC-DOC-01.
3. **Core flows (P1):** §4, §5, §6, §8, §9, §10, §11, §12.
4. **Security (P0):** §13 — run with a clean ORG2 dataset.
5. **Accessibility (P1/P2):** §14.
6. **Regression sweep:** §15 table as assertions layered onto the above.

> **Reporting:** For each case emit `{ id, status: pass|fail|n/a, evidence }`. For non-deterministic
> answer cases, evidence is the structural assertions met (card type, chip present, citation count),
> not the answer text.
```

