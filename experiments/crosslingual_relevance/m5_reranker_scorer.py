"""M5 with BGE reranker scorer — gold in first packet via dense + reranker rescue.

Replaces MPNet with BGE-reranker-v2-m3 cross-encoder as the rescue scorer.
Uses a diagnostic threshold selected after inspecting Typer scores. Results
are not independent calibration or acceptance evidence.

Usage:
    DOCATLAS_RERANKER_MODEL_DIR=... \
    DOCATLAS_RERANKER_MODEL_MANIFEST=... \
    python -m experiments.crosslingual_relevance.m5_reranker_scorer
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from eval.evidence_quality_v2.run import documents_for, load_protocol, audit_payload
from eval.evidence_quality_v2.runtime import write_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens

from experiments.crosslingual_relevance.context_rescue import installed, BoundedScorer
from experiments.crosslingual_relevance.m5_real_scorer import (
    _build_vector_service, _index_all, _check_gold,
    TYPER_TASKS, M15_DEV_TASKS, ALL_PROJECTS,
)
from experiments.crosslingual_relevance.bge_reranker_scorer import reranker_scorer, reranker_identity

RERANKER_THRESHOLD = 0.01  # Diagnostic only: selected after inspecting Typer.


def _run(max_sections_per_source: int = 20):
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="m5-reranker-"))
    print(f"Working directory: {tmp}")
    print(f"Model: {reranker_identity()}")
    print(f"Threshold: {RERANKER_THRESHOLD}")

    _, _, manifest = load_protocol()
    roots = {}
    for project in ALL_PROJECTS:
        docs = documents_for(project, manifest)
        root = tmp / "projects" / project
        write_project(root, docs)
        roots[project] = str(root)

    print("Building vector service...")
    service, config, patcher = _build_vector_service(tmp, max_sections_per_source=max_sections_per_source)
    try:
        _index_all(service, roots)
        print("All projects indexed with vectors.\n")

        print(f"\n{'='*60}")
        print("M5 with BGE reranker scorer")
        print(f"{'='*60}")

        results = []
        executions = []
        for task in TYPER_TASKS + M15_DEV_TASKS:
            root = roots[task["project"]]
            request = {"question": task["question"], "project_path": root, "scope": "all"}
            bounded = BoundedScorer(reranker_scorer, capture_text=True,
                                    score_range=(0.0, 1.0),
                                    max_evaluations=256, timeout=300.0)
            with installed(bounded, threshold=RERANKER_THRESHOLD, question=task["question"]):
                payload, trace = observe_call(service, request)
            errors = audit_payload(payload, trace["snapshot"], Path(root))
            r = _check_gold(payload, task, audit_errors=errors)
            r["scorer_executed"] = bounded.summary["evaluations"] > 0
            r["scorer_degraded"] = bounded.degraded
            r["scorer_model_verified"] = bounded.identity().get("verified") is True
            r["scorer_kind"] = "cross-encoder"
            executions.append({"request": request, "payload": payload, "trace": trace,
                               "scorer_events": bounded.events, "scorer_summary": bounded.summary})
            results.append(r)
            status = r["assessment"]["verdict"]
            print(f"  [{status}] {r['task_id']} ({r['formulation']}): "
                  f"gold_found={r['gold_found']} sources={r['total_sources']} "
                  f"budget={r['budget_tokens']} context_available={r['context_available']}")

        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        typer_results = [r for r in results if r["project"] == "typer"]
        m15_results = [r for r in results if r["project"] != "typer"]
        typer_pass = sum(1 for r in typer_results if r["assessment"]["verdict"] == "PASS")
        m15_pass = sum(1 for r in m15_results if r["assessment"]["verdict"] == "PASS")
        print(f"Typer (M0 target): {typer_pass}/{len(typer_results)}")
        print(f"M1.5 dev: {m15_pass}/{len(m15_results)}")

        output = {
            "schema_version": 2,
            "evaluation_kind": "reranker_rescue_with_canonical_claim_audit",
            "max_sections_per_source": max_sections_per_source,
            "scorer": reranker_identity(),
            "threshold": RERANKER_THRESHOLD,
            "executions": executions,
            "results": results,
            "summary": {
                "typer_pass": typer_pass, "typer_total": len(typer_results),
                "m15_pass": m15_pass, "m15_total": len(m15_results),
            },
        }
        from .evaluation_v2 import save_new_report
        out_path = Path("experiments/crosslingual_relevance/review_runs") / f"m5-reranker-{uuid.uuid4().hex}.json"
        save_new_report(out_path, json.loads(json.dumps(output, default=str)))
        print(f"\nResults saved to {out_path}")
    finally:
        patcher.stop()


def main():
    import argparse
    from .pinned_embedding_session import pinned_embeddings
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-sections-per-source", type=int, choices=(2, 20), default=20)
    args = parser.parse_args()
    with pinned_embeddings():
        _run(args.max_sections_per_source)


if __name__ == "__main__":
    main()
