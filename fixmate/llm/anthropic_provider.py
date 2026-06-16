"""The Anthropic (Claude) LLM backend used in production.

Implements the ``LLMProvider`` contract by calling the Anthropic API for both
text completion and vision-based figure captioning. Claude is API-only (it can't
be self-hosted), so this backend requires network access and an API key; the
local Ollama backend is the offline alternative.
"""

import base64

from anthropic import AsyncAnthropic

from fixmate.llm.base import CompletionRequest, CompletionResult


class AnthropicProvider:
    """LLM backend backed by Anthropic's Claude models."""

    def __init__(self, api_key: str, model: str):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Generate a completion via the Messages API and report token usage."""
        msg = await self._client.messages.create(
            model=self._model,
            system=request.system,
            messages=request.messages,
            max_tokens=request.max_tokens,
            thinking={"type": "adaptive"},
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        return CompletionResult(
            text=text,
            model_version=self._model,
            provider="anthropic",
            tokens_used=msg.usage.input_tokens + msg.usage.output_tokens,
        )

    async def caption_image(self, image: bytes, media_type: str, context: str) -> str:
        """Describe a manual figure in one sentence for search indexing.

        Sends the image plus surrounding ``context`` to Claude's vision model and
        returns a concise caption (including figure/page numbers when visible).
        """
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.b64encode(image).decode(),
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Caption this technical figure for search indexing. "
                                f"Context: {context}. One sentence, include figure "
                                "number and page if visible."
                            ),
                        },
                    ],
                }
            ],
        )
        return "".join(b.text for b in msg.content if b.type == "text").strip()
