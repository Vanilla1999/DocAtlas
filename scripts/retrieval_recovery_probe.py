from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from eval.evidence_quality_v2.run import run


OUTPUT = Path("/tmp/docatlas-systemic-insufficient-probe")
TARGETS = {"httpx-06", "pydantic-03", "typer-05"}
PROJECTS = ["httpx", "pydantic", "typer"]
STAGES = (
    "retrieved_candidates",
    "query_window",
    "rankings",
    "qualified_fragments",
    "expansions",
    "final_projection",
)


def _text(item: dict[str, Any]) -> str:
    for key in ("snippet", "display_text", "content", "text", "retrieval_text"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return ""


def _path(item: dict[str, Any]) -> str:
    for key in ("path_or_url", "source_path", "path", "source"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _compact(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": _path(item),
        "line_start": item.get("line_start"),
        "line_end": item.get("line_end"),
        "stable_chunk_id": item.get("stable_chunk_id"),
        "evidence_id": item.get("evidence_id"),
        "qualified": item.get("qualified"),
        "qualification_reason": item.get("qualification_reason") or item.get("reason"),
        "query_id": item.get("query_id"),
        "route": item.get("retrieval_route") or item.get("route"),
        "score": item.get("score") or item.get("rank") or item.get("rerank_score"),
        "text": _text(item)[:500],
    }


def _sourceish(value: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        if _text(value) and (_path(value) or value.get("stable_chunk_id") or value.get("evidence_id")):
            out.append(_compact(value))
        for nested in value.values():
            _sourceish(nested, out)
    elif isinstance(value, list):
        for nested in value:
            _sourceish(nested, out)


def _stage_summary(trace: dict[str, Any], stage: str) -> dict[str, Any]:
    calls = (trace.get("stages") or {}).get(stage, [])
    found: list[dict[str, Any]] = []
    _sourceish(calls, found)
    dedup: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in found:
        key = (
            item["path"], item["line_start"], item["line_end"],
            item["stable_chunk_id"], item["evidence_id"], item["text"],
        )
        dedup[key] = item
    return {
        "call_count": len(calls) if isinstance(calls, list) else 0,
        "sources": list(dedup.values())[:30],
        "call_keys": [sorted(call.keys()) for call in calls[:4] if isinstance(call, dict)],
    }


def _case_summary(case: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "id", "question", "family", "project_group", "answerability",
        "gold_witness", "gold_witnesses", "gold", "expected", "budget_check",
    )
    return {key: case[key] for key in keep if key in case}


def main() -> int:
    shutil.rmtree(OUTPUT, ignore_errors=True)
    run(OUTPUT, projects=PROJECTS)

    case_doc = json.loads(Path("eval/evidence_quality_v2/cases.json").read_text(encoding="utf-8"))
    cases = {str(case["id"]): case for case in case_doc["cases"]}
    rows = json.loads((OUTPUT / "rows.json").read_text(encoding="utf-8"))
    report: list[dict[str, Any]] = []

    for row in rows:
        case_id = str(row.get("id"))
        if case_id not in TARGETS or row.get("variant") != "A-current":
            continue
        trace = json.loads(
            (OUTPUT / "traces" / "A-current" / f"{case_id}.json").read_text(encoding="utf-8")
        )
        report.append({
            "case": _case_summary(cases[case_id]),
            "assessment": row.get("assessment"),
            "stage_assessment": row.get("stage_assessment"),
            "payload": row.get("payload"),
            "stages": {stage: _stage_summary(trace, stage) for stage in STAGES},
        })

    print("SYSTEMIC_INSUFFICIENT_PROBE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
