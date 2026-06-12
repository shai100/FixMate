# CLAUDE.md — FixMate Architectural & Development Preferences

**Last updated:** June 2026  
**Status:** Living document — update as architectural decisions evolve

---

## 1. Project Core Values & Decision Framework

**FixMate** is an AI-powered troubleshooting assistant for field technicians, grounded in curated knowledge bases with human-approved field fixes. Every feature decision must uphold these non-negotiable principles:

- **Safety first.** Wrong instructions can harm technicians or damage equipment. Groundedness (≥95% of claims traceable to sources), confidence gating (low-confidence answers always escalate), and human-approved fixes are non-negotiable.
- **Groundedness over capability.** Never fabricate part numbers, torque specs, electrical values, or procedures. If retrieval confidence is low, say so explicitly and offer human escalation.
- **Audit trail.** Every answer, every fix state change, every user action must be logged immutably for 24 months. This is a product feature (debugging) and a liability shield (legal defensibility).
- **Tenant isolation.** Each organization's documents, fixes, and conversations are strictly isolated. Use row-level security (RLS) in PostgreSQL; separate namespaces in vector DB.
- **Approved-fix moat.** The core competitive advantage is field-verified, curated fixes. Indexing approved fixes alongside manual content and ranking them by symptom match is essential to the business model.

When in doubt, ask: **"Could a wrong answer here hurt someone or break equipment?"** If yes, require human review, immutable logging, and citations.

---

## 2. Architecture Principles

### 2.1 RAG Over Fine-Tuning
- **RAG (Retrieval-Augmented Generation)** is the chosen approach for all answer generation.
  - **Why:** Instant customer onboarding (upload PDFs → live today), clean tenant isolation, easy document updates, citable answers. Fine-tuning per customer is slow, expensive, and impossible to audit.
  - **How to apply:** Every answer must trace back to retrieved chunks. Implement retrieval ranking (BM25 + dense vectors), reranking, and explicit citation logic. Store retrieved chunk IDs in the answer log.

### 2.2 Hybrid Retrieval (BM25 + Dense Vector)
- **Why:** Error codes (e.g., "E47"), part numbers, and numeric specs are precisely where pure-vector search fails. Domain precision is critical.
  - **Implementation:** Merge BM25 keyword search results with dense vector search via reciprocal-rank fusion (RRF), then apply a learned or rule-based reranker.
  - **Approval-critical:** Field fixes must boost in retrieval on symptom match; the retrieval layer is where field fixes compete with manual content for ranking.

### 2.3 Image-Aware Ingestion
- During document ingestion, extract all figures/diagrams with bounding boxes.
- Use a vision model (Claude) to caption each figure (e.g., "Fig 12 — concentrate valve location, p.41").
- Index captions alongside text chunks; at answer time, embed image URLs in steps that reference them.
- **Why:** Delivers the "detailed response including images" requirement without OEM copyright friction — the customer supplied the documents under their own license.

### 2.4 Approved-Fix Indexing as Product Feature
- Approved fixes are **embedded into the per-tenant vector index** with `source_type=field_fix` metadata.
- Retrieval boosts field fixes on close symptom match.
- Answer prompt instructs the model to present field fixes with their verification badge (approver, date, linked question).
- Rejection/retirement removes them from the index **immediately** — the index is the single source of truth.
- **Why:** This is how field-verified knowledge becomes the moat. Never serve an unapproved fix to an end user.

### 2.5 Human-in-the-Loop Curation (AI Assists, Humans Approve)
- AI safety pre-screen flags contradictions, missing LOTO/depressurization steps, hazardous-category keywords.
- Output is a **structured advisory** shown to the human curator.
- **Design principle:** AI assists review; humans approve. The human-in-the-loop is a product feature and a liability shield, never a bottleneck to automate away.
- **Corollary:** Never auto-approve fixes. Never remove human review, even as it scales.

### 2.6 Conversation & Answer Logging (Every Answer is Auditable)
- Every answer stores: exact retrieved chunks, chunk IDs, model version, confidence score, citations, timestamp.
- Logs are immutable and retained for 24 months.
- **Why:** Enables regression evaluation, "why did it say that?" investigations, and legal defensibility.

---

## 3. Technology Stack & Rationale

| Layer | Choice | Notes |
|-------|--------|-------|
| **Mobile/Web Client** | React + PWA (Capacitor for iOS/Android later) | One codebase, offline-capable. Glove-friendly touch targets. WCAG 2.1 AA. |
| **Admin Console** | React + shared design system | Ingestion, review queue, analytics, user management. |
| **API** | Python (FastAPI) | FastAPI preferred — pairs well with async ML ingestion code. |
| **Async Workers** | Python + **Celery (Redis broker)** | Chosen over Temporal (spec v1.1): one small container locally. Ingestion, OCR, embedding, offline pack building. Horizontally scalable. |
| **Vector DB** | **pgvector (start) → Pinecone/Weaviate at scale** | pgvector keeps early ops simple inside Postgres; separate namespaces per tenant. |
| **Keyword Search** | **PostgreSQL full-text search** (→ `pg_search`/OpenSearch only at scale) | Hybrid retrieval complement; part of the BM25 + dense vector merge. Same DB, same RLS isolation. |
| **RDBMS** | PostgreSQL with Row-Level Security (RLS) | Tenant isolation, fixes + states, audit logs, user management. |
| **Object Storage** | **MinIO (local/MVP) → AWS S3 (cloud)** | Identical S3 API both ways. Original PDFs, extracted figures, offline packs. |
| **PDF/OCR** | PyMuPDF + Tesseract or cloud OCR; Claude vision for figure captioning | Support scanned manuals (real SMB need). |
| **LLM** | **Dual backend via provider-abstraction layer:** Ollama-served local model (MVP/dev) + **Anthropic Claude** (production) | Answers, vision (photo diagnosis), safety pre-screen. `LLM_PROVIDER=ollama\|anthropic`. Local 4 GB GPU profile: Qwen3-4B Q4 generation, BGE-M3 embeddings on CPU (spec §8.3). Release gates & technician pilots run on Claude. |
| **Auth** | OIDC via **Keycloak**; SAML SSO at Business tier | Chosen over Auth0 (spec v1.1): runs as a local container, no SaaS dependency, no per-MAU pricing. |
| **Infrastructure** | **Docker Compose (local/MVP) → AWS ECS Fargate (cloud)**, IaC (Terraform) | EU + il-central-1 (Tel Aviv) regions for GDPR/IL residency. Full local-PC profile: spec §8. |
| **Observability** | OpenTelemetry + structured answer-quality metrics (groundedness, helpfulness) | Track as first-class SLOs. |

### 3.1 LLM Provider Abstraction
- Implement a provider-agnostic interface for LLM calls (e.g., `AnswerComposer` with pluggable backends).
- **Why:** Protects against cost swings and capability shifts; enables fallback strategies and per-tenant token budgets.
- **Non-negotiable:** Cache frequent answers and multi-turn contexts (use Claude's prompt caching feature on the Anthropic backend; application-level answer caching on the local backend).
- **Backend selection:** `LLM_PROVIDER=ollama` (local MVP/dev, spec §8.3) or `LLM_PROVIDER=anthropic` (production). Claude models are API-only and cannot be self-hosted — the local profile uses open-weight models served by Ollama.

---

## 4. Code Quality & Style

### 4.1 Language & Framework Conventions
- **Python (async workers, ingestion):** Follow PEP 8. Type hints mandatory. Use `async`/`await` for I/O-bound work. Pytest for tests.
- **TypeScript (Node.js / NestJS API):** Strict mode on. ESLint + Prettier. Express or NestJS dependency injection for testability.
- **React:** Functional components + hooks. Reusable component library for both client and admin console.

### 4.2 Error Handling & Validation
- **At system boundaries only:** Validate user input (API requests), external API responses, and file uploads. Reject invalid input early with clear error messages.
- **Internally:** Trust framework guarantees and types. Don't add defensive checks for data that internal code created.
- **LLM output validation:** Always validate that citations exist in retrieved chunks. Enforce groundedness at the API boundary before responding to users.

### 4.3 Testing Strategy
- **Unit tests:** For business logic (retrieval ranking, fix state transitions, safety pre-screen scoring).
- **Integration tests:** Hit a real PostgreSQL instance, real vector DB (or test container), real file storage. Mocks are fragile in this domain.
  - **Rationale:** Ingestion and retrieval are where data-model assumptions live. Mock tests have hidden failures.
- **Answer regression tests:** Store a baseline of answers with retrieved chunks; run new retrievals against the same questions and measure drift.
- **Safety tests:** Verify that low-confidence answers escalate, that unsafe flags block answers, that approved-fix badging is accurate.

### 4.4 Naming & Documentation
- **Default: No comments.** Code should speak for itself via clear names.
- **When to comment:**
  - Non-obvious algorithmic choices (e.g., reciprocal-rank fusion formula for BM25 + vector merge).
  - Hidden constraints (e.g., "chunk size must be < 512 tokens for reranker stability").
  - Workarounds for specific bugs (e.g., "Claude vision sometimes misses captions in rotated PDFs; always rotate to 0° before embedding").
  - Safety-critical decisions (e.g., "This cutoff (0.3) is derived from customer safety review; do not lower without explicit approval").

### 4.5 Database & Data Integrity
- **PostgreSQL RLS:** Tag every table with `organization_id`. Use RLS policies to enforce tenant isolation at the query level, not the application level.
  - **Why:** Defense in depth. Even if application code has a bug, RLS blocks cross-tenant leaks.
- **Audit logging:** Create a dedicated `audit_log` table. Log all state changes (fix lifecycle, user actions, document versions) with actor, entity, action, before/after values, and timestamp.
- **Answer logs:** Store as structured records (not just text blobs). Include `retrieved_chunk_ids[]`, `model_version`, `confidence_score`, `citations[]`, `tokens_used`.

### 4.6 Secrets & Security
- **Never commit secrets.** Use environment variables or a managed vault (HashiCorp Vault, AWS Secrets Manager).
- **LLM API keys:** Store in a vault; rotate monthly.
- **Database credentials:** Use IAM-based auth where possible (AWS RDS IAM, Postgres GCP Cloud SQL auth).
- **Customer data:** Encrypt at rest (AES-256) and in transit (TLS 1.3). Per-tenant deletion within 30 days of request.

### 4.7 Commit Documentation (Build Log)
- **Every commit Claude creates gets a companion markdown file in `docs/`**, included in that commit (or an immediate follow-up), describing what was done and how it was verified.
- **Naming:** `docs/phase-N-<short-name>.md` for plan-phase commits; `docs/<yyyy-mm-dd>-<short-slug>.md` for other commits.
- **Required content:**
  - **Header:** commit hash + message, link to the relevant plan/spec section, date.
  - **What was built** — files created/changed and the design decisions they embody (contracts, constraints, why).
  - **Verification evidence** — the actual commands run and their real output (test results, healthchecks, DB queries). Never claim verification without pasting the evidence; never fabricate output.
- **Why:** an audit trail for engineering decisions, mirroring the product's own auditability value — any engineer can reconstruct what was verified and how.
- Examples: `docs/phase-0-compose-infrastructure.md`, `docs/phase-1-schema-rls.md`.

---

## 5. Decision-Making Patterns

### 5.1 When to Use a New Microservice
- **Only if:** It has a separate scalability profile (e.g., ingestion workers scale independently of the API), a separate deployment cadence, or strong tenant-isolation requirements.
- **Don't create microservices to** "keep things clean" or for hypothetical future use cases. One monolith with async workers is fine until proof of scale argues otherwise.

### 5.2 When to Build vs. Buy
- **Curation workflow & fix lifecycle management:** Build. This is the core moat; you own it end-to-end.
- **Vector DB:** Start with pgvector (keep it simple). Move to managed Qdrant/Pinecone only if ops becomes a bottleneck.
- **Auth/SSO:** Buy (Auth0, Keycloak). Don't homegrow.
- **OCR/Captioning:** Buy cloud OCR (Google Cloud Vision, AWS Textract) for robustness. Use Claude vision for figure captioning (it's excellent at this).

### 5.3 Feature Scope & MVP
- **MVP scope is non-negotiable:** Text Q&A + citations, PDF ingestion, equipment profiles, **full curation workflow** (this is the moat), basic admin, English, feedback loop.
- **Photo diagnosis, voice input, offline packs, advanced analytics:** Phase 2+.
- **Reason:** Curation workflow is where the product earns trust. Don't ship without it.

---

## 6. Tenant Isolation & Multi-Tenancy

- **At the database level:** Every core table (documents, chunks, fixes, conversations) has `organization_id`. Enable PostgreSQL RLS policies.
- **At the vector DB level:** Separate namespaces per tenant. Store `organization_id` in metadata; filter all queries by it.
- **At the API level:** Extract `org_id` from the authenticated user's token. Pass it to all downstream queries. Never trust a query param.
- **In object storage:** Prefix all paths with `org_id/`. Use IAM policies to prevent cross-org bucket access.
- **Regression risk:** Cross-tenant leaks are high-impact. Test multi-org scenarios in CI.

---

## 7. Performance & Observability

### 7.1 Latency SLOs
- **Answer first-token:** < 3 seconds (99th percentile).
- **Full answer:** < 12 seconds on 4G (99th percentile).
- **Ingestion of a 500-page manual:** < 10 minutes.

### 7.2 Metrics to Track
- **Answer quality:** Groundedness (claims traceable to sources), confidence distribution, citation accuracy.
- **Helpfulness:** "Did it help?" ratio, fix-submission rate, approver velocity.
- **Retrieval quality:** Precision@5 (are top 5 results relevant?), reranker lift (does reranking improve results?).
- **Operational:** API response times, ingestion job duration, vector DB query latency, error rates per tenant.

### 7.3 Structured Logging
- Log all requests in structured JSON format (timestamp, trace ID, actor, organization, action, duration, result).
- Include answer metadata in logs: retrieved chunk IDs, reranker score, model tokens, groundedness check outcome.
- Forward logs to a managed observability platform (Datadog, New Relic, or OpenTelemetry collector).

---

## 8. Safety & Compliance

### 8.1 Safety as a Feature, Not an Edge Case
- **Safety warnings cannot be disabled** at any pricing tier.
- **Low-confidence answers must always offer escalation** to a senior technician or admin.
- **Fabrication detection:** Post-process every answer to verify that numeric claims (torque specs, pressures, electrical values) and part numbers are present in the retrieved chunks. Reject if not found.

### 8.2 Audit & Legal Defensibility
- **Immutable answer logs:** Every answer is logged with retrieved sources, model version, and exact output. Retained 24 months.
- **Approval & rejection trail:** Every fix state change (submit → review → approve/reject) includes actor, reason, timestamp, before/after content.
- **Terms of Service:** Position FixMate as "decision support," not a replacement for OEM manuals or technician judgment. Clear liability limitations.

### 8.3 Data Residency & Privacy
- **GDPR compliance:** Support data-residency controls (EU region). Per-tenant deletion within 30 days of request.
- **Customer data never trains shared models.** Each organization's documents and fixes are siloed.

---

## 9. Deployment & Infrastructure

### 9.1 CI/CD Pipeline
- **Every commit:** Run unit tests, linters, type checks.
- **Every PR:** Run integration tests, answer regression tests (if applicable), security scanning (Semgrep, dependency checks).
- **Before merge:** Manual code review, approval from a senior engineer.
- **Releases:** Tag releases in git. Deploy via IaC (Terraform) to staging, run smoke tests, then production.

### 9.2 Rollout Strategy
- **Feature flags:** Use feature flags for risky changes (new retrieval algorithm, UI overhauls). Roll out to 5% → 25% → 100% of users.
- **Database migrations:** Expand-contract pattern. Add columns in one release, backfill in the next, drop old columns in a third.
- **Backward compatibility:** Never break API contracts without a deprecation period (2 releases, announced in release notes).

---

## 10. Common Pitfalls to Avoid

| Pitfall | Why It Matters | How to Prevent |
|---------|---|---|
| **Fabricated specs in answers** | Safety issue + loss of trust | Post-process all numeric claims; log retrieved chunks; integrate CI tests for groundedness. |
| **Approving unsafe fixes without pre-screen** | Liability + harm to technicians | Run AI safety pre-screen on every fix; display it to curators. Never skip. |
| **Mixing approved & unapproved fixes in responses** | Confuses end users about trust level | Use distinct visual badge. Strict separation in indexing logic. |
| **Slow curation queue** | Kills the approved-fix feedback loop | Measure approver velocity as an SLO. Alert if > 24h average. |
| **Cross-tenant data leak** | Catastrophic for trust & compliance | Test multi-org scenarios in CI. Use RLS + separate DB namespaces. |
| **Poor offline support** | Field technicians have spotty connectivity | Offline packs (Phase 2) are essential; plan for them now. |
| **Ignoring document versioning** | Old answers cite outdated procedures | Track document versions; flag superseded revisions in answers. |
| **Weak image extraction from PDFs** | Skipped the "detailed response including images" requirement | Invest in robust figure extraction. Test on scanned PDFs. |

---

## 11. Working with Claude (This Agent)

### When to Ask for Help
- **Architecture questions:** "Should we build X as a microservice or part of the monolith?"
- **Code reviews:** "Is this retrieval logic correct?" or "Does this violate tenant isolation?"
- **Debugging:** "Why is this chunk not being retrieved?" — Provide logs, retrieval queries, expected vs. actual results.
- **Safety scenarios:** "Does this answer expose a safety risk?" — Provide the answer text and manual excerpt.

### Preferred Workflow
1. **State the goal:** "Implement the safety pre-screen for fix curation."
2. **Provide context:** Link to the spec (Section 3.4), the data model (Section 5.4), and any relevant code.
3. **Ask the question:** "Should the pre-screen be a separate API call or part of the fix-submission handler?"
4. **Include constraints:** "We want it to complete in < 2s" or "It must work offline."

### What Claude Assumes
- You understand the product (read the spec in `docs/fixmate-product-spec.md`).
- You've checked `CLAUDE.md` before asking architecture questions.
- You have git history available (use `git log` to see prior decisions).
- You're comfortable with async/concurrent code.

---

## 12. Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-12 | Initial | Document created; captured product spec, architecture, and development norms |
| 2026-06-12 | Spec v1.1 | Resolved open stack options (Celery, Postgres FTS, Keycloak, MinIO→S3, Compose→ECS Fargate); LLM layer made dual-backend (local Ollama model for MVP on 4 GB GPU, Claude for production); local-PC deployment profile added as spec §8 |
| 2026-06-12 | Build log | Added §4.7: every commit gets a companion `docs/` markdown file with "What was built" + "Verification evidence" |

---

**Last Updated:** June 12, 2026  
**Next Review:** When next major component is added or architectural assumption shifts
