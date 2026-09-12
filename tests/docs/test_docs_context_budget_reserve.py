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
    # Admission for docs_context is deliberately more conservative.
    assert docs_context_budget_tokens(payload) >= math.ceil(serialized_bytes / 3)
    assert docs_context_budget_tokens(payload) > estimate_projection_tokens(payload)


def test_non_context_projection_keeps_existing_byte_estimator_contract() -> None:
    payload = {"status": "ok", "kind": "docs_answer", "answer": "plain text"}
    serialized_bytes = len(canonical_projection_bytes(payload))

    assert estimate_projection_tokens(payload) == math.ceil(serialized_bytes / 4)
