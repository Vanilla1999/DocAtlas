from __future__ import annotations

import json
import shutil
from pathlib import Path

from eval.evidence_quality_v2.run import run


OUTPUT = Path("/tmp/docatlas-retrieval-recovery-probe")


def _short_source(source: dict) -> dict:
    return {
        "path": source.get("path_or_url") or source.get("source_path"),
        "line_start": source.get("line_start"),
        "line_end": source.get("line_end"),
        "snippet": str(source.get("snippet") or source.get("display_text") or "")[:500],
        "evidence_id": source.get("evidence_id") or source.get("stable_chunk_id"),
    }


def main() -> int:
    shutil.rmtree(OUTPUT, ignore_errors=True)
    run(OUTPUT, projects=["pydantic"])
    rows = json.loads((OUTPUT / "rows.json").read_text(encoding="utf-8"))
    rows = [row for row in rows if row.get("id") == "pydantic-02"]
    report: dict[str, object] = {"rows": []}
    for row in rows:
        variant = str(row["variant"])
        trace = json.loads(
            (OUTPUT / "traces" / variant / "pydantic-02.json").read_text(encoding="utf-8")
        )
        stage_report: dict[str, object] = {}
        for stage in (
            "retrieved_candidates",
            "query_window",
            "rankings",
            "qualified_fragments",
            "expansions",
        ):
            calls = trace.get("stages", {}).get(stage, [])
            compact_calls = []
            for call in calls:
                compact: dict[str, object] = {
                    key: value
                    for key, value in call.items()
                    if key not in {"sources", "before", "after"}
                }
                for key in ("sources", "before", "after"):
                    value = call.get(key)
                    if isinstance(value, list):
                        compact[key] = [_short_source(item) for item in value]
                    elif isinstance(value, dict):
                        compact[key] = _short_source(value)
                compact_calls.append(compact)
            stage_report[stage] = compact_calls
        report["rows"].append(
            {
                "variant": variant,
                "sufficiency": row.get("assessment", {}).get("context_sufficiency"),
                "literal_required": row.get("literal_required"),
                "first_loss": row.get("stage_assessment", {}).get("first_observed_loss"),
                "payload_sources": [_short_source(item) for item in row.get("payload", {}).get("sources", [])],
                "stages": stage_report,
            }
        )
    print("RECOVERY_PROBE_BEGIN")
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    print("RECOVERY_PROBE_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
