"""OpenAI embeddings provider.

Defaults to ``text-embedding-3-small`` (1536-d) which is the cheapest
modern OpenAI embedding model and a good fit for production RAG setups
that prefer API embeddings over downloading FastEmbed models into a
container. Switch to ``text-embedding-3-large`` (3072-d) by setting
``embeddings.model`` + ``embeddings.dimensions`` in YAML.

Batches up to ``max_batch_size`` items per request (OpenAI accepts large
batches but raises 400 if the cumulative token count exceeds the model
limit; callers can lower ``embeddings.batch_size`` if they trip that).
Retries 429 and 5xx with exponential backoff so a transient rate-limit
spike does not abort a long ingest.
"""
from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any

from .base import EmbeddingsProvider

if TYPE_CHECKING:
    from docmancer.core.config import EmbeddingsConfig

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RETRIES = 5
_RETRY_BASE_DELAY_S = 1.0


class OpenAIProvider(EmbeddingsProvider):
    """Dense embeddings via the OpenAI HTTP API.

    Streams retries with bounded exponential backoff on 429 / 5xx
    responses. Sparse embeddings are not supported by the OpenAI API.
    """

    name = "openai"

    def __init__(self, config: "EmbeddingsConfig") -> None:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "openai embeddings require the 'embeddings-openai' extra; "
                "install with `pip install docmancer[embeddings-openai]`."
            ) from exc
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is not set")
        base_url = os.environ.get("OPENAI_BASE_URL") or None
        # The OpenAI SDK uses OPENAI_BASE_URL automatically; passing it
        # explicitly here lets callers point at a compatible provider
        # (Azure OpenAI, vLLM, etc.) without juggling env vars.
        self._client: Any = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        self.model_name = config.model or "text-embedding-3-small"
        self.dimensions = int(config.dimensions or 1536)
        # OpenAI's docs cap a single embeddings request at 2048 inputs.
        # We default to 128 to stay well under per-request token caps.
        self.max_batch_size = int(getattr(config, "batch_size", 128) or 128)

    # ------------------ retry helper ------------------

    def _embed_once(self, texts: list[str]) -> list[list[float]]:
        # Pass dimensions only when the model supports it (3-small / 3-large /
        # newer). The legacy ada-002 model rejects the parameter; gate by
        # model name prefix.
        kwargs: dict[str, Any] = {"model": self.model_name, "input": texts}
        if self.model_name.startswith("text-embedding-3") and self.dimensions:
            kwargs["dimensions"] = self.dimensions
        resp = self._client.embeddings.create(**kwargs)
        # OpenAI guarantees the order of data matches the input order.
        return [list(map(float, item.embedding)) for item in resp.data]

    def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        last_exc: Exception | None = None
        for attempt in range(_DEFAULT_MAX_RETRIES):
            try:
                return self._embed_once(texts)
            except Exception as exc:  # OpenAI exceptions are not stable across SDK versions
                if not _is_transient(exc):
                    raise
                last_exc = exc
                delay = _RETRY_BASE_DELAY_S * (2**attempt)
                logger.warning(
                    "openai embeddings transient error (attempt %d/%d): %s. Retrying in %.1fs",
                    attempt + 1,
                    _DEFAULT_MAX_RETRIES,
                    type(exc).__name__,
                    delay,
                )
                time.sleep(delay)
        assert last_exc is not None
        raise last_exc

    # ------------------ EmbeddingsProvider API ------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        bs = max(1, self.max_batch_size)
        for start in range(0, len(texts), bs):
            chunk = texts[start : start + bs]
            out.extend(self._embed_with_retry(chunk))
        return out

    def embed_query(self, query: str) -> list[float]:
        return self.embed([query])[0]

    def health_check(self) -> bool:
        try:
            self.embed_query("health")
            return True
        except Exception:
            return False


def _is_transient(exc: Exception) -> bool:
    """Best-effort: 429 + 5xx are retryable, everything else is not."""
    # The OpenAI SDK raises typed errors with `status_code` attributes
    # in v1.x. We don't import the types because they have moved between
    # minor releases; we sniff the exception class + status instead.
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None) if response is not None else None
    if status in (408, 409, 429) or (status is not None and 500 <= int(status) < 600):
        return True
    name = type(exc).__name__.lower()
    return any(
        keyword in name
        for keyword in ("ratelimit", "timeout", "apierror", "connection", "servererror")
    )
