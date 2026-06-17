"""The Ollama (local, open-weight) LLM backend used for dev / the MVP profile.

Implements the ``LLMProvider`` contract by calling a locally-running Ollama
server (default model: ``qwen3:4b``) over HTTP. It runs fully offline on modest
hardware (spec §8.3), which is why it's the default for local development. It has
no vision capability, so figure captioning falls back to the Anthropic backend.
"""

import re

import httpx

from fixmate.llm.base import CompletionRequest, CompletionResult

# qwen3's chat template opens the reasoning block in the prompt, so the model's
# content can begin mid-reasoning and close with </think> before the answer.
# Strip everything through the closing tag so callers receive only answer prose.
_THINK_BLOCK = re.compile(r"^.*?</think>\s*", re.DOTALL)


class OllamaProvider:
    """LLM backend backed by a local Ollama server."""

    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Generate a completion via Ollama's ``/api/chat``, stripping reasoning.

        Uses qwen3's ``/no_think`` user-message directive to move chain-of-thought
        into the separate ``message.thinking`` field (not counted against the answer
        token budget) so ``message.content`` contains only answer prose.  The
        ``think: false`` API param is also sent for forward-compatibility but is
        ignored by Ollama ≤ 0.30.x.  Uses a long timeout because CPU generation
        at ~8 t/s can take 60–90 s for a real answer.
        """
        # Inject /no_think into the last user turn — the only signal Ollama 0.30.x
        # + qwen3:4b reliably respects for suppressing runaway chain-of-thought.
        # This directive must appear at the start of a user message (model-level
        # token, not a server parameter), so we prepend it rather than using the
        # `think: false` API flag which is silently ignored on this version.
        messages = [{"role": "system", "content": request.system}, *request.messages]
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                messages[i] = {**messages[i], "content": "/no_think " + messages[i]["content"]}
                break
        # Hard-cap token budget for CPU dev: thinking tokens count against
        # num_predict even when separated via /no_think, so 2048 (the caller
        # default) would take ~300 s at 8 t/s.  700 tokens ≈ 300 thinking +
        # 400 answer — fits in ~90 s and produces a usable dev answer.
        # The Anthropic backend has no such cap; this is local-only.
        LOCAL_MAX = 600
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "think": False,  # forward-compat for Ollama ≥ 0.6 when it ships
            "options": {"num_predict": min(request.max_tokens, LOCAL_MAX)},
        }
        if request.json_response:
            payload["format"] = "json"
        # CPU-served qwen3:4b (spec §8.3 local profile) can take 90+ s per call;
        # keep a generous read timeout but well under the uvicorn worker timeout.
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        # prompt_eval_count + eval_count are Ollama's input/output token counters.
        tokens = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
        # With /no_think, Ollama 0.30.x puts the chain-of-thought in
        # message.thinking and the answer in message.content.  Apply the regex
        # as a safety net in case an older Ollama version merges them into content.
        raw = data["message"]["content"]
        text = _THINK_BLOCK.sub("", raw).strip()
        return CompletionResult(
            text=text,
            model_version=self._model,
            provider="ollama",
            tokens_used=tokens,
        )

    async def caption_image(self, image: bytes, media_type: str, context: str) -> str:
        """Not supported — the local model has no vision; use the Anthropic backend."""
        # spec §8.3 keeps figure captioning on the Claude backend; the local
        # generation model (qwen3:4b) has no vision capability.
        raise NotImplementedError("use anthropic backend for captioning")
