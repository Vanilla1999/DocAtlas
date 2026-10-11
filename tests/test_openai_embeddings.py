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





