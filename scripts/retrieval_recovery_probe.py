from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from docmancer.retrieval.dispatch import RetrievalDispatcher
from eval.evidence_quality_v2.run import run


ROOT = Path("/tmp/docatlas-cap-lane-probe")
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


def _candidate_record(value: dict[str, Any]) -> dict[str, Any] | None:
    metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
    path = (
        value.get("path_or_url") or value.get("source_path") or value.get("source")
        or metadata.get("canonical_url") or metadata.get("source_path")
    )
    stable = value.get("stable_chunk_id") or value.get("evidence_id") or metadata.get("stable_chunk_id")
    lines = (
        value.get("line_start"), value.get("line_end"),
        metadata.get("line_start"), metadata.get("line_end"),
    )
    if not path and not stable and not any(item is not None for item in lines):
        return None
    lexical = value.get("lexical_match") or metadata.get("lexical_match")
    ranking = value.get("ranking") or metadata.get("ranking")
    return {
        "path": path,
        "stable_chunk_id": stable,
        "parent_logical_id": value.get("parent_logical_id") or metadata.get("parent_logical_id"),
        "chunk_index": value.get("chunk_index") if value.get("chunk_index") is not None else metadata.get("chunk_index"),
        "line_start": value.get("line_start") if value.get("line_start") is not None else metadata.get("line_start"),
        "line_end": value.get("line_end") if value.get("line_end") is not None else metadata.get("line_end"),
        "score": value.get("score"),
        "rank": value.get("rank"),
        "title": value.get("title") or metadata.get("title") or metadata.get("section_title"),
        "anchor": value.get("anchor") or metadata.get("anchor"),
        "ranking": ranking,
        "lexical_match": lexical,
        "snippet": str(value.get("snippet") or value.get("text") or value.get("display_text") or "")[:260],
    }


def _records(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            record = _candidate_record(node)
            if record is not None:
                key = json.dumps(record, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    found.append(record)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return found


def main() -> int:
    shutil.rmtree(ROOT, ignore_errors=True)
    original = RetrievalDispatcher._limit_sections_per_source
    try:
        RetrievalDispatcher._limit_sections_per_source = _hard_per_source_cap
        run(HARD, projects=["pydantic"])
    finally:
        RetrievalDispatcher._limit_sections_per_source = original

    rows = json.loads((HARD / "rows.json").read_text(encoding="utf-8"))
    report: dict[str, Any] = {}
    for case_id in ("pydantic-01", "pydantic-02"):
        row = next(
            item for item in rows
            if item.get("id") == case_id and item.get("variant") == "A-current"
        )
        trace = json.loads(
            (HARD / "traces" / "A-current" / f"{case_id}.json").read_text(encoding="utf-8")
        )
        report[case_id] = {
            "question": row.get("question"),
            "sufficiency": row.get("assessment", {}).get("context_sufficiency"),
            "payload_sources": row.get("payload", {}).get("sources", []),
            "stages": {
                stage: _records(trace.get("stages", {}).get(stage, []))
                for stage in ("retrieved_candidates", "query_window", "rankings", "qualified_fragments", "expansions")
            },
        }

    print("CAP_LANE_PROBE_BEGIN")
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True, default=str))
    print("CAP_LANE_PROBE_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
