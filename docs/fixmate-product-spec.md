# FixMate — Product Specification & System Architecture
**Version 1.1 · June 2026 · Status: Draft for review**

> **v1.1 changes:** Resolved open technology options to single choices (§5.3), made the LLM provider layer explicitly dual-backend (local model for MVP development, Anthropic Claude for production), and added §8 — a local-PC deployment profile (Docker Compose) that runs the entire infrastructure, including a locally hosted LLM on a 4 GB GPU, before any cloud deployment.

---

## 1. Project Definition (updated)

FixMate is an AI-powered troubleshooting assistant that allows a field technician — or any person dealing with a specific equipment system — to ask questions in natural language about how to fix a product or problem, and receive a detailed, step-by-step response including images, diagrams, and links to the relevant source documentation.

The system is grounded exclusively in a curated knowledge base composed of (a) uploaded technical documents (service manuals, bulletins, wiring diagrams, parts catalogs) and (b) **field-verified fixes** contributed by technicians and **approved by a senior technician or administrator before becoming authoritative**, so that a single wrong or unsafe entry can never mislead the team. Every answer cites its sources, displays a confidence level, and surfaces safety warnings first. Over time, the approved-fix loop turns each customer's private knowledge base into a growing, self-improving asset — the product's core moat.

Target customers: SMB and mid-market field-service companies (5–200 technicians) and equipment OEMs who white-label the assistant for their dealer/service networks.

---

## 2. Personas & Roles

| Role | Description | Key permissions |
|---|---|---|
| **Technician** | Field worker on a job site, often on mobile, sometimes offline | Ask questions, view answers/sources, give feedback, submit fixes |
| **Senior Tech / Curator** | Experienced technician designated as knowledge reviewer | All technician rights + review/approve/edit/reject submitted fixes |
| **Admin** | Service manager or owner | All curator rights + manage users, equipment profiles, documents, analytics, billing |
| **OEM Knowledge Manager** | (White-label tier) manages the OEM's master knowledge base | Publish documents/fixes to the entire dealer network |
| **End customer** (optional) | Equipment owner using a limited self-service mode | Ask questions against a restricted, customer-safe knowledge subset |

---

## 3. Functional Requirements

### 3.1 Ask & Answer (core loop)
- **FR-1** Technician selects an equipment profile (or scans a QR/nameplate photo to auto-identify model and serial) and asks a question via text or voice.
- **FR-2** The system retrieves relevant passages, images, and diagrams from the equipment's knowledge base and generates a structured answer: plain-language diagnosis, ordered repair steps with specific values/specs, safety warnings (always first), required parts with part numbers, and follow-up suggestions.
- **FR-3** Every answer displays: (a) a **confidence level** (high / medium / low) derived from retrieval quality; (b) **source citations** linking to the exact document page; (c) inline **images and diagrams** extracted from the source documents (exploded views, wiring schematics, figures), rendered next to the step that references them.
- **FR-4** If retrieval confidence is below threshold, the system explicitly says it doesn't know, shows the nearest related manual sections, and offers an "escalate to senior tech" action. The system never fabricates procedures, part numbers, or torque/pressure/electrical values.
- **FR-5** Multi-turn conversation: follow-ups retain context ("the pressure is still high after cleaning").
- **FR-6** Photo-based diagnosis: technician uploads a photo (error screen, nameplate, damaged part); the system uses it to identify the equipment/error and refine retrieval.
- **FR-7** Multilingual: questions and answers in the user's language (launch: English + Hebrew; architecture must support adding languages without re-ingesting documents).

### 3.2 Knowledge ingestion
- **FR-8** Admins upload documents (PDF, Word, HTML, scanned PDFs via OCR). The ingestion pipeline extracts text, tables, **and images/figures with their captions and page anchors**, chunks the content, and indexes it per equipment profile.
- **FR-9** Each document is versioned; superseded revisions are flagged so answers always cite the current revision and can warn when a procedure changed between revisions.
- **FR-10** Equipment profiles: model, type, photos, associated documents, parts catalog, and the approved-fix collection.

### 3.3 Feedback & field-verified fixes
- **FR-11** Every answer ends with **"Did it help?"** (Yes / No).
- **FR-12** On "No," the technician gets a free-text box (plus optional photo attachment) to describe **what actually solved the issue**. Submission creates a *candidate fix* linked to the original question, the answer given, the equipment profile, and the submitting technician.
- **FR-13** On "Yes," the answer's source passages receive a positive reinforcement signal used to improve future retrieval ranking.

### 3.4 Curation workflow (approval before knowledge goes live)
Candidate fixes are **never used in answers until approved**. The lifecycle:

```
 SUBMITTED ──► PENDING REVIEW ──► APPROVED ──► ACTIVE (used in answers)
                    │                              │
                    ├──► EDITED & APPROVED ────────┘
                    ├──► REJECTED (with reason, visible to submitter)
                    └──► FLAGGED UNSAFE (blocked + safety notice to submitter)
```

- **FR-14** New candidate fixes enter a **review queue** visible to Curators/Admins, with badge counts and (configurable) email/push notification.
- **FR-15** The review screen shows side-by-side: the original question, the answer the system gave, the technician's proposed fix, the relevant manual excerpts, and an **automatic AI pre-screen** that flags potential safety issues (electrical, pressure, chemical, gas, lifting), contradictions with the OEM manual, and missing safety steps. The pre-screen advises the human reviewer; it never auto-approves.
- **FR-16** Curator actions: **Approve** (fix becomes active), **Edit & Approve** (curator refines wording, adds safety steps or references), **Reject** (with reason sent to the submitter), **Flag unsafe** (blocked; submitter notified with explanation).
- **FR-17** Approved fixes are indexed into the knowledge base tagged as "Field-verified — approved by {curator} on {date}" and are cited in answers with a distinct visual badge, ranked alongside (and, on symptom match, above) manual content.
- **FR-18** Full audit trail: every state change records who, when, and what was modified. Approved fixes can be retired or re-edited later; retired fixes immediately stop appearing in answers.
- **FR-19** Governance settings per organization: minimum reviewer role, optional two-reviewer rule for safety-critical equipment categories, and auto-expiry review (re-confirm fixes older than N months).

### 3.5 Administration & analytics
- **FR-20** Dashboard: most-asked questions, unanswered/low-confidence questions (content-gap list), helpfulness rate, fix-submission and approval rates, per-technician usage.
- **FR-21** User management with SSO (Business tier), role assignment, equipment-profile access control.
- **FR-22** OEM tier: a master knowledge base published downstream to all dealer organizations; dealers can layer local approved fixes on top but cannot alter OEM master content.

### 3.6 Mobile & offline
- **FR-23** Mobile-first PWA / native apps; voice input for hands-busy work.
- **FR-24** Offline packs: per-equipment bundles (key manual sections, images, approved fixes) downloadable for connectivity-poor sites; questions queue and sync when back online. (Phase 2 — see roadmap.)

---

## 4. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Latency** | First token of answer < 3 s; full answer < 12 s on 4G |
| **Groundedness** | ≥ 95% of answer claims traceable to a cited source in automated evaluation; zero fabricated part numbers or numeric specs in release testing |
| **Availability** | 99.5% (Starter/Pro), 99.9% (Business/OEM) |
| **Security** | Tenant isolation per organization (separate index namespaces + row-level security); encryption in transit (TLS 1.3) and at rest (AES-256); secrets in a managed vault |
| **Privacy** | Customer documents and fixes are never used to train shared models; per-tenant data deletion within 30 days of request; GDPR + Israeli Privacy Protection Law compliance |
| **Auditability** | Immutable log of every answer (question, retrieved sources, response, model version) retained 24 months — required for liability defense |
| **Scalability** | 10k organizations / 500k seats without architecture change; ingestion of a 500-page manual < 10 minutes |
| **Accessibility** | WCAG 2.1 AA; large-touch-target mode for gloved hands |
| **Safety posture** | Safety warnings cannot be disabled at any pricing tier; low-confidence answers always offer human escalation |

---

## 5. System Architecture

### 5.1 High-level diagram

```
┌──────────────────────────── Clients ────────────────────────────┐
│  Mobile PWA / iOS / Android      Web Console (Admin/Curator)    │
│  (chat, voice, camera, offline)  (ingestion, review queue,      │
│                                   analytics, user mgmt)         │
└────────────────┬────────────────────────────┬───────────────────┘
                 │            HTTPS / WSS     │
        ┌────────▼────────────────────────────▼────────┐
        │              API Gateway (REST + SSE)        │
        │   AuthN/AuthZ (OIDC/SSO) · rate limiting ·   │
        │   tenant routing · audit logging             │
        └──┬───────────────┬───────────────┬───────────┘
           │               │               │
 ┌─────────▼─────┐ ┌───────▼────────┐ ┌────▼───────────────┐
 │ Answer Service│ │ Ingestion Svc  │ │ Knowledge Mgmt Svc │
 │ (RAG          │ │ (async workers)│ │ (fix lifecycle,    │
 │  orchestrator)│ │ PDF parse, OCR,│ │  review queue,     │
 │               │ │ image & figure │ │  AI safety         │
 │ 1. embed query│ │ extraction,    │ │  pre-screen,       │
 │ 2. hybrid     │ │ chunking,      │ │  versioning,       │
 │    retrieve   │ │ embedding,     │ │  audit trail)      │
 │ 3. rerank     │ │ indexing       │ └────┬───────────────┘
 │ 4. LLM compose│ └───────┬────────┘      │
 │ 5. cite+conf  │         │               │
 └──────┬────────┘         │               │
        │                  │               │
┌───────▼──────────────────▼───────────────▼──────────────────────┐
│                        Data Layer                                │
│  Vector DB (per-tenant namespaces: chunks + image captions)      │
│  PostgreSQL (orgs, users, equipment, fixes + states, audit log,  │
│              conversations, feedback signals)                    │
│  Object Storage (original PDFs, extracted figures/images,        │
│                  offline packs)                                  │
│  Search index (BM25 keyword — hybrid retrieval complement)       │
└───────────────────────────┬──────────────────────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │     LLM Provider Layer     │
              │  pluggable backends:       │
              │  · Ollama (local, MVP dev) │
              │  · Anthropic API (prod)    │
              │  roles: answer composition,│
              │  vision (photo diagnosis), │
              │  safety pre-screen         │
              └────────────────────────────┘
```

### 5.2 Component decisions & rationale

**RAG over fine-tuning.** Retrieval-augmented generation over per-tenant indexes gives instant onboarding ("upload PDFs → live today"), clean tenant isolation, easy document updates, and citable answers. Fine-tuning per customer would be slow, expensive, and impossible to audit.

**Hybrid retrieval.** Dense vector search (semantic) + BM25 keyword search (exact error codes like "E47", part numbers) merged with reciprocal-rank fusion, then a reranker. Error codes and part numbers are precisely where pure-vector search fails — hybrid is non-negotiable for this domain.

**Image-aware ingestion.** During ingestion, figures/diagrams are extracted with bounding boxes, captioned by a vision model ("Fig 12 — concentrate valve location, p.41"), and indexed by caption text. At answer time, steps referencing a figure attach the actual image URL from object storage. This implements the "detailed response including images" requirement without OEM-image copyright issues — the customer supplied the documents under their own license.

**Approved-fix indexing.** Approved fixes are embedded into the same per-tenant index with a `source_type=field_fix` tag and metadata (approver, date, linked question). The retrieval layer boosts field fixes on close symptom match; the answer prompt instructs the model to present them with their verification badge. Rejection/retirement removes them from the index immediately — the index is the single source of truth for what the model can see.

**AI safety pre-screen (curation assist).** A dedicated prompt evaluates each candidate fix against the equipment's manual: detects contradictions, missing lock-out/tag-out or depressurization steps, hazardous-category keywords. Output is a structured advisory shown to the human curator. Design principle: **AI assists review, humans approve** — the human-in-the-loop is a product feature and a liability shield, never a bottleneck to be automated away.

**Conversation & answer logging.** Every answer stores the exact retrieved chunks and model version, enabling regression evaluation, "why did it say that?" investigations, and legal defensibility.

### 5.3 Technology stack (options resolved in v1.1)

Where v1.0 listed alternatives, v1.1 commits to one choice per layer. The deciding criterion throughout: **every component must also run on a single developer PC** (see §8), so the same stack moves from laptop to cloud without substitution.

| Layer | Decision | Rationale |
|---|---|---|
| Mobile/web client | React + PWA (Capacitor for app stores later) | One codebase, offline-capable via service worker |
| Admin console | React + component library | Shares design system with client |
| API | **Python (FastAPI)** | Chosen over NestJS: one language across API and ingestion workers, native async, and the ML/RAG ecosystem (embeddings, rerankers, PyMuPDF) is Python-first |
| Async workers | **Python + Celery (Redis broker)** | Chosen over Temporal: Celery + Redis is one small container locally; Temporal adds a server cluster we don't need at MVP scale |
| Vector DB | **pgvector** (→ Qdrant/managed only if ops demands it) | Lives inside the Postgres we already run; per-tenant isolation via RLS on the chunks table; one fewer service everywhere |
| Keyword search | **PostgreSQL full-text search** (→ OpenSearch only at scale) | Same database, same RLS tenant isolation; ranking is not true BM25 but is an adequate hybrid complement at MVP corpus sizes — `pg_search` (ParadeDB) is the in-Postgres upgrade path to real BM25 before reaching for OpenSearch |
| RDBMS | PostgreSQL 16 + RLS | Fixes, states, audit, users — plus vectors and keyword index (above) |
| Object storage | **MinIO (local/self-hosted) → AWS S3 (cloud)** | Identical S3 API in both environments; code never changes |
| PDF/OCR | **PyMuPDF + Tesseract** (cloud OCR as later opt-in for hard scans) | Fully local, no per-page cost during development; revisit AWS Textract/Google Vision only if scanned-manual quality demands it |
| LLM | **Dual backend behind the provider-abstraction layer:** Ollama-served local model (MVP/dev — see §8.3) and Anthropic Claude (production) | Claude models are API-only and cannot be self-hosted, so local development requires an open-weight backend; the abstraction (`LLM_PROVIDER=ollama\|anthropic`) makes the switch a config change |
| Auth | **Keycloak** (OIDC; SAML SSO at Business tier) | Chosen over Auth0: Auth0 is SaaS-only and cannot run on a local PC; Keycloak is a container, covers OIDC + SAML, and avoids per-MAU pricing |
| Infra | **Docker Compose (local/MVP) → AWS ECS Fargate (cloud), IaC (Terraform)** | AWS has both EU regions and il-central-1 (Tel Aviv) for the IL data-residency requirement; ECS over k8s for lower ops burden at this team size |
| Observability | **OpenTelemetry collector + Grafana/Prometheus/Loki locally → managed backend in cloud** | Same OTel instrumentation in both; groundedness & helpfulness tracked as first-class SLOs |

### 5.4 Core data model (simplified)

```
Organization ──< User (role: tech | curator | admin)
Organization ──< EquipmentProfile ──< Document ──< Chunk ──< Figure
EquipmentProfile ──< Fix
  Fix: { id, question_text, answer_given_id, proposed_text, photos[],
         submitted_by, state: submitted|pending|approved|rejected|unsafe|retired,
         reviewed_by, review_notes, ai_prescreen_report, approved_at, version }
Conversation ──< Message ──< AnswerLog { retrieved_chunk_ids[], model_version,
                                          confidence, citations[] }
Feedback { message_id, helped: bool, fix_id? }
AuditEvent { actor, entity, action, before, after, timestamp }
```

---

## 6. Delivery Roadmap

| Phase | Scope | Target |
|---|---|---|
| **MVP (3 mo)** | Text Q&A with citations + confidence, PDF ingestion (text+figures), equipment profiles, feedback loop, **full curation workflow**, basic admin, EN+HE | 3–5 design partners in one vertical |
| **Phase 2 (6 mo)** | Photo diagnosis, voice input, analytics dashboard, offline packs, AI pre-screen v2, two-reviewer rule | Paid SMB launch |
| **Phase 3 (9–12 mo)** | OEM white-label & master-KB publishing, SSO, FSM/CRM integrations, parts-ordering links, additional languages | First OEM lighthouse deal |

---

## 7. Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Wrong instruction causes injury/damage | Grounded-only answers, confidence gating, mandatory safety warnings, human-approved fixes, immutable answer logs, clear ToS positioning as decision support |
| Bad fix approved by a careless curator | AI pre-screen, optional two-reviewer rule for hazardous categories, retirement + audit trail, periodic re-confirmation of aging fixes |
| Thin customer documentation → weak answers | Onboarding wizard that measures KB coverage and shows the content-gap report from day one |
| OEM document copyright | Customers upload under their own license; OEM tier makes the rights-holder the publisher |
| LLM cost/capability shifts | Provider-abstraction layer; per-tenant token budgets; cache frequent answers |
| Platform giants bundle "good enough" AI | Win on vertical depth, visual answers, the curated-fix moat, and SMB pricing they can't profitably match |

---

## 8. Local Development & MVP Deployment Profile (added v1.1)

The entire FixMate infrastructure runs on a single developer PC before any cloud deployment. This is a hard requirement of the stack choices in §5.3: no component may be SaaS-only.

### 8.1 Containerization: Docker Compose

**Decision: Docker Compose** (one `docker-compose.yml`, `docker compose up`), not a local Kubernetes distribution and not native installs.

- **Why not native installs:** Postgres + Redis + MinIO + Keycloak installed directly on Windows drift from production immediately and are not reproducible across developer machines.
- **Why not local Kubernetes (minikube/k3d/kind):** the cloud target is ECS Fargate (§5.3), so local k8s buys parity with nothing while adding cluster ops to every dev day. Revisit only if the cloud target ever becomes Kubernetes.
- **Podman** is an acceptable drop-in substitute (compose-compatible) for licensing-sensitive environments; Docker Desktop with the WSL2 backend is the default on Windows.

The same container images built locally are what Terraform deploys to ECS — promotion is a registry push, not a rebuild.

### 8.2 Compose service inventory

| Service | Image (indicative) | Role |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | RDBMS + RLS, vector index, full-text keyword index, audit log |
| `redis` | `redis:7` | Celery broker + answer cache |
| `minio` | `minio/minio` | S3-compatible object storage (PDFs, figures, offline packs) |
| `api` | project image (FastAPI) | Answer Service, Knowledge Mgmt Service |
| `worker` | project image (Celery) | Ingestion: PDF parse, OCR, figure extraction, embedding, indexing |
| `keycloak` | `quay.io/keycloak/keycloak` | OIDC auth (realm-per-environment; org roles per §2) |
| `ollama` | `ollama/ollama` (GPU) | Local LLM serving (§8.3) |
| `otel-collector` + `grafana` stack | optional profile | Traces/metrics/logs; same OTel instrumentation as production |

**GPU note (Windows):** GPU passthrough to containers requires Docker Desktop + WSL2 with the NVIDIA CUDA-on-WSL driver. A pragmatic alternative that avoids passthrough entirely: run Ollama **natively on the Windows host** (it gets direct GPU access) and point containers at `http://host.docker.internal:11434`. Either topology is supported; the provider abstraction only sees a base URL.

### 8.3 Local LLM profile (MVP) — 4 GB GPU budget

A 4 GB VRAM card caps generation at ~4B parameters at 4-bit quantization (~2.5 GB weights, leaving headroom for KV cache). Embedding and reranking run on **CPU** so the GPU serves generation only.

| Role | Model | Serving | Why |
|---|---|---|---|
| Answer composition (generation) | **Qwen3-4B-Instruct, Q4_K_M** (`ollama pull qwen3:4b`) | Ollama, GPU | Strongest instruction-following and citation discipline in the ≤4B class; usable multilingual coverage for the EN+HE launch requirement; ~2.5 GB fits 4 GB VRAM with KV-cache headroom |
| Fallback / alternative generation | Llama 3.2 3B Instruct (`llama3.2:3b`) | Ollama, GPU | Slightly smaller and faster; weaker Hebrew |
| Embeddings | **BGE-M3** (`bge-m3`) | CPU | Multilingual (incl. Hebrew) so EN+HE works without re-ingestion (FR-7); also emits sparse signals useful to hybrid retrieval |
| Reranker | BGE-reranker-v2-m3 | CPU | Pairs with BGE-M3; runs acceptably on CPU at top-20 candidate depth |
| Figure captioning (ingestion-time) | Claude vision via API (batch), or `gemma3:4b` locally at reduced quality | API / Ollama | Captioning happens once per document at ingestion, not per answer — low volume makes API use cheap, and caption quality compounds into every future retrieval |

Backend selection is a single environment switch consumed by the provider-abstraction layer:

```env
LLM_PROVIDER=ollama      # local MVP profile
LLM_PROVIDER=anthropic   # production profile (Claude via official SDK)
```

### 8.4 Scope and safety boundary of the local profile

The local model profile is for **development, demos, and the MVP iteration loop**. It does not change the safety posture in §4:

- The groundedness gate (≥95% traceable claims, zero fabricated specs) and the fabrication post-check apply to **whichever backend is active**. A ≤4B model will trip the confidence/escalation path (FR-4) more often — that is the system working as designed, not a defect.
- **Release-gate evaluation and any pilot with real field technicians runs on the Claude backend** until the local model demonstrably passes the same groundedness and safety evals. Answer-regression baselines (§5.2) are recorded per backend and never compared across backends.
- The AI safety pre-screen (FR-15) advises a human curator in both profiles; curation rules are backend-independent.
