"""The Ollama (local, open-weight) LLM backend used for dev / the MVP profile.

Implements the ``LLMProvider`` contract by calling a locally-running Ollama
server (default model: ``llama3.2:3b``) over HTTP. It runs fully offline on
modest hardware (spec §8.3), which is why it's the default for local development.
It has no vision capability, so figure captioning falls back to the Anthropic
backend.
"""

import httpx

from fixmate.core.settings import settings
from fixmate.llm.base import CompletionRequest, CompletionResult


class OllamaProvider:
    """LLM backend backed by a local Ollama server."""

    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Generate a completion via Ollama's ``/api/chat``.

        llama3.2:3b is a plain instruct model with no chain-of-thought, so unlike
        the previous qwen3:4b default there is no reasoning block to suppress or
        strip — ``message.content`` is answer prose directly. A higher local token
        cap is therefore affordable: every generated token is answer, not discarded
        thinking, and the model runs on-GPU at ~40-80 t/s.
        """
        messages = [{"role": "system", "content": request.system}, *request.messages]
        # Local-only token cap: keeps a runaway generation bounded on the dev
        # profile while leaving ample room for a full grounded answer (no thinking
        # tokens to budget for now). The Anthropic backend has no such cap.
        LOCAL_MAX = 1024
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            # Keep the generation model resident so it isn't evicted by the
            # embedding model between requests (and vice-versa) — model swapping
            # was adding a full cold load to each answer on the 4 GB profile.
            "keep_alive": settings.ollama_keep_alive_param,
            "options": {"num_predict": min(request.max_tokens, LOCAL_MAX)},
        }
        if request.json_response:
            payload["format"] = "json"
        # Generous read timeout for the local profile, kept well under the uvicorn
        # worker timeout. On-GPU llama3.2:3b answers in a few seconds, but a cold
        # load or CPU fallback can still take longer.
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        # prompt_eval_count + eval_count are Ollama's input/output token counters.
        tokens = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
        text = data["message"]["content"].strip()
        return CompletionResult(
            text=text,
            model_version=self._model,
            provider="ollama",
            tokens_used=tokens,
        )

    async def caption_image(self, image: bytes, media_type: str, context: str) -> str:
        """Not supported — the local model has no vision; use the Anthropic backend."""
        # spec §8.3 keeps figure captioning on the Claude backend; the local
        # generation model (llama3.2:3b) has no vision capability.
        raise NotImplementedError("use anthropic backend for captioning")
