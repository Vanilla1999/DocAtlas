from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.evidence_quality_v2.run import run


ROOT = Path("/tmp/docatlas-cap-policy-probe")
CURRENT = ROOT / "current"
HARD = ROOT / "hard-cap"


def _hard_per_source_cap(self, chunks, *, limit=None, expand=None):
    if (expand or "").lower() in {"adjacent", "page"}:
        return chunks
    max_per_source = getattr(self.config.retrieval, "max_sections_per_source", None)
    if not max_per_source:
        return list(chunks)[:limit] if limit is not None else list(chunks)
    counts: dict[str, int] = {}
    out: list[Any] = []
    for chunk in chunks:
        metadata = getattr(chunk, "metadata", {}) or {}
        source = str(metadata.get("canonical_url") or getattr(chunk, "source", "") or "")
        count = counts.get(source, 0)
        if count >= int(max_per_source):
            continue
        counts[source] = count + 1
        out.append(chunk)
        if limit is not None and len(out) >= limit:
            break
    return out


def _a_current(path: Path, case_id: str) -> dict[str, Any]:
    rows = json.loads((path / "rows.json").read_text(encoding="utf-8"))
    return next(
        row for row in rows
        if row.get("id") == case_id and row.get("variant") == "A-current"
    )


def _compact_sources(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "path": source.get("path_or_url"),
            "line_start": source.get("line_start"),
            "line_end": source.get("line_end"),
            "snippet": str(source.get("snippet") or "")[:320],
        }
        for source in row.get("payload", {}).get("sources", [])
    ]


def _summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sufficiency": row.get("assessment", {}).get("context_sufficiency"),
        "first_loss": row.get("stage_assessment", {}).get("first_observed_loss"),
        "sources": _compact_sources(row),
    }


def main() -> int:
    shutil.rmtree(ROOT, ignore_errors=True)

    run(CURRENT, projects=["pydantic"])

    original = RetrievalDispatcher._limit_sections_per_source
    try:
        RetrievalDispatcher._limit_sections_per_source = _hard_per_source_cap
        run(HARD, projects=["pydantic"])
    finally:
        RetrievalDispatcher._limit_sections_per_source = original

    report: dict[str, Any] = {}
    for case_id in ("pydantic-01", "pydantic-02"):
        current = _a_current(CURRENT, case_id)
        hard = _a_current(HARD, case_id)
        report[case_id] = {
            "current": _summary(current),
            "hard_cap": _summary(hard),
        }

    print("CAP_POLICY_PROBE_BEGIN")
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    print("CAP_POLICY_PROBE_END")

    expected = {
        "pydantic-01": ("sufficient", "sufficient"),
        "pydantic-02": ("sufficient", "insufficient"),
    }
    for case_id, (current_expected, hard_expected) in expected.items():
        current_label = report[case_id]["current"]["sufficiency"]
        hard_label = report[case_id]["hard_cap"]["sufficiency"]
        if (current_label, hard_label) != (current_expected, hard_expected):
            raise SystemExit(
                f"unexpected {case_id} outcome: current={current_label}, hard={hard_label}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
