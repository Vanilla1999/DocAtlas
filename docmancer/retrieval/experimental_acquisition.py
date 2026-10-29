"""Fixed, non-semantic work ceilings for native lexical acquisition.

Chosen before runtime; see reports/docatlas-grounded-20261013/heuristic-removal/
A_ACQUISITION.md. These are not final context budgets or completeness guarantees.
"""
from __future__ import annotations

import os

ACQUISITION_CANDIDATES = 256
ACQUISITION_ESTIMATED_TOKENS = 131_072
ACQUISITION_TEXT_BYTES = 1_048_576
ACQUISITION_METHOD = "fts5_bm25_equal_fields_or_v1"

ACQUISITION_POLICY_ENV = "DOCATLAS_ACQUISITION_POLICY"
ACQUISITION_POLICIES = ("main", "retrieval_text", "rrf")
ACQUISITION_RRF_K = 60
_METHODS = {
    "main": ACQUISITION_METHOD,
    "retrieval_text": "fts5_bm25_retrieval_text_or_v1",
    "rrf": "fts5_bm25_two_view_rrf_v1",
}


def resolve_acquisition_policy(value: str | None = None) -> str:
    """Read a host-only experiment setting; request/source text cannot set it."""
    policy = os.environ.get(ACQUISITION_POLICY_ENV, "main") if value is None else value
    if policy not in ACQUISITION_POLICIES:
        raise ValueError("invalid_DOCATLAS_ACQUISITION_POLICY")
    return policy


def acquisition_method(policy: str) -> str:
    return _METHODS[resolve_acquisition_policy(policy)]


def acquisition_view_limits(policy: str, limit: int = ACQUISITION_CANDIDATES) -> dict[str, int]:
    """Allocate one aggregate returned-row budget, not 256 rows per view."""
    policy = resolve_acquisition_policy(policy)
    if limit < 0:
        raise ValueError("acquisition row limit must be non-negative")
    bounded = min(limit, ACQUISITION_CANDIDATES)
    if policy == "rrf":
        first = bounded // 2
        return {"all_fields": first, "retrieval_text": bounded - first}
    return {"all_fields" if policy == "main" else "retrieval_text": bounded}


def acquisition_policy_config(policy: str) -> dict:
    """Version the opt-in search procedure without changing the main receipt."""
    policy = resolve_acquisition_policy(policy)
    if policy == "main":
        return {}
    result = {
        "acquisition_policy": policy,
        "views": acquisition_view_limits(policy),
        "query_terms": "quoted_original_word_tokens_or",
        "retrieval_text_weights": [0.0, 1.0, 0.0],
    }
    if policy == "rrf":
        result["rrf_k"] = ACQUISITION_RRF_K
    return result
