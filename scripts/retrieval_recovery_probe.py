from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path

from eval.evidence_quality_v2.run import run


OUTPUT = Path("/tmp/docatlas-systemic-full-probe")


def _status(row: dict) -> str:
    return str((row.get("assessment") or {}).get("context_sufficiency") or "unknown")


def _payload_sources(row: dict) -> list[dict]:
    result: list[dict] = []
    for source in (row.get("payload") or {}).get("sources", []):
        if not isinstance(source, dict):
            continue
        result.append({
            "path": source.get("path_or_url") or source.get("source_path") or source.get("source"),
            "line_start": source.get("line_start"),
            "line_end": source.get("line_end"),
            "evidence_id": source.get("evidence_id") or source.get("stable_chunk_id"),
        })
    return result


def main() -> int:
    shutil.rmtree(OUTPUT, ignore_errors=True)
    run(OUTPUT)

    case_doc = json.loads(Path("eval/evidence_quality_v2/cases.json").read_text(encoding="utf-8"))
    cases = {str(case["id"]): case for case in case_doc["cases"]}
    rows = json.loads((OUTPUT / "rows.json").read_text(encoding="utf-8"))

    by_variant: dict[str, list[dict]] = {}
    for row in rows:
        case = cases.get(str(row.get("id")))
        if not case or case.get("answerability") != "within_budget":
            continue
        by_variant.setdefault(str(row.get("variant")), []).append(row)

    variant_counts = {
        variant: dict(sorted(Counter(_status(row) for row in variant_rows).items()))
        for variant, variant_rows in sorted(by_variant.items())
    }

    current = by_variant.get("A-current", [])
    failures: list[dict] = []
    for row in current:
        if _status(row) == "sufficient":
            continue
        case = cases[str(row["id"])]
        failures.append({
            "id": row["id"],
            "project": case.get("project_group"),
            "family": case.get("family"),
            "status": _status(row),
            "first_loss": (row.get("stage_assessment") or {}).get("first_observed_loss"),
            "budget_check": case.get("budget_check"),
            "payload_sources": _payload_sources(row),
        })

    current_by_project: dict[str, Counter] = {}
    for row in current:
        project = str(cases[str(row["id"])].get("project_group"))
        current_by_project.setdefault(project, Counter())[_status(row)] += 1

    report = {
        "schema_version": case_doc.get("schema_version"),
        "unseen_validation": case_doc.get("unseen_validation"),
        "within_budget_case_count": len(current),
        "variant_counts": variant_counts,
        "a_current_by_project": {
            project: dict(sorted(counts.items()))
            for project, counts in sorted(current_by_project.items())
        },
        "a_current_failures": failures,
    }
    print("SYSTEMIC_FULL_PROBE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
