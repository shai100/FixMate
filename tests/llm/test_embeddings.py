"""Unit tests for the embedding client's request batching.

These do not touch Ollama: ``httpx.AsyncClient`` is replaced with a fake that
records each request body. They guard the fix that splits a large set of texts
into bounded sub-batches so a whole-manual embedding call cannot overflow a
single request's timeout (which previously failed large-manual ingestion).
"""

import fixmate.llm.embeddings as embeddings
from fixmate.llm.embeddings import EMBEDDING_DIM, embed


class _FakeResponse:
    """Minimal stand-in for an httpx response carrying one batch of vectors."""

    def __init__(self, n: int):
        self._n = n

    def raise_for_status(self) -> None:  # noqa: D102 - trivial
        return None

    def json(self) -> dict:
        # Each input text maps to a distinct, correctly-sized vector so callers
        # can assert both count and ordering.
        return {"embeddings": [[float(i)] * EMBEDDING_DIM for i in range(self._n)]}


class _FakeClient:
    """Async-context-manager fake that records the size of every embed request."""

    batch_sizes: list[int] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, _url, json):  # noqa: A002 - mirror httpx signature
        n = len(json["input"])
        type(self).batch_sizes.append(n)
        return _FakeResponse(n)


async def test_embed_batches_large_inputs(monkeypatch):
    """A 70-text request is split into 32/32/6 sub-requests, all dimensions valid."""
    _FakeClient.batch_sizes = []
    monkeypatch.setattr(embeddings.httpx, "AsyncClient", _FakeClient)

    vectors = await embed([f"text {i}" for i in range(70)])

    assert _FakeClient.batch_sizes == [32, 32, 6]
    assert len(vectors) == 70
    assert all(len(v) == EMBEDDING_DIM for v in vectors)


async def test_embed_empty_input_makes_no_request(monkeypatch):
    """An empty input list returns [] without hitting the embed endpoint."""
    _FakeClient.batch_sizes = []
    monkeypatch.setattr(embeddings.httpx, "AsyncClient", _FakeClient)

    assert await embed([]) == []
    assert _FakeClient.batch_sizes == []
