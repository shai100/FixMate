# Phase 2 — LLM provider abstraction

**Commit:** `feat: LLM provider abstraction with ollama + anthropic backends (phase 2)`
**Plan:** `docs/superpowers/plans/2026-06-12-fixmate-mvp.md` §Phase 2 (and Appendix A.1, A.2)
**Date:** 2026-06-14

---

## What was built

A provider-agnostic LLM layer so all later phases call models through one frozen
contract and never bind to a vendor SDK directly (CLAUDE.md §3.1).

| File | Purpose / design |
|------|------------------|
| `fixmate/llm/base.py` | The cross-phase contract (Appendix A.1): `CompletionRequest`, `CompletionResult`, and the `LLMProvider` `Protocol`. Structural typing — providers satisfy it without inheritance. `CompletionResult` carries `model_version` / `provider` / `tokens_used` so Phase 5 can write them straight into `answer_logs` (CLAUDE.md §4.5). |
| `fixmate/llm/ollama_provider.py` | `POST /api/chat` with `stream:false`; `format:"json"` when `json_response`. `caption_image` raises `NotImplementedError("use anthropic backend for captioning")` — qwen3:4b has no vision (spec §8.3). `think:false` + a `</think>`-strip keep `text` to answer prose only (see decision below). `tokens_used = prompt_eval_count + eval_count`. |
| `fixmate/llm/anthropic_provider.py` | Official `AsyncAnthropic` SDK; model from settings (default `claude-opus-4-8`), `thinking={"type":"adaptive"}` (verified correct against the claude-api skill — adaptive is the only on-mode for the Opus 4.x family). `caption_image` sends a base64 image block for figure captioning (used by Phase 3). |
| `fixmate/llm/embeddings.py` | `embed(texts)` → `POST /api/embed` with `bge-m3`. **Always Ollama/CPU regardless of `LLM_PROVIDER`** (spec §8.3). Asserts every vector is `EMBEDDING_DIM == 1024` — the schema `vector(1024)` contract from Phase 1 (Appendix A.2). |
| `fixmate/llm/factory.py` | `get_provider(provider=None)` — selects on `LLM_PROVIDER` (or explicit override); unknown value raises `ValueError`. The single construction point; business logic never instantiates a provider directly. |
| `fixmate/llm/cli.py` | `python -m fixmate.llm.cli "<prompt>" [--provider ...]` → prints `[provider/model] text`. |
| `tests/llm/test_factory.py` | Unit: factory returns the right class per setting, honors override, raises on unknown. |
| `tests/llm/test_ollama_integration.py` | `@pytest.mark.integration` (live Ollama): `complete()` returns non-empty text; `embed()` returns two 1024-dim vectors. |

### Design decision: stripping qwen3 reasoning output

qwen3:4b is a hybrid reasoning model. Ollama's chat template opens a `<think>` block
in the prompt, so with a small token budget the entire response is consumed by
chain-of-thought and `content` comes back empty (observed: `tokens_used=92`, `text=''`).
Fix: send `think:false` and strip everything through the first `</think>` the template
emits, so `complete().text` is answer prose only. This matters because Phase 5 parses
`[chunk:<id>]` citations and runs the groundedness check over this text — it must not
contain reasoning. The model's remaining verbosity is a Phase 5 prompt-engineering
concern, not part of the provider contract. `/no_think` was rejected as an alternative:
on this Ollama build it intermittently strips the answer along with the reasoning.

---

## Verification evidence

### `pytest tests/llm -v` (compose up, live Ollama)

```
tests/llm/test_factory.py::test_factory_returns_ollama PASSED            [ 16%]
tests/llm/test_factory.py::test_factory_returns_anthropic PASSED         [ 33%]
tests/llm/test_factory.py::test_factory_explicit_override PASSED         [ 50%]
tests/llm/test_factory.py::test_factory_unknown_raises PASSED            [ 66%]
tests/llm/test_ollama_integration.py::test_ollama_complete_returns_text PASSED [ 83%]
tests/llm/test_ollama_integration.py::test_ollama_embed_returns_1024_dim_vectors PASSED [100%]

============================= 6 passed in 16.95s ==============================
```

### CLI smoke test (plan 2.8 standalone check)

```
$ python -m fixmate.llm.cli "Reply with exactly: OK"
[ollama/qwen3:4b] OK
```

### JSON-mode path (`json_response=True`)

```
JSON OUTPUT: '{\n  "status": "ok"\n}'
```

### Lint / format

```
$ ruff check
All checks passed!
$ ruff format --check fixmate tests
17 files already formatted
```

> The `anthropic` backend is exercised only at the factory/construction level — no live
> API call is made in CI (no key in the local profile). Its request shape is taken
> verbatim from the plan and validated against the claude-api skill.
