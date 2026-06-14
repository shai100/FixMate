import argparse
import asyncio

from fixmate.llm.base import CompletionRequest
from fixmate.llm.factory import get_provider


async def _run(prompt: str, provider_name: str | None) -> None:
    provider = get_provider(provider_name)
    result = await provider.complete(
        CompletionRequest(
            system="You are FixMate, a concise assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
    )
    print(f"[{result.provider}/{result.model_version}] {result.text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a one-shot prompt to the configured LLM.")
    parser.add_argument("prompt")
    parser.add_argument("--provider", choices=["ollama", "anthropic"], default=None)
    args = parser.parse_args()
    asyncio.run(_run(args.prompt, args.provider))


if __name__ == "__main__":
    main()
