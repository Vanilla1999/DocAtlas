"""Opt-in, process-local ordering experiment. Never install in a running server.

This adapter changes no retrieval, qualification, source policy, snippets, query
plan, coverage, token limit, or default product behavior. Use sequentially in a
throw-away diagnostic/test process; unittest.mock.patch is not thread-local.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from unittest.mock import patch

from docmancer.docs.application.context_candidate_ranking import (
    _prefer_missing_baseline_candidate as _baseline_preference,
)

REVISION = 'single-host-original-protection-v1-development'


def prefer_original_baseline(
    candidates: list[Any], selected: list[dict[str, Any]],
    public_query_ids: set[str], host_query_ids: set[str],
    canonical_query_ids: set[str],
) -> None:
    """For one host lookup, protect the original, not optional anchor aliases.

    Keep the existing multi-lookup diversity and canonical fallback behavior.
    Removing aliases here does NOT remove their public query IDs, candidates,
    explicit-path checks, or coverage from the real projection; it only avoids
    promoting them under the misleading name of baseline protection.
    """
    protected_public = public_query_ids
    if len(host_query_ids) == 1:
        protected_public = public_query_ids & (host_query_ids | {'query-original'})
    _baseline_preference(candidates, selected, protected_public,
                         host_query_ids, canonical_query_ids)


@contextmanager
def packing_experiment() -> Iterator[None]:
    """Explicit temporary opt-in; restore the exact previous hook on every exit."""
    from docmancer.docs.application import _docs_context_projection_core as core
    with patch.object(core, '_prefer_missing_baseline_candidate', prefer_original_baseline):
        yield
