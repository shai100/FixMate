from dataclasses import dataclass
from typing import Protocol


@dataclass
class CompletionRequest:
    system: str
    messages: list[dict]  # [{"role": "user"|"assistant", "content": str}]
    max_tokens: int = 2048
    json_response: bool = False  # provider must coax/enforce JSON output


@dataclass
class CompletionResult:
    text: str
    model_version: str  # e.g. "qwen3:4b" / "claude-opus-4-8"
    provider: str  # "ollama" / "anthropic"
    tokens_used: int = 0


class LLMProvider(Protocol):
    async def complete(self, request: CompletionRequest) -> CompletionResult: ...

    async def caption_image(self, image: bytes, media_type: str, context: str) -> str: ...
