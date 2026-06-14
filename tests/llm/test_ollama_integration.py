import pytest

from fixmate.llm.base import CompletionRequest
from fixmate.llm.embeddings import EMBEDDING_DIM, embed
from fixmate.llm.factory import get_provider

pytestmark = pytest.mark.integration


async def test_ollama_complete_returns_text():
    provider = get_provider("ollama")
    result = await provider.complete(
        CompletionRequest(
            system="You are a terse assistant.",
            messages=[{"role": "user", "content": "Reply with the single word OK."}],
            max_tokens=64,
        )
    )
    assert result.text.strip()
    assert result.provider == "ollama"
    assert result.model_version


async def test_ollama_embed_returns_1024_dim_vectors():
    vectors = await embed(["hello", "pump pressure too high"])
    assert len(vectors) == 2
    assert all(len(v) == EMBEDDING_DIM for v in vectors)
