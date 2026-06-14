import base64

from anthropic import AsyncAnthropic

from fixmate.llm.base import CompletionRequest, CompletionResult


class AnthropicProvider:
    def __init__(self, api_key: str, model: str):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, request: CompletionRequest) -> CompletionResult:
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
