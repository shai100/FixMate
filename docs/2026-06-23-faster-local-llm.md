# Faster local LLM: llama3.2:3b on GPU + bge-m3 on CPU

**Date:** 2026-06-23
**Commit:** _(pending)_ — "Switch local generation to llama3.2:3b; pin embeddings to CPU"
**Relates to:** CLAUDE.md §3 (LLM stack, spec §8.3 local profile), §7.1 (latency SLOs)

## Problem

The local/MVP profile used `qwen3:4b` (Q4) served by Ollama. On the 4 GB GPU
profile it ran at ~8 t/s, taking 60–90 s per answer. Two causes:

1. **qwen3 is a reasoning model.** Even with the `/no_think` directive, it
   generated chain-of-thought tokens that the provider then stripped — paying for
   discarded tokens and forcing a hard `num_predict` cap of 600.
2. **VRAM contention.** With both the generation model and the resident `bge-m3`
   embedding model pinned via `keep_alive=-1`, a 2.5 GB Q4 model + KV cache +
   embeddings did not fit in 4 GB VRAM, so Ollama spilled generation layers to
   CPU — the actual throughput cap.

## What was built

- **`fixmate/core/settings.py`** — default `ollama_generation_model` →
  `llama3.2:3b` (non-reasoning instruct, ~2 GB at Q4, fits 4 GB VRAM). Added
  `ollama_embed_on_cpu: bool = True`.
- **`fixmate/llm/ollama_provider.py`** — removed the qwen3 `/no_think` injection
  and the `_THINK_BLOCK` regex (no reasoning block to strip); raised the local
  token cap `LOCAL_MAX` 600 → 1024 (every token is now answer, not thinking).
- **`fixmate/llm/embeddings.py`** — when `ollama_embed_on_cpu` is set, send
  `options.num_gpu=0` on the embed request so `bge-m3` runs on CPU and never
  evicts generation from the GPU.
- **Config/docs** — `.env.example`, `.env`, `docker-compose.yml` comments,
  `setup-instructions.md` (prerequisites, env table, model-pull step, healthcheck
  expected output), `docs/ARCHITECTURE.md` stack table. Updated the model-name
  references in `fixmate/ingestion/figures.py` and `ollama_provider.py` comments.

## Design notes

- **Why llama3.2:3b over qwen2.5:3b:** both are strong; llama edges it on strict
  instruction-following, which matters most for grounded RAG + safety gating
  (only answer from chunks, cite, escalate on low confidence). qwen2.5:3b is a
  drop-in alternative if technical/numeric extraction proves weaker.
- **Production unchanged.** Release gates and technician pilots run on Claude
  (CLAUDE.md §3); this only affects local dev/MVP iteration speed.
- The smoke test confirmed correct groundedness behavior — asked about an unknown
  error code, the model declined rather than fabricating.

## Verification evidence

Settings resolve to the new model:

```
$ python -c "import fixmate.core.settings as s; print('gen:', s.settings.ollama_generation_model, '| embed_cpu:', s.settings.ollama_embed_on_cpu)"
gen: llama3.2:3b | embed_cpu: True
```

Imports clean + factory unit tests pass:

```
$ python -m pytest tests/llm/test_factory.py -q
4 passed in 2.19s
```

Model pulled into the Ollama container:

```
$ docker compose exec -T ollama ollama pull llama3.2:3b
... success
```

Live provider smoke test (groundedness preserved, declines unknown code):

```
--- 25.2s, 96 tokens, model=llama3.2:3b ---   (first call: includes cold model load)
I'm not familiar with that specific error code; can you please provide more
context or information about the pump model and its manufacturer ...
```

Warm-path latency (representative of steady-state):

```
warm: 3.8s for a full short answer
```

~4 s warm vs the previous 60–90 s on qwen3 — comfortably inside the §7.1
12 s full-answer SLO.
