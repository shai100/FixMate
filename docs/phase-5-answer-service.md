# Phase 5 — Answer service (RAG, citations, confidence, groundedness, logging)

**Commit:** _(this commit)_ — `feat: answer service — RAG compose + citations + confidence + groundedness + answer log (phase 5)`
**Plan:** `docs/superpowers/plans/2026-06-12-fixmate-mvp.md` §Phase 5 (tasks 5.1–5.6)
**Architecture rules:** CLAUDE.md §2.1 (RAG), §2.6 (answer logging), §4.2 (LLM output validation), §8.1 (safety/fabrication detection); Appendix A.7 (citation marker) / A.8 (safety constants)
**Date:** 2026-06-15

---

## What was built

`fixmate/answers/` — the answer service that turns a question into a grounded, cited,
auditable answer on top of Phase 4 retrieval.

- **`groundedness.py`** — `check_groundedness(answer, chunk_texts) -> (bool, [violations])`.
  Regex-extracts numeric safety claims (torque/pressure/electrical/temperature/dimension/
  speed) and part numbers, and rejects any not present verbatim in the retrieved corpus.
  Normalization strips all whitespace and the middle dot so spacing variants ("12 Nm" /
  "12Nm" / "N·m") compare equal. This is the FR-4 / spec §8.4 fabrication gate.
- **`confidence.py`** — `confidence_band(top_score) -> "high"|"medium"|"low"` from the top
  rerank score. Thresholds `0.70 / 0.45` carry the SAFETY-CRITICAL comment (Appendix A.8):
  change only with Phase 12 eval evidence. `low` ⇒ escalation path.
- **`prompts.py`** — `SYSTEM_PROMPT` (answer only from SOURCES; warnings-first structure;
  exact values; `[chunk:<id>]` citations; field-fix verification badge), `render_sources` /
  `build_user_prompt` (formats retrieved chunks; field-fix chunks get the
  "Field-verified — approved by {approver} on {date}" badge header), `escalation_answer`
  (FR-4 "don't know" + nearest sections + escalate, no fabricated body), and
  `groundedness_retry_suffix` (retry feedback).
- **`answer_log.py`** — `write_answer_log(...)` persists the immutable `answer_logs` row
  (retrieved_chunk_ids, model_version, provider, confidence, citations, groundedness,
  tokens_used) — CLAUDE.md §4.5 / §2.6.
- **`composer.py`** — `compose_answer(org_id, equipment_id, question, history=[])`:
  search → confidence gate → (if low: escalation, no LLM body) → LLM `complete` → parse
  `[chunk:<uuid>]` citations → validate every cited id ∈ retrieved set → `check_groundedness`
  → **retry once** with violations appended → degrade to escalation if still ungrounded →
  persist `answer_logs`. Returns `Answer(text, confidence, citations[], figures[],
  escalated, answer_log_id)`. Figures attach via `figures` rows matching a retrieved
  chunk's (document_id, page), exposed as short-lived presigned MinIO URLs.
- **`cli.py`** — `python -m fixmate.answers.cli "<question>" --org <name> [--equipment <name>]`.

Supporting change: `core/storage.presigned_url(key)` (signed GET URL for private figure
objects); `OllamaProvider` read timeout 120s → 600s (CPU-served qwen3:4b needs several
minutes for a full structured answer; 300s was right at the edge and flaked).

### Design decisions

- **Out-of-corpus detection via structured abstention, not score thresholds.** Measured on
  the fixture corpus, a nonsense query ("calibrate the flux capacitor") top-scores **0.758**
  while a relevant query ("fix E47") top-scores **0.822** — the MVP reranker's `(cos+1)/2`
  mapping compresses all scores into ~0.69–0.82, so no global confidence threshold separates
  them, and a model told to "just answer" will cite irrelevant chunks. So the system prompt
  gives the model a clean way to decline: emit the sentinel `INSUFFICIENT_CONTEXT` when none
  of the SOURCES mention the question's subject. The composer detects it and routes to the
  FR-4 escalation path. This is reliable on the corpus and **does not touch the safety-critical
  0.70/0.45 thresholds** (Appendix A.8 — recalibration is deferred to Phase 12 evals). The
  confidence band is still computed, logged, and gates the no-LLM-body path for genuinely low
  scores (meaningful on real, larger corpora).
- **Abstention is keyword-anchored** ("do ANY SOURCES mention the equipment/component/error
  code/symptom?"). An earlier, broader phrasing made the weak 4B dev model over-refuse a
  genuinely answerable question (E47); anchoring abstention to concrete relevance fixed it.
- **A non-escalated answer must also carry ≥1 valid citation** (CLAUDE.md §4.2): an uncited
  answer is treated as a refusal and escalated, never shown to a technician.
- **Groundedness retry before degrade.** On a citation or numeric-claim violation the
  composer re-prompts once with the specific offending tokens, then degrades to escalation —
  never serves a fabricated value.
- **Field-fix badge sourced at compose time** from `fixes.reviewed_by` (→ `users.name`) and
  `fixes.approved_at`, injected into the source header so the model surfaces the verification
  badge (spec §2.4 moat).

## Verification evidence

Compose services up (postgres healthy; ollama with qwen3:4b + bge-m3).

### Unit tests — groundedness + confidence (`pytest tests/answers/test_groundedness.py tests/answers/test_confidence.py -q`)
```
........                                                                 [100%]
8 passed in 0.03s
```

### No regressions — full suite minus the slow answer-integration tests (`pytest --ignore=tests/answers/test_composer_integration.py -q`)
```
....................................                                     [100%]
36 passed in 81.74s (0:01:21)
```

### Integration suite — all answer composer cases (`pytest tests/answers/test_composer_integration.py -v`)
```
tests/answers/test_composer_integration.py::test_grounded_answer_has_citations_and_logs PASSED [ 33%]
tests/answers/test_composer_integration.py::test_out_of_corpus_question_escalates PASSED [ 66%]
tests/answers/test_composer_integration.py::test_equipment_isolation_yields_escalation PASSED [100%]
3 passed in 620.55s (0:10:20)
```
Confirms: E47 yields a non-empty, grounded answer with ≥1 `[chunk:<uuid>]` citation and an
`answer_logs` row (`groundedness.grounded` true); the out-of-corpus question abstains →
`escalated=True`, no citations, `groundedness.reason="model_abstained"`; an unknown
equipment id returns the escalation answer with no citations.

### Retrieval score separation (motivates the abstention design)
```
$ python -m fixmate.retrieval.cli "calibrate the flux capacitor" --org demo --equipment "Pump X" --top-k 1
 0.758  manual    3  Reassembly. Tighten to 12 Nm. ...
$ python -m fixmate.retrieval.cli "How do I fix error E47?" --org demo --equipment "Pump X" --top-k 1
 0.822  manual    2  Error E47: concentrate valve blocked. ...
```
Nonsense (0.758) and relevant (0.822) both land in the "high" band — score gating alone
cannot separate them; hence the sentinel.

### Lint
```
$ ruff check fixmate/answers
All checks passed!
```

### Standalone CLI (`python -m fixmate.answers.cli "How do I fix error E47?" --org demo --equipment "Pump X"`)
```
[high]

... grounded answer body ...

Citations:
  - manual p2 (chunk 57c6492b-b714-4519-aa50-f038ab6e3a3f)

Figures:
  - p2: Figure on page 2 of sample-manual.pdf

answer_log_id: ba4da54a-bb29-49db-b493-aecb7377bc70
```
Grounded answer with a valid citation, attached figure, and a persisted answer log. (On the
qwen3:4b dev backend some chain-of-thought leaks into the prose despite `think=False` — a
known small-model artifact; the groundedness/citation gates still pass and production runs
on Claude, spec §8.3.)
