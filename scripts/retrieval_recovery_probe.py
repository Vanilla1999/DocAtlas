from __future__ import annotations

import json
import shutil
from pathlib import Path

from eval.evidence_quality_v2.run import run


OUTPUT = Path("/tmp/docatlas-retrieval-recovery-probe")
QUESTION_NEEDLES = ("uuid", "strict", "json", "python")


def _text(item: dict) -> str:
    return str(
        item.get("snippet")
        or item.get("display_text")
        or item.get("text")
        or item.get("content")
        or ""
    )


def _source_key(item: dict) -> str:
    return str(
        item.get("evidence_id")
        or item.get("stable_chunk_id")
        or item.get("chunk_id")
        or item.get("source_id")
        or ""
    )


def _path(item: dict) -> str:
    return str(item.get("path_or_url") or item.get("source_path") or item.get("source") or "")


def _compact(item: dict) -> dict:
    text = _text(item)
    return {
        "key": _source_key(item),
        "path": _path(item),
        "lines": [item.get("line_start"), item.get("line_end")],
        "qualified": item.get("qualified"),
        "qualification_reason": item.get("qualification_reason") or item.get("reason"),
        "route": item.get("retrieval_route") or item.get("route"),
        "score": item.get("score") or item.get("rank") or item.get("rerank_score"),
        "needles": [needle for needle in QUESTION_NEEDLES if needle in text.casefold()],
        "text": " ".join(text.split())[:260],
    }


def _items(value: object) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("sources", "candidates", "items", "before", "after", "selected"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def _flatten_stage(trace: dict, stage: str) -> list[dict]:
    result: list[dict] = []
    for call in trace.get("stages", {}).get(stage, []):
        if not isinstance(call, dict):
            continue
        found = False
        for key in ("sources", "candidates", "items", "before", "after", "selected"):
            value = call.get(key)
            if isinstance(value, list):
                result.extend(item for item in value if isinstance(item, dict))
                found = True
        if not found:
            result.extend(_items(call))
    dedup: dict[tuple, dict] = {}
    for item in result:
        compact = _compact(item)
        key = (
            compact["key"],
            compact["path"],
            tuple(compact["lines"]),
            compact["text"],
        )
        dedup[key] = compact
    return list(dedup.values())


def _interesting(items: list[dict]) -> list[dict]:
    hits = [item for item in items if item.get("needles")]
    return hits[:20]


def main() -> int:
    shutil.rmtree(OUTPUT, ignore_errors=True)
    run(OUTPUT, projects=["pydantic"])
    rows = json.loads((OUTPUT / "rows.json").read_text(encoding="utf-8"))
    report: list[dict] = []
    for row in rows:
        if row.get("id") != "pydantic-02":
            continue
        variant = str(row["variant"])
        trace = json.loads(
            (OUTPUT / "traces" / variant / "pydantic-02.json").read_text(encoding="utf-8")
        )
        stages: dict[str, object] = {}
        for stage in (
            "retrieved_candidates",
            "query_window",
            "rankings",
            "qualified_fragments",
            "expansions",
        ):
            flattened = _flatten_stage(trace, stage)
            stages[stage] = {
                "total": len(flattened),
                "interesting": _interesting(flattened),
            }
        payload_sources = row.get("payload", {}).get("sources", [])
        report.append(
            {
                "variant": variant,
                "sufficiency": row.get("assessment", {}).get("context_sufficiency"),
                "first_loss": row.get("stage_assessment", {}).get("first_observed_loss"),
                "payload_sources": [_compact(item) for item in payload_sources],
                "stages": stages,
            }
        )
    print("RECOVERY_PROBE=" + json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
