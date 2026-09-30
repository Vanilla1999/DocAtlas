"""Opt-in multi-host ordering ablation; never install in a concurrent server.

Only orders already qualified objects. Complete matching against an audited
rewrite is NOT completion of its parent question and NEVER grants authority.
This experiment is distinct from the frozen one-host live pilot intervention.
"""
from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Iterator
from unittest.mock import patch
from docmancer.docs.application.context_candidate_ranking import _fully_matched_query_ids
from .packing_experiment import prefer_original_baseline

REVISION = 'multi-host-audited-direction-diversity-v1-development'


def _audited_ids(source: dict, hosts: set[str], canonical: set[str]) -> set[str]:
    return {key for key, trace in (source.get('retrieval_query_matches') or {}).items()
        if key in canonical and isinstance(trace, dict)
        and trace.get('qualified') is True and not trace.get('admission_only')
        and trace.get('query_origin') == 'canonical_intent'
        and trace.get('relation') == 'audited_rewrite'
        and not trace.get('derived_from_query_id')
        and trace.get('public_parent_query_id') in hosts
        and trace.get('match_ratio') == 1.0}


def prefer_audited_diversity(candidates: list[dict[str, Any]], selected: list[dict],
                             public: set[str], hosts: set[str], canonical: set[str]) -> None:
    """Keep an opportunity for unrepresented fully matched audited directions.

    A directly complete host leader keeps its existing priority. Rewrites never
    mark host queries complete. Zero/single-host behavior is exactly unchanged.
    No source text, query plan, qualifications, objects or budget is modified.
    """
    if len(hosts) > 1 and candidates:
        missing_hosts = hosts - _fully_matched_query_ids(selected)
        direct_leader = _fully_matched_query_ids((candidates[0],)) & missing_hosts
        if not direct_leader:
            covered: set[str] = set()
            for source in selected:
                covered.update(_audited_ids(source, missing_hosts, canonical))
            for index, source in enumerate(candidates):
                if _audited_ids(source, missing_hosts, canonical) - covered:
                    candidates.insert(0, candidates.pop(index))
                    return
    prefer_original_baseline(candidates, selected, public, hosts, canonical)


@contextmanager
def flow_experiment() -> Iterator[None]:
    """Explicit process-local opt-in. Restores previous hook even on failure."""
    from docmancer.docs.application import _docs_context_projection_core as core
    with patch.object(core, '_prefer_missing_baseline_candidate', prefer_audited_diversity):
        yield
