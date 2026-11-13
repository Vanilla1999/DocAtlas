"""Start the real DocAtlas stdio MCP docs server with passive observers.

run.py starts this file instead of ``doc-atlas mcp docs-serve`` so that it can
report, per question, whether internal ceilings were reached. docmancer is
imported from PYTHONPATH (the source tree under test). When
``BLIND_OBSERVER_LOG`` is set, two existing methods are wrapped; each wrapper
calls the original, appends one JSON line and returns the original object:

* ``SQLiteStore.acquire_candidates``: the counters the store already attaches
  to every candidate (SQL rows before the 256-candidate ceiling, admitted rows,
  rows skipped by the token/byte ceilings) and, when ``BLIND_OBSERVER_FACTS``
  names a JSON list of ``{"fact_id", "quote"}``, the rank of the first
  returned candidate whose text contains each quote, so a missed fact can be
  told apart: never acquired, or acquired and dropped later;
* ``ProjectMetadataReader.read``: catalogued candidates and any wall-clock or
  byte truncation warning of document discovery.

Without the variable nothing is wrapped. run.py --no-observer exists to show
that delivered context is identical either way.
"""
from __future__ import annotations

import json
import os
import sys

if sys.path and os.path.abspath(sys.path[0]) == os.path.dirname(os.path.abspath(__file__)):
    sys.path.pop(0)

LOG = os.environ.get("BLIND_OBSERVER_LOG")
FACTS = os.environ.get("BLIND_OBSERVER_FACTS")


def _append(event: dict) -> None:
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _install() -> None:
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.docs.project import ProjectMetadataReader

    acquire = SQLiteStore.acquire_candidates
    read = ProjectMetadataReader.read
    facts = {}
    if FACTS:
        with open(FACTS, encoding="utf-8") as handle:
            facts = {item["fact_id"]: item["quote"] for item in json.load(handle)}

    def observed_acquire(self, text, *args, **kwargs):
        chunks = acquire(self, text, *args, **kwargs)
        counters = dict((chunks[0].metadata or {}).get("acquisition") or {}) if chunks else {}
        ranks = {}
        for rank, chunk in enumerate(chunks, start=1):
            body = chunk.text or ""
            for fact_id, quote in facts.items():
                if fact_id not in ranks and quote in body:
                    ranks[fact_id] = rank
        _append({"event": "acquisition", "text": text, "expand": kwargs.get("expand"),
                 "filters": kwargs.get("filters"), "returned_rows": len(chunks), "fact_ranks": ranks,
                 **counters})
        return chunks

    def observed_read(self, project_path, *args, **kwargs):
        metadata = read(self, project_path, *args, **kwargs)
        _append({"event": "catalog_read", "candidates": len(metadata.docs_candidates),
                 "truncation_warnings": [w for w in metadata.warnings if "truncated" in w]})
        return metadata

    SQLiteStore.acquire_candidates = observed_acquire
    ProjectMetadataReader.read = observed_read

    if os.environ.get("BLIND_OBSERVER_SELECTION") == "1":
        _install_selection(facts)

    if os.environ.get("BLIND_OBSERVER_EVIDENCE") == "1":
        _install_evidence_receipt()


def _install_evidence_receipt() -> None:
    """Log per-call receipts of the opt-in Qwen evidence scorer.

    Pure instrumentation: the wrapped function and its arguments are unchanged,
    only the returned receipt is appended to the observer log.
    """
    from docmancer.docs.application import context_evidence_scoring as scoring

    original = scoring.score_evidence_units

    def observed_score(query, identities, documents, model_path, **kwargs):
        scores, receipt = original(query, identities, documents, model_path, **kwargs)
        _append({"event": "evidence_scoring",
                 "units": len(identities),
                 "scored_units": len(scores),
                 "forwards": receipt.get("model_forwards"),
                 "input_tokens": receipt.get("model_input_tokens"),
                 "inference_seconds": receipt.get("inference_seconds"),
                 "peak_vram_allocated_bytes": receipt.get("peak_vram_allocated_bytes"),
                 "status": receipt.get("status")})
        return scores, receipt

    scoring.score_evidence_units = observed_score


def _install_selection(facts: dict[str, str]) -> None:
    """Optional loss-stage observation; gold never reaches a ranking function.

    Only the first portion's stage decisions are classified. Later portions
    replay earlier selections, so attributing their last trace to the entire
    pool would be misleading. Final cumulative delivery is scored separately.
    """
    from contextvars import ContextVar
    from docmancer.docs.application import joint_context_selection as joint
    from docmancer.docs.application.query_trace import query_trace

    selection = joint.select_joint_context
    prune = joint.prune_checked_pool
    pruning = ContextVar("blind_pool_pruning", default=None)

    def observed_prune(payload, *args, **kwargs):
        before = {row["evidence_id"] for row in payload.get("sources") or ()}
        result = prune(payload, *args, **kwargs)
        current = pruning.get()
        if current is not None:
            current.update(before - {row["evidence_id"] for row in result[0].get("sources") or ()})
        return result

    def observed_selection(payload, snapshot, retrieval, *args, **kwargs):
        if kwargs.get("portion", 1) != 1:
            return selection(payload, snapshot, retrieval, *args, **kwargs)
        rows = payload.get("sources") or []
        checked = {fact_id: [row["evidence_id"] for row in rows if quote in row.get("snippet", "")]
                   for fact_id, quote in facts.items()}
        removed: set[str] = set()
        token = pruning.set(removed)
        try:
            with query_trace(True):
                result = selection(payload, snapshot, retrieval, *args, **kwargs)
        finally:
            pruning.reset(token)
        delivered = {row["evidence_id"] for row in result[0].get("sources") or ()}
        trace = ((retrieval.get("retrieval_diagnostics") or {}).get("docs_context_projection") or {}).get(
            "joint_selection_observation") or {}
        decisions = {row["evidence_id"]: row.get("decision", "unobserved") for row in trace.get("rows", ())}
        fact_stages = {}
        for fact_id, ids in checked.items():
            stages = sorted({"delivered" if row_id in delivered else
                             "pool_pruning" if row_id in removed else
                             "delivery_finalization" if decisions.get(row_id) == "selected" else
                             decisions.get(row_id, "unobserved") for row_id in ids})
            fact_stages[fact_id] = {"checked_rows": len(ids), "stages": stages}
        _append({"event": "joint_selection", "portion": 1, "checked_rows": len(rows),
                 "pruned_rows": len(removed), "selected_rows": len(delivered),
                 "trace_omitted_rows": trace.get("omitted_rows", 0), "fact_stages": fact_stages})
        return result

    joint.prune_checked_pool = observed_prune
    joint.select_joint_context = observed_selection


if LOG:
    _install()

from docmancer.cli.__main__ import cli  # noqa: E402

sys.argv = ["doc-atlas", "mcp", "docs-serve"]
cli()
