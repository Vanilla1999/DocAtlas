"""Score normalized DocAtlas and Context7 traces against one parity dataset.

Raw provider responses are intentionally not committed.  This module stores only
per-item verdicts and aggregate statistics, so a recapture can be audited without
changing the shared questions or their evidence contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Iterable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
REQUIRED_ITEM_FIELDS = {
    "id", "ecosystem", "library", "requested_version", "question_type", "question",
    "allowed_corpus", "expected_evidence", "requires_code_snippet", "expected_first_tool",
    "context7_library_id",
}
TRACE_REQUIRED_FIELDS = {"provider", "case_id", "first_tool", "results", "latency_ms", "phase"}


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number}: expected JSON object")
        records.append(value)
    return records


def dataset_digest(items: list[dict[str, Any]]) -> str:
    normalized = "\n".join(json.dumps(item, sort_keys=True, separators=(",", ":")) for item in items)
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def validate_dataset(items: list[dict[str, Any]]) -> None:
    if len(items) < 150:
        raise ValueError(f"Parity dataset must contain at least 150 items, got {len(items)}")
    ids = [str(item.get("id") or "") for item in items]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise ValueError("Parity dataset item ids must be non-empty and unique")
    for item in items:
        missing = REQUIRED_ITEM_FIELDS - set(item)
        if missing:
            raise ValueError(f"{item.get('id', '<unknown>')}: missing {sorted(missing)}")
        if not item["allowed_corpus"].get("sources"):
            raise ValueError(f"{item['id']}: allowed corpus must name at least one source")
        if not item["expected_evidence"].get("source") or not item["expected_evidence"].get("section"):
            raise ValueError(f"{item['id']}: expected source and section are required")


def _host(value: str) -> str:
    return urlparse(value).netloc.casefold()


def _result_text(result: dict[str, Any]) -> str:
    return "\n".join(str(result.get(key) or "") for key in ("source", "title", "section", "content", "snippet"))


def _source_allowed(result: dict[str, Any], item: dict[str, Any]) -> bool:
    source_host = _host(str(result.get("source") or ""))
    allowed_hosts = {_host(source) for source in item["allowed_corpus"]["sources"]}
    return bool(source_host) and any(source_host == host or source_host.endswith(f".{host}") for host in allowed_hosts)


def _result_relevant(result: dict[str, Any], item: dict[str, Any]) -> bool:
    expected = item["expected_evidence"]
    text = _result_text(result).casefold()
    source_ok = _host(str(expected["source"])) == _host(str(result.get("source") or ""))
    section_ok = str(expected["section"]).casefold() in text
    symbol_ok = any(str(symbol).casefold() in text for symbol in expected.get("symbols") or [])
    return (source_ok or section_ok) and symbol_ok


def _syntax_valid(snippet: str, ecosystem: str) -> bool:
    code = snippet.strip()
    if not code:
        return False
    if ecosystem == "python":
        try:
            compile(code, "<snippet>", "exec")
        except SyntaxError:
            return False
        return True
    # Basic, deterministic validation only; full TS/Dart compilation would make
    # the corpus-dependent evaluation non-reproducible.
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []
    for char in code:
        if char in pairs:
            stack.append(pairs[char])
        elif char in pairs.values() and (not stack or stack.pop() != char):
            return False
    return not stack and len(code) >= 8


def _wilson(successes: int, total: int, z: float = 1.96) -> list[float]:
    if total == 0:
        return [0.0, 0.0]
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total) / denominator
    return [round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4)]


def score_trace(item: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    missing = TRACE_REQUIRED_FIELDS - set(trace)
    if missing:
        raise ValueError(f"{trace.get('case_id', '<unknown>')}: trace missing {sorted(missing)}")
    provider = str(trace["provider"])
    results = [result for result in trace["results"] if isinstance(result, dict)]
    relevance = [_result_relevant(result, item) for result in results]
    first_rank = next((index for index, relevant in enumerate(relevance, start=1) if relevant), None)
    snippets = [str(result.get("snippet") or "") for result in results]
    valid_snippet = any(_syntax_valid(snippet, item["ecosystem"]) for snippet in snippets)
    contaminating = [str(result.get("source") or "") for result in results if not _source_allowed(result, item)]
    resolved_version = str(trace.get("resolved_version") or "")
    expected_tool = str(item["expected_first_tool"].get(provider) or "")
    version_status = (
        "unknown" if not resolved_version
        else "match" if resolved_version == item["requested_version"]
        else "mismatch"
    )
    return {
        "id": item["id"],
        "provider": provider,
        "phase": trace["phase"],
        "first_tool": trace["first_tool"],
        "first_tool_correct": bool(expected_tool) and trace["first_tool"] == expected_tool,
        "first_relevant_rank": first_rank,
        "hit_at_1": first_rank == 1,
        "hit_at_3": first_rank is not None and first_rank <= 3,
        "mrr": round(1 / first_rank, 4) if first_rank else 0.0,
        "version_status": version_status,
        "version_mismatch": version_status == "mismatch",
        "version_verified": version_status == "match",
        "snippet_required": item["requires_code_snippet"],
        "snippet_present": bool(snippets),
        "snippet_syntax_valid": valid_snippet,
        "latency_ms": float(trace["latency_ms"]),
        "network_fetch_count": int(trace.get("network_fetch_count") or 0),
        "lifecycle_call_count": int(trace.get("lifecycle_call_count") or 0),
        "unnecessary_lifecycle_call": bool(trace.get("unnecessary_lifecycle_call")),
        "source_contamination": contaminating,
        "status": str(trace.get("status") or "success"),
    }


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return round(sum(values) / len(values), 4) if values else 0.0


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    hits1 = sum(bool(item["hit_at_1"]) for item in items)
    hits3 = sum(bool(item["hit_at_3"]) for item in items)
    tool_ok = sum(bool(item["first_tool_correct"]) for item in items)
    version_bad = sum(bool(item["version_mismatch"]) for item in items)
    version_unknown = sum(item["version_status"] == "unknown" for item in items)
    contamination = sum(bool(item["source_contamination"]) for item in items)
    snippets_required = [item for item in items if item["snippet_required"]]
    snippets_ok = sum(bool(item["snippet_present"] and item["snippet_syntax_valid"]) for item in snippets_required)
    cold = [item["latency_ms"] for item in items if item["phase"] == "cold"]
    warm = [item["latency_ms"] for item in items if item["phase"] == "warm"]
    return {
        "items": total,
        "first_tool_accuracy": _mean([float(item["first_tool_correct"]) for item in items]),
        "hit_at_1": _mean([float(item["hit_at_1"]) for item in items]),
        "hit_at_3": _mean([float(item["hit_at_3"]) for item in items]),
        "mrr": _mean([float(item["mrr"]) for item in items]),
        "version_mismatch_rate": _mean([float(item["version_mismatch"]) for item in items]),
        "version_unknown_rate": _mean([float(item["version_status"] == "unknown") for item in items]),
        "exact_version_verified_rate": _mean([float(item["version_verified"]) for item in items]),
        "usable_snippet_rate": _mean([float(item["snippet_present"] and item["snippet_syntax_valid"]) for item in snippets_required]),
        "cold_latency_ms": _mean(cold),
        "warm_latency_ms": _mean(warm),
        "network_fetch_count": sum(item["network_fetch_count"] for item in items),
        "unnecessary_lifecycle_call_rate": _mean([float(item["unnecessary_lifecycle_call"]) for item in items]),
        "source_contamination_rate": _mean([float(bool(item["source_contamination"])) for item in items]),
        "confidence_intervals_95": {"hit_at_1": _wilson(hits1, total), "hit_at_3": _wilson(hits3, total), "first_tool_accuracy": _wilson(tool_ok, total), "version_mismatch_rate": _wilson(version_bad, total), "version_unknown_rate": _wilson(version_unknown, total), "source_contamination_rate": _wilson(contamination, total), "usable_snippet_rate": _wilson(snippets_ok, len(snippets_required))},
    }


def build_report(dataset_path: str | Path, trace_paths: list[str | Path]) -> dict[str, Any]:
    dataset = load_jsonl(dataset_path)
    validate_dataset(dataset)
    by_id = {item["id"]: item for item in dataset}
    per_provider: dict[str, list[dict[str, Any]]] = {}
    unsupported: list[dict[str, str]] = []
    for trace_path in trace_paths:
        for trace in load_jsonl(trace_path):
            case_id = str(trace.get("case_id") or "")
            if case_id not in by_id:
                unsupported.append({"case_id": case_id, "reason": "not_in_dataset"})
                continue
            result = score_trace(by_id[case_id], trace)
            per_provider.setdefault(result["provider"], []).append(result)
    summaries = {provider: summarize(results) for provider, results in sorted(per_provider.items())}
    expected_ids = set(by_id)
    full_coverage = all(
        len(results) == len(dataset) and {item["id"] for item in results} == expected_ids
        for results in per_provider.values() if results
    )
    same_corpus_rules = all(
        summary["source_contamination_rate"] == 0.0 for summary in summaries.values()
    )
    comparable = set(summaries) >= {"docatlas", "context7"} and full_coverage and same_corpus_rules
    comparison = {"comparable": comparable, "wins": [], "losses": [], "unsupported_cases": unsupported}
    if comparable:
        for metric in ("hit_at_1", "hit_at_3", "mrr", "first_tool_accuracy", "usable_snippet_rate"):
            delta = round(summaries["docatlas"][metric] - summaries["context7"][metric], 4)
            target = "wins" if delta > 0 else "losses" if delta < 0 else "unsupported_cases"
            comparison[target].append({"metric": metric, "docatlas_minus_context7": delta})
    else:
        comparison["unsupported_cases"].append({
            "reason": "No comparative claim: providers must cover the same full dataset using the allowed corpus."
        })
    return {
        "schema_version": "context7-parity-1",
        "dataset": {"path": str(dataset_path), "items": len(dataset), "digest": dataset_digest(dataset), "corpus_policy": "official-docs-only"},
        "providers": summaries,
        "per_item": per_provider,
        "comparison": comparison,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate normalized DocAtlas/Context7 parity traces.")
    parser.add_argument("--dataset", default=str(ROOT / "dataset.jsonl"))
    parser.add_argument("--traces", action="append", required=True, help="JSONL trace file; repeat per provider.")
    parser.add_argument("--output", required=True, help="Summary JSON path outside the raw trace directory.")
    args = parser.parse_args()
    report = build_report(args.dataset, args.traces)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
