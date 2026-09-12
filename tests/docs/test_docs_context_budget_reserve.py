from __future__ import annotations

import math

from docmancer.docs.application.model_visible_projection import (
    canonical_projection_bytes,
    docs_context_budget_tokens,
    estimate_projection_tokens,
)


def test_docs_context_budget_reserves_for_structured_token_density() -> None:
    payload = {
        "status": "ok",
        "kind": "docs_context",
        "answer_policy": "cite_only",
        "answer_supported": False,
        "answer_available": False,
        "edit_ready": False,
        "sources": [
            {
                "evidence_id": "ev-a",
                "path_or_url": "docs/reference/configuration.md",
                "section": "Configuration / strict-mode",
                "snippet": (
                    "`strict-mode=true` preserves source-bound behavior; "
                    "use `worker.pool.size=4`, `retry.max=3`, and avoid "
                    "assuming hidden defaults from a different version."
                ),
                "version_binding": "current",
                "content_sha256": "a" * 64,
                "project_identity": "project:test",
                "line_start": 10,
                "line_end": 14,
                "authority": "source_of_truth",
                "scope": "project",
            }
        ],
        "estimated_tokens": 0,
    }
    serialized_bytes = len(canonical_projection_bytes(payload))

    # Keep the public engineering estimate backward-compatible.
    assert estimate_projection_tokens(payload) == math.ceil(serialized_bytes / 4)
    # Admission also enforces the named offline codec, independently of the public estimate.
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    assert docs_context_budget_tokens(payload) == max(estimate_projection_tokens(payload), projection_token_count(canonical_projection_bytes(payload)))


def test_non_context_projection_keeps_existing_byte_estimator_contract() -> None:
    payload = {"status": "ok", "kind": "docs_answer", "answer": "plain text"}
    serialized_bytes = len(canonical_projection_bytes(payload))

    assert estimate_projection_tokens(payload) == math.ceil(serialized_bytes / 4)


def test_pinned_codec_is_offline_and_matches_reference_counts(monkeypatch) -> None:
    from docmancer.docs.application.projection_tokenizer import projection_encoder, projection_token_count
    import tiktoken.load
    def forbidden(*args, **kwargs):
        raise AssertionError('token accounting must never download its vocabulary')
    projection_encoder.cache_clear()
    monkeypatch.setattr(tiktoken.load, 'read_file', forbidden)
    assert projection_token_count(b'{"ids":[123,456],"hash":"abc123def456","ok":true}') == 18
    assert projection_token_count('Привет, мир! 日本語の文。 🚀'.encode()) == 12
    assert projection_token_count(b'x_y = {"key": "<|endoftext|>"}\n') == 14


def test_dense_identifiers_cannot_enter_on_byte_estimate_alone() -> None:
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    payload = {'sources': [{'snippet': ' '.join(f'x_{i:04x}' for i in range(150))}]}
    actual = projection_token_count(canonical_projection_bytes(payload))
    assert actual > estimate_projection_tokens(payload)
    assert docs_context_budget_tokens(payload) == actual
