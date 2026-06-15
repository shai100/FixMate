import re

import httpx

from fixmate.llm.base import CompletionRequest, CompletionResult

# qwen3's chat template opens the reasoning block in the prompt, so the model's
# content can begin mid-reasoning and close with </think> before the answer.
# Strip everything through the closing tag so callers receive only answer prose.
_THINK_BLOCK = re.compile(r"^.*?</think>\s*", re.DOTALL)


class OllamaProvider:
    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": request.system}, *request.messages],
            "stream": False,
            # qwen3 is a hybrid reasoning model; disable thinking so the full
            # num_predict budget produces answer content, not chain-of-thought
            # (downstream citation/groundedness parsing expects answer prose).
            "think": False,
            "options": {"num_predict": request.max_tokens},
        }
        if request.json_response:
            payload["format"] = "json"
        # CPU-served qwen3:4b (spec §8.3 local profile) can take several minutes
        # to generate a full structured answer; keep a generous read timeout.
        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        # prompt_eval_count + eval_count are Ollama's input/output token counters.
        tokens = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
        return CompletionResult(
            text=_THINK_BLOCK.sub("", data["message"]["content"]).strip(),
            model_version=self._model,
            provider="ollama",
            tokens_used=tokens,
        )

    async def caption_image(self, image: bytes, media_type: str, context: str) -> str:
        # spec §8.3 keeps figure captioning on the Claude backend; the local
        # generation model (qwen3:4b) has no vision capability.
        raise NotImplementedError("use anthropic backend for captioning")
