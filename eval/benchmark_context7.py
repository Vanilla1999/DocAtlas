from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAIRS = [
    ("eval/results/docmancer_fastapi_results.json", "eval/results/context7_fastapi_results.json"),
    ("eval/results/docmancer_riverpod_results.json", "eval/results/context7_riverpod_results.json"),
    ("eval/results/docatlas_click_results.json", "eval/results/context7_click_results.json"),
    ("eval/results/docatlas_flutter_bloc_results.json", "eval/results/context7_flutter_bloc_results.json"),
    ("eval/results/docatlas_project_docs_results.json", "eval/results/context7_project_docs_results.json"),
]

TARGETS = {
    "correct_source_rate": 0.95,
    "contamination_rate": 0.0,
    "hit@1": 0.80,
    "hit@5": 0.90,
    "mrr": 0.85,
    "unique_sources@5": 3.0,
    "redundancy_rate": 0.40,
    "snippet_usefulness": 0.70,
    "avg_cold_latency_ms": 2000.0,
    "avg_warm_latency_ms": 500.0,
    "setup_calls_avg": 3.0,
    "exact_version_correctness": 1.0,
    "hallucinated_api_rate": 0.0,
}


BENCHMARK_QUERIES = [
    {"library": "fastapi", "query": "Depends dependency injection", "expected": ["Depends", "dependencies", "callable"]},
    {"library": "fastapi", "query": "HTTPException usage", "expected": ["HTTPException", "status_code", "headers"]},
    {"library": "fastapi", "query": "TestClient async tests", "expected": ["TestClient", "pytest", "async"]},
    {"library": "click", "query": "group options callback", "expected": ["@click.group", "@click.option", "callback"]},
    {"library": "click", "query": "context pass_context", "expected": ["Context", "pass_context", "ensure_object"]},
    {"library": "riverpod", "query": "autoDispose", "expected": ["ref.onDispose", "autoDispose"]},
    {"library": "riverpod", "query": "keepAlive", "expected": ["keepAlive", "ref.keepAlive"]},
    {"library": "riverpod", "query": "family modifier", "expected": ["family", "parameter"]},
    {"library": "riverpod", "query": "ref.watch ref.listen", "expected": ["ref.watch", "ref.listen", "AsyncValue"]},
    {"library": "riverpod", "query": "AsyncNotifier", "expected": ["AsyncNotifier", "build", "AsyncNotifierProvider"]},
    {"library": "flutter_bloc", "query": "BlocProvider", "expected": ["BlocProvider", "create", "child"]},
    {"library": "flutter_bloc", "query": "BlocBuilder", "expected": ["BlocBuilder", "builder", "buildWhen"]},
    {"library": "flutter_bloc", "query": "BlocListener", "expected": ["BlocListener", "listener", "listenWhen"]},
    {"library": "flutter_bloc", "query": "MultiBlocProvider", "expected": ["MultiBlocProvider", "providers"]},
    {"library": "docatlas", "query": "How does DocAtlas ingest docs?", "expected": ["ingest", "add_url", "index"]},
    {"library": "docatlas", "query": "How does DocAtlas handle Trust Contract?", "expected": ["trust_contract", "selected", "rejected"]},
    {"library": "docatlas", "query": "How does DocAtlas resolve library versions?", "expected": ["resolve_library", "version", "lockfile"]},
]


def _load_report(path: str | Path) -> dict[str, Any]:
    report_path = Path(path)
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    with report_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def contamination_check(chunks: list[dict[str, Any]], expected_library: str) -> bool:
    expected = expected_library.casefold()
    for chunk in chunks:
        source = str(chunk.get("source") or "").casefold()
        title = str(chunk.get("title") or "").casefold()
        if expected not in source and expected not in title:
            return False
    return True


def snippet_score(chunk_text: str, query_terms: set[str]) -> float:
    text = chunk_text.casefold()
    if not query_terms:
        return 0.0
    hits = sum(1 for term in query_terms if term.casefold() in text)
    code_bonus = 1 if "```" in chunk_text or "has_code_snippet" in chunk_text else 0
    return round((hits + code_bonus) / (len(query_terms) + 1), 4)


def _report_items(report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(report.get("items") or [])


def _system_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    items = [item for report in reports for item in _report_items(report)]
    total = len(items)
    if total == 0:
        return {
            "queries": 0,
            "contamination_rate": 0.0,
            "correct_source_rate": 0.0,
            "hit@1": 0.0,
            "hit@5": 0.0,
            "mrr": 0.0,
            "snippet_usefulness": 0.0,
            "unique_sources@5": 0.0,
            "redundancy_rate": 0.0,
            "avg_cold_latency_ms": 0.0,
            "avg_warm_latency_ms": 0.0,
            "avg_latency_ms": 0.0,
            "setup_calls_avg": 0.0,
            "exact_version_correctness": 0.0,
            "hallucinated_api_rate": 0.0,
        }

    contamination_hits = sum(1 for item in items if item.get("forbidden_source_hits"))
    hit1 = sum(1 for item in items if item.get("first_hit_rank") == 1) / total
    hit5 = sum(1 for item in items if item.get("hit_at_5")) / total
    reciprocal_ranks = [1 / item["first_hit_rank"] for item in items if item.get("first_hit_rank")]
    snippet_hits = sum(
        1
        for item in items
        if (item.get("snippet_presence") or {}).get("snippet_present_at_5") or item.get("snippet_present_at_5")
    ) / total
    unique_sources = [(item.get("source_diversity") or {}).get("unique_sources_at_5", 0) for item in items]
    redundancy = [(item.get("source_diversity") or {}).get("redundancy_rate_at_5", 0.0) for item in items]
    report_quality = [report.get("metrics", {}).get("quality", {}) for report in reports]
    if not any(unique_sources):
        unique_sources = [quality.get("unique_sources_at_5_avg", 0) for quality in report_quality if quality]
    if not any(redundancy):
        redundancy = [quality.get("redundancy_rate_at_5_avg", 0.0) for quality in report_quality if quality]
    item_latencies = [float(item.get("latency_ms") or 0.0) for item in items if item.get("latency_ms") is not None]
    cold_latencies = []
    warm_latencies = []
    for report in reports:
        latencies = [float(item.get("latency_ms") or 0.0) for item in _report_items(report) if item.get("latency_ms") is not None]
        if not latencies:
            avg_latency = report.get("metrics", {}).get("avg_latency_ms")
            if avg_latency is not None:
                item_latencies.append(float(avg_latency))
            continue
        cold = max(latencies)
        cold_latencies.append(cold)
        warm_latencies.extend(latency for latency in latencies if latency != cold)
    setup_calls = [float(item.get("setup_calls", 1 if item.get("first_hit_rank") else 3)) for item in items]
    exact_versions = [bool(item.get("exact_version_match", not item.get("forbidden_version_hits"))) for item in items]
    hallucinated = [bool(item.get("hallucinated_api_hits")) for item in items]

    return {
        "queries": total,
        "contamination_rate": round(contamination_hits / total, 4),
        "correct_source_rate": round(1 - contamination_hits / total, 4),
        "hit@1": round(hit1, 4),
        "hit@5": round(hit5, 4),
        "mrr": round(sum(reciprocal_ranks) / total, 4),
        "snippet_usefulness": round(snippet_hits, 4),
        "unique_sources@5": round(sum(unique_sources) / len(unique_sources), 4) if unique_sources else 0.0,
        "redundancy_rate": round(sum(redundancy) / len(redundancy), 4) if redundancy else 0.0,
        "avg_cold_latency_ms": round(sum(cold_latencies) / len(cold_latencies), 3) if cold_latencies else 0.0,
        "avg_warm_latency_ms": round(sum(warm_latencies) / len(warm_latencies), 3) if warm_latencies else 0.0,
        "avg_latency_ms": round(sum(item_latencies) / len(item_latencies), 3) if item_latencies else 0.0,
        "setup_calls_avg": round(sum(setup_calls) / len(setup_calls), 4) if setup_calls else 0.0,
        "exact_version_correctness": round(sum(1 for item in exact_versions if item) / len(exact_versions), 4) if exact_versions else 0.0,
        "hallucinated_api_rate": round(sum(1 for item in hallucinated if item) / len(hallucinated), 4) if hallucinated else 0.0,
    }


def _acceptance(report: dict[str, Any]) -> dict[str, Any]:
    docatlas = report["docatlas"]
    checks = {
        "all_queries_return_results": report["total_queries"] == report["benchmark_catalog_queries"],
        "docatlas_contamination_zero": docatlas["contamination_rate"] == TARGETS["contamination_rate"],
        "docatlas_correct_source_rate": docatlas["correct_source_rate"] >= TARGETS["correct_source_rate"],
        "docatlas_hit@1": docatlas["hit@1"] > TARGETS["hit@1"],
        "docatlas_hit@5": docatlas["hit@5"] > TARGETS["hit@5"],
        "docatlas_mrr": docatlas["mrr"] > TARGETS["mrr"],
        "docatlas_unique_sources@5": docatlas["unique_sources@5"] > TARGETS["unique_sources@5"],
        "docatlas_redundancy_rate": docatlas["redundancy_rate"] < TARGETS["redundancy_rate"],
        "docatlas_snippet_usefulness": docatlas["snippet_usefulness"] > TARGETS["snippet_usefulness"],
        "docatlas_cold_latency": docatlas["avg_cold_latency_ms"] < TARGETS["avg_cold_latency_ms"],
        "docatlas_warm_latency": docatlas["avg_warm_latency_ms"] < TARGETS["avg_warm_latency_ms"],
        "docatlas_setup_calls": docatlas["setup_calls_avg"] < TARGETS["setup_calls_avg"],
        "docatlas_exact_version": docatlas["exact_version_correctness"] == TARGETS["exact_version_correctness"],
        "docatlas_hallucinated_api": docatlas["hallucinated_api_rate"] == TARGETS["hallucinated_api_rate"],
    }
    return {"passed": all(checks.values()), "checks": checks, "targets": TARGETS}


class BenchmarkRunner:
    def __init__(self, pairs: list[tuple[str, str]] | None = None):
        self.pairs = pairs or DEFAULT_PAIRS

    def run_query(self, context: str) -> dict[str, Any]:
        query = next((item for item in BENCHMARK_QUERIES if item["query"] == context), None)
        return {"query": context, "expected": query["expected"] if query else [], "status": "catalog_only"}

    def run(self) -> dict[str, Any]:
        started = time.perf_counter()
        docatlas_reports = []
        context7_reports = []
        for docatlas_path, context7_path in self.pairs:
            docatlas = _load_report(docatlas_path)
            context7 = _load_report(context7_path)
            if docatlas.get("dataset") != context7.get("dataset"):
                raise ValueError(f"Dataset mismatch: {docatlas_path} vs {context7_path}")
            docatlas_reports.append(docatlas)
            context7_reports.append(context7)

        report = {
            "schema_version": 1,
            "benchmark_catalog_queries": len(BENCHMARK_QUERIES),
            "total_queries": sum(len(_report_items(report)) for report in docatlas_reports),
            "docatlas": _system_summary(docatlas_reports),
            "context7": _system_summary(context7_reports),
            "summary": {
                "docatlas_advantages": ["project-aware", "exact-version", "offline", "attribution"],
                "context7_advantages": ["zero-setup", "lower latency", "clean snippets"],
                "readiness": "benchmark snapshots comparable; expand fixtures to all catalog queries for final gate",
            },
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        report["acceptance"] = _acceptance(report)
        if report["acceptance"]["passed"]:
            report["summary"]["readiness"] = "all roadmap 08 acceptance criteria passed on normalized benchmark snapshots"
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare DocAtlas benchmark snapshots against Context7 snapshots.")
    parser.add_argument("--output", help="Optional JSON output path.")
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit non-zero if roadmap 08 acceptance checks fail.")
    args = parser.parse_args()

    report = BenchmarkRunner().run()
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    if args.fail_on_regression and not report["acceptance"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
