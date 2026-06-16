"""The LLM provider contract — the interface every backend must implement.

FixMate never calls a vendor SDK directly from business logic. Instead it talks
to this small abstraction, so the same answer/ingestion code runs unchanged
whether the backend is a local Ollama model (dev) or Anthropic Claude
(production). This file defines the request/result data shapes and the
``LLMProvider`` Protocol that ``ollama_provider`` and ``anthropic_provider``
fulfil; ``factory.get_provider`` picks one at runtime.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class CompletionRequest:
    """Everything a provider needs to generate a completion.

    ``system`` is the system prompt; ``messages`` is the chat history as
    ``[{"role": "user"|"assistant", "content": str}, ...]``. ``json_response``
    asks the provider to force JSON output (used by the safety pre-screen).
    """

    system: str
    messages: list[dict]  # [{"role": "user"|"assistant", "content": str}]
    max_tokens: int = 2048
    json_response: bool = False  # provider must coax/enforce JSON output


@dataclass
class CompletionResult:
    """A provider's response, normalized across backends.

    Carries the generated ``text`` plus the metadata the answer log needs:
    which ``model_version``/``provider`` produced it and how many tokens it used.
    """

    text: str
    model_version: str  # e.g. "qwen3:4b" / "claude-opus-4-8"
    provider: str  # "ollama" / "anthropic"
    tokens_used: int = 0


class LLMProvider(Protocol):
    """Structural interface a backend must satisfy to be usable as an LLM.

    Any class with these two async methods counts as an ``LLMProvider`` (Python
    ``Protocol`` = duck-typed interface, no inheritance required):

      - ``complete``: generate a text completion for a request.
      - ``caption_image``: describe an image for figure captioning (vision).
    """

    async def complete(self, request: CompletionRequest) -> CompletionResult: ...

    async def caption_image(self, image: bytes, media_type: str, context: str) -> str: ...
