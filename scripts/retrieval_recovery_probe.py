from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from eval.evidence_quality_v2.run import run


OUTPUT = Path("/tmp/docatlas-projector-boundary-probe")


def _match_summary(matches: Any) -> dict[str, Any]:
    if not isinstance(matches, dict):
        return {}
    result: dict[str, Any] = {}
    for query_id, trace in matches.items():
        if not isinstance(trace, dict):
            continue
        result[str(query_id)] = {
            key: trace.get(key)
            for key in (
                "qualified", "qualification_reason", "relation", "query_text",
                "query_terms", "exact_terms", "parent_exact_terms",
                "matched_terms", "missing_exact_terms", "missing_parent_exact_terms",
                "match_ratio", "public_parent_query_id", "derived_from_query_id",
            )
            if key in trace
        }
    return result


def _candidate_summary(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        return {"type": type(candidate).__name__}
    metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
    content = candidate.get("content") or candidate.get("display_text") or candidate.get("snippet") or ""
    return {
        "id": candidate.get("stable_id") or candidate.get("stable_chunk_id") or candidate.get("evidence_id") or metadata.get("stable_chunk_id"),
        "path": candidate.get("path") or candidate.get("source") or metadata.get("project_doc_path") or metadata.get("source_path"),
        "line_span": candidate.get("line_span") or metadata.get("line_span"),
        "project_identity": candidate.get("project_identity") or metadata.get("project_identity"),
        "authority": candidate.get("authority") or metadata.get("project_doc_authority"),
        "content": " ".join(str(content).split())[:650],
        "retrieval_query_ids": candidate.get("retrieval_query_ids") or metadata.get("retrieval_query_ids"),
        "matches": _match_summary(candidate.get("retrieval_query_matches") or metadata.get("retrieval_query_matches")),
    }


def main() -> int:
    from docmancer.docs.application import docs_context_projection as projection

    shutil.rmtree(OUTPUT, ignore_errors=True)
    run(OUTPUT, projects=["httpx"])
    trace = json.loads((OUTPUT / "traces" / "A-current" / "httpx-06.json").read_text(encoding="utf-8"))
    raw = json.loads((OUTPUT / "raw" / "A-current" / "httpx-06.json").read_text(encoding="utf-8"))
    projector_inputs = trace.get("stages", {}).get("projector_inputs", [])
    assert len(projector_inputs) == 1
    retrieval = deepcopy(projector_inputs[0])
    selection_diag: dict[str, Any] = {}
    payload, snapshot = projection.project_docs_context(
        retrieval=retrieval,
        max_tokens=800,
        selection_diagnostics=selection_diag,
    )
    qplan = retrieval.get("documentation_query_plan") or {}
    query_summary = [
        {
            key: item.get(key)
            for key in (
                "query_id", "text", "origin", "relation", "public_parent_query_id",
                "requirement_id", "facet_id", "mandatory",
            )
            if isinstance(item, dict) and key in item
        }
        for item in qplan.get("queries", [])
        if isinstance(item, dict)
    ]
    report = {
        "row_status": (raw.get("assessment") or {}).get("context_sufficiency"),
        "payload": payload,
        "query_plan": {
            "original_question": qplan.get("original_question"),
            "public_query_ids": qplan.get("public_query_ids"),
            "required_query_ids": qplan.get("required_query_ids"),
            "unresolved_parts": qplan.get("unresolved_parts"),
            "component_scope_complete": qplan.get("component_scope_complete"),
            "queries": query_summary,
        },
        "context_pack": [_candidate_summary(item) for item in retrieval.get("context_pack", [])],
        "projection_diagnostics": (retrieval.get("retrieval_diagnostics") or {}).get("docs_context_projection"),
        "selection_diagnostics": selection_diag,
        "snapshot_keys": sorted(snapshot),
    }
    print("PROJECTOR_BOUNDARY_PROBE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
