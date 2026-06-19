"""OpenAI embeddings provider: batching, retry, transient error sniffing."""
from __future__ import annotations

import sys
import types

import pytest


def _install_fake_openai(monkeypatch, *, fail_first: int = 0, status_code: int = 429) -> dict:
    """Install a stub ``openai`` module in ``sys.modules`` for the provider import."""
    state = {"calls": [], "remaining_failures": fail_first}

    class FakeRateLimit(Exception):
        def __init__(self, msg="rate limited") -> None:
            super().__init__(msg)
            self.status_code = status_code

    class FakeResp:
        def __init__(self, vectors):
            self.data = [types.SimpleNamespace(embedding=v) for v in vectors]

    class FakeEmbeddings:
        def __init__(self, client):
            self._client = client

        def create(self, *, model, input, dimensions=None, **kwargs):
            self._client.calls.append({"model": model, "input": list(input), "dimensions": dimensions})
            if self._client.remaining_failures > 0:
                self._client.remaining_failures -= 1
                raise FakeRateLimit()
            # Echo deterministic vectors so tests can assert on order.
            return FakeResp([[float(len(t)), 1.0, 2.0, 3.0] for t in input])

    class FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.calls = state["calls"]
            self.remaining_failures = state["remaining_failures"]
            self.embeddings = FakeEmbeddings(self)
            # Mirror state back so the test can inspect after the fact.
            state["client"] = self

    fake_module = types.SimpleNamespace(OpenAI=FakeOpenAI, RateLimitError=FakeRateLimit)
    monkeypatch.setitem(sys.modules, "openai", fake_module)
    return state


def test_openai_provider_requires_api_key(monkeypatch):
    _install_fake_openai(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from docmancer.core.config import EmbeddingsConfig
    from docmancer.embeddings.openai_provider import OpenAIProvider

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIProvider(EmbeddingsConfig(provider="openai"))


def test_openai_provider_batches_inputs(monkeypatch):
    state = _install_fake_openai(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from docmancer.core.config import EmbeddingsConfig
    from docmancer.embeddings.openai_provider import OpenAIProvider

    provider = OpenAIProvider(
        EmbeddingsConfig(provider="openai", model="text-embedding-3-small", dimensions=1536, batch_size=2)
    )
    texts = [f"text-{i}" for i in range(5)]
    out = provider.embed(texts)
    assert len(out) == 5
    # 5 inputs with batch_size=2 → 3 calls: 2 + 2 + 1.
    assert len(state["calls"]) == 3
    assert [len(c["input"]) for c in state["calls"]] == [2, 2, 1]
    # All requests carried the configured dimensions for text-embedding-3-*.
    assert all(c["dimensions"] == 1536 for c in state["calls"])


def test_openai_provider_retries_on_rate_limit(monkeypatch):
    state = _install_fake_openai(monkeypatch, fail_first=2)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    # Make backoff sleeps a no-op so the test is instant.
    import docmancer.embeddings.openai_provider as mod

    monkeypatch.setattr(mod.time, "sleep", lambda *a, **kw: None)

    from docmancer.core.config import EmbeddingsConfig

    provider = mod.OpenAIProvider(EmbeddingsConfig(provider="openai", batch_size=4))
    out = provider.embed(["hello"])
    assert len(out) == 1
    # Two failures + one success → three SDK calls.
    assert len(state["calls"]) == 3
