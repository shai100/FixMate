"""Command-line tool to send a one-shot prompt to the configured LLM backend.

Handy for checking that Ollama/Anthropic is reachable and responding. Example:
``python -m fixmate.llm.cli "hello" --provider ollama``.
"""

import argparse
import asyncio

from fixmate.llm.base import CompletionRequest
from fixmate.llm.factory import get_provider


async def _run(prompt: str, provider_name: str | None) -> None:
    """Send ``prompt`` to the chosen provider and print the reply."""
    provider = get_provider(provider_name)
    result = await provider.complete(
        CompletionRequest(
            system="You are FixMate, a concise assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
    )
    print(f"[{result.provider}/{result.model_version}] {result.text}")


def main() -> None:
    """Parse CLI arguments and run the prompt."""
    parser = argparse.ArgumentParser(description="Send a one-shot prompt to the configured LLM.")
    parser.add_argument("prompt")
    parser.add_argument("--provider", choices=["ollama", "anthropic"], default=None)
    args = parser.parse_args()
    asyncio.run(_run(args.prompt, args.provider))


if __name__ == "__main__":
    main()
