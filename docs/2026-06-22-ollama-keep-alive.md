# Fix slow queries: stop Ollama model-swap thrashing (keep_alive)

**Date:** 2026-06-22
**Commit:** _(pending)_ — "Keep Ollama models resident to remove per-query cold loads"
**Relates to:** CLAUDE.md §3 (LLM stack), §7.1 (Latency SLOs), §8.3 local profile; `docs/2026-06-22-rerank-stored-embeddings.md`

## Problem

A real MPS query ("no light in power btn") took **minutes** and frequently timed
out. Measured end-to-end (`LLM_PROVIDER=ollama`, fresh process):

```
[retrieval]  108,479 ms   (just embedding the query)
[generation] hit the 180 s ReadTimeout and crashed
WALL CLOCK:  247.5 s, then errored
```

`ollama ps` showed **zero models resident**. On the 4 GB profile Ollama evicts a
model as soon as the other is requested, so every answer swaps
`bge-m3` (embeddings) ↔ `qwen3:4b` (generation) and pays a full **cold model
load** on each call. With the embedding model warm, the same retrieval embed took
**0.55 s** — proving the ~108 s was cold-load/swap, not compute.

(An earlier fix — reranking from stored embeddings instead of re-embedding the
candidates — removed ~7 s of redundant work, but the model-swap cold load was the
dominant cost and is addressed here.)

## What was built

- **`docker-compose.yml`** — the `ollama` service now sets
  `OLLAMA_KEEP_ALIVE=-1` (never unload) and `OLLAMA_MAX_LOADED_MODELS=2` so both
  the embedding and generation models stay resident simultaneously.
- **`fixmate/core/settings.py`** — new `ollama_keep_alive` setting (default
  `-1`) plus an `ollama_keep_alive_param` property that coerces whole-number
  values to a JSON `int`. Ollama's `/api/embed` returns **HTTP 400** for a string
  `"-1"`; the sentinel must be a number, while duration strings ("5m") stay
  strings.
- **`fixmate/llm/embeddings.py`** and **`fixmate/llm/ollama_provider.py`** — both
  send `keep_alive` on every request, so the behaviour also applies to an Ollama
  running outside Compose (native Windows), not just the container.
- **`setup-instructions.md`**, **`docs/ARCHITECTURE.md`** — documented the new
  env var and the keep-resident rationale.

No safety logic changed: the confidence gate, groundedness check, and the
two-attempt groundedness retry are untouched.

## Verification evidence

Same MPS query after the fix (`OLLAMA_KEEP_ALIVE=-1`, `OLLAMA_MAX_LOADED_MODELS=2`):

```
[retrieval #1 cold] 11,315 ms   (one bge-m3 load, vs ~108 s before)
[retrieval #2 warm]    927 ms    (model stays resident — no reload)
[compose_answer TOTAL] 323.4 s   (escalated=True, conf=high)
```

`tests/llm/test_ollama_integration.py::test_ollama_embed_returns_1024_dim_vectors`
passes in isolation (9.5 s); it only timed out earlier under concurrent Ollama load.

### Honest limitation — generation is still the wall

Retrieval is now fixed: the cold model load dropped from ~108 s to ~11 s (one
load) and warm queries are ~0.9 s. But **generation latency is unchanged** —
CPU-served `qwen3:4b` runs at ~8 tok/s, so each `complete()` call is ~150 s, and
the groundedness retry can run it twice (the 323 s above = two attempts before
escalation). `keep_alive` cannot speed token generation; it only removes the
model-swap cold load. On this 4 GB CPU profile, sub-12-second answers (SLO §7.1)
are only achievable with `LLM_PROVIDER=anthropic` (Claude), which the team
deferred pending a valid API key (the configured one returns 401).
