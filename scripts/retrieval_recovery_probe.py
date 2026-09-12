from __future__ import annotations

import json
import shutil
from pathlib import Path

from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.evidence_quality_v2.run import run


ROOT = Path("/tmp/docatlas-cap-causal-probe")
BASELINE = ROOT / "baseline"
NO_CAP = ROOT / "no-cap"


def _rows(path: Path) -> dict[tuple[str, str], dict]:
    rows = json.loads((path / "rows.json").read_text(encoding="utf-8"))
    return {
        (str(row["id"]), str(row["variant"])): row
        for row in rows
        if str(row.get("id") or "").startswith("pydantic-")
    }


def _label(row: dict) -> str:
    return str(row.get("assessment", {}).get("context_sufficiency") or "")


def _payload_sources(row: dict) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for source in row.get("payload", {}).get("sources", []):
        result.append({
            "path": source.get("path_or_url") or source.get("source_path"),
            "line_start": source.get("line_start"),
            "line_end": source.get("line_end"),
            "snippet": str(source.get("snippet") or "")[:320],
        })
    return result


def _without_per_source_cap(self, chunks, *, limit=None, expand=None):
    """Counterfactual: remove only source quota, keep the public lane limit."""
    del self, expand
    values = list(chunks)
    return values[:limit] if limit is not None else values


def main() -> int:
    shutil.rmtree(ROOT, ignore_errors=True)
    run(BASELINE, projects=["pydantic"])

    original = RetrievalDispatcher._limit_sections_per_source
    try:
        RetrievalDispatcher._limit_sections_per_source = _without_per_source_cap
        run(NO_CAP, projects=["pydantic"])
    finally:
        RetrievalDispatcher._limit_sections_per_source = original

    baseline = _rows(BASELINE)
    no_cap = _rows(NO_CAP)
    changes: list[dict[str, object]] = []
    for key in sorted(set(baseline) | set(no_cap)):
        before = baseline.get(key, {})
        after = no_cap.get(key, {})
        before_label = _label(before)
        after_label = _label(after)
        if before_label == after_label and _payload_sources(before) == _payload_sources(after):
            continue
        changes.append({
            "id": key[0],
            "variant": key[1],
            "baseline": before_label,
            "no_cap": after_label,
            "baseline_sources": _payload_sources(before),
            "no_cap_sources": _payload_sources(after),
            "baseline_first_loss": before.get("stage_assessment", {}).get("first_observed_loss"),
            "no_cap_first_loss": after.get("stage_assessment", {}).get("first_observed_loss"),
        })

    print("CAP_CAUSAL_PROBE_BEGIN")
    print(json.dumps({
        "baseline_rows": len(baseline),
        "no_cap_rows": len(no_cap),
        "changed": changes,
    }, indent=2, ensure_ascii=False, sort_keys=True))
    print("CAP_CAUSAL_PROBE_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
