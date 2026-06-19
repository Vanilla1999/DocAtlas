"""Offline retrieval evaluator for golden datasets."""
from __future__ import annotations

import time
from typing import Any

from docmancer.eval.metrics import MetricAccumulator
from docmancer.eval.schema import ExpectedSource, GoldenQuery, load_golden_dataset


def _matches_expected(chunk: Any, expected: ExpectedSource) -> bool:
    meta = chunk.metadata or {}
    if expected.section_id is not None and meta.get("section_id") != expected.section_id:
        return False
    if expected.source and expected.source.lower() not in (chunk.source or "").lower():
        return False
    if expected.title and expected.title.lower() not in str(meta.get("title") or "").lower():
        return False
    return True


def relevance_for_chunks(chunks: list[Any], item: GoldenQuery) -> list[bool]:
    if not item.expected_sources:
        return [False for _ in chunks]
    return [any(_matches_expected(chunk, expected) for expected in item.expected_sources) for chunk in chunks]


def _chunk_text(chunk: Any) -> str:
    meta = chunk.metadata or {}
    return "\n".join(
        part
        for part in [chunk.source or "", str(meta.get("title") or ""), getattr(chunk, "text", "") or ""]
        if part
    )


def _contains_casefold(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def required_fact_results(chunks: list[Any], item: GoldenQuery) -> dict[str, bool]:
    corpus = "\n".join(_chunk_text(chunk) for chunk in chunks)
    return {fact: _contains_casefold(corpus, fact) for fact in item.required_facts}


def forbidden_source_hits(chunks: list[Any], item: GoldenQuery) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for rank, chunk in enumerate(chunks, start=1):
        for forbidden in item.forbidden_sources:
            if _matches_expected(chunk, forbidden):
                hits.append({"rank": rank, "source": chunk.source, "title": (chunk.metadata or {}).get("title")})
                break
    return hits


def forbidden_version_hits(chunks: list[Any], item: GoldenQuery) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    expected_version = None
    if item.project_context:
        raw_version = item.project_context.get("version")
        expected_version = str(raw_version) if raw_version else None
    for rank, chunk in enumerate(chunks, start=1):
        meta = chunk.metadata or {}
        source_version = meta.get("version") or meta.get("resolved_version")
        if expected_version and source_version and str(source_version) != expected_version:
            hits.append({"rank": rank, "source": chunk.source, "versions": [str(source_version)], "expected_version": expected_version})
            continue
        text = _chunk_text(chunk)
        matched = [version for version in item.forbidden_versions if _contains_casefold(text, version)]
        if matched:
            hits.append({"rank": rank, "source": chunk.source, "versions": matched})
    return hits


def unknown_version_hits(chunks: list[Any], item: GoldenQuery) -> list[dict[str, Any]]:
    if item.version_policy != "exact" or not item.project_context or not item.project_context.get("version"):
        return []
    hits: list[dict[str, Any]] = []
    for rank, chunk in enumerate(chunks, start=1):
        meta = chunk.metadata or {}
        if not (meta.get("version") or meta.get("resolved_version")):
            hits.append({"rank": rank, "source": chunk.source, "expected_version": str(item.project_context["version"])})
    return hits


def _token_estimate(chunk: Any) -> int:
    meta = chunk.metadata or {}
    value = meta.get("token_estimate")
    if isinstance(value, int) and value >= 0:
        return value
    text = getattr(chunk, "text", "") or ""
    return max(1, len(text) // 4) if text else 0


def token_metrics(chunks: list[Any]) -> dict[str, Any]:
    docmancer_tokens = sum(_token_estimate(chunk) for chunk in chunks)
    raw_tokens = docmancer_tokens
    savings_percent = 0.0 if raw_tokens else 0.0
    runway_multiplier = 1.0 if docmancer_tokens else None
    return {
        "docmancer_tokens": docmancer_tokens,
        "raw_tokens": raw_tokens,
        "savings_percent": savings_percent,
        "runway_multiplier": runway_multiplier,
    }


def _source_key(chunk: Any) -> str:
    meta = chunk.metadata or {}
    return str(meta.get("canonical_url") or chunk.source or "")


def source_diversity_metrics(chunks: list[Any], *, k: int = 5) -> dict[str, Any]:
    top = chunks[:k]
    sources = [_source_key(chunk) for chunk in top]
    unique = len(set(sources))
    redundancy = 0.0 if not top else round(1.0 - (unique / len(top)), 4)
    return {f"unique_sources_at_{k}": unique, f"redundancy_rate_at_{k}": redundancy}


_LOCALE_PATH_MARKERS = (
    "/ar/", "/bn/", "/de/", "/es/", "/fr/", "/it/", "/ja/", "/ko/", "/ru/", "/tr/", "/zh-Hans/",
)


def locale_contamination(chunks: list[Any]) -> dict[str, Any]:
    hits = [_source_key(chunk) for chunk in chunks if any(marker in _source_key(chunk) for marker in _LOCALE_PATH_MARKERS)]
    return {"locale_contamination_count": len(hits), "locale_contamination_sources": hits}


def snippet_presence_metrics(chunks: list[Any], *, k: int = 5) -> dict[str, Any]:
    top = chunks[:k]
    count = 0
    for chunk in top:
        meta = chunk.metadata or {}
        snippets = meta.get("code_snippets") or []
        if meta.get("has_code_snippet") or snippets:
            count += 1
    return {f"snippet_sections_at_{k}": count, f"snippet_present_at_{k}": count > 0}


def snippet_relevance_metrics(chunks: list[Any], item: GoldenQuery) -> dict[str, Any]:
    relevance = relevance_for_chunks(chunks, item)
    return {
        "snippet_relevance_at_1": bool(chunks[:1]) and snippet_presence_metrics(chunks, k=1)["snippet_present_at_1"] and any(relevance[:1]),
        "snippet_relevance_at_3": bool(chunks[:3]) and snippet_presence_metrics(chunks, k=min(3, len(chunks) or 1)).get(f"snippet_present_at_{min(3, len(chunks) or 1)}", False) and any(relevance[:3]),
        "has_directly_usable_snippet": snippet_presence_metrics(chunks, k=min(5, len(chunks) or 1)).get(f"snippet_present_at_{min(5, len(chunks) or 1)}", False),
        "snippet_api_symbol_match": any(
            fact.casefold() in _chunk_text(chunk).casefold()
            for fact in item.required_facts
            for chunk in chunks
            if (chunk.metadata or {}).get("has_code_snippet") or (chunk.metadata or {}).get("code_snippets")
        ) if item.required_facts else False,
    }


def explain_contract_metrics(chunks: list[Any], item: GoldenQuery) -> dict[str, Any]:
    has_project_context = bool(item.project_context)
    has_selected = bool(chunks)
    has_rejected_or_risky = bool(forbidden_version_hits(chunks, item) or unknown_version_hits(chunks, item))
    return {
        "explain_has_selected_sources": has_selected,
        "explain_has_rejected_or_risky_sources": has_rejected_or_risky if has_project_context else False,
    }


def aggregate_quality_metrics(items: list[dict[str, Any]], *, k: int = 5) -> dict[str, Any]:
    if not items:
        return {
            f"unique_sources_at_{k}_avg": 0.0,
            f"redundancy_rate_at_{k}_avg": 0.0,
            f"snippet_present_at_{k}_rate": 0.0,
            f"snippet_sections_at_{k}_avg": 0.0,
            "locale_contamination_count": 0,
            "locale_contamination_rate": 0.0,
        }
    unique_key = f"unique_sources_at_{k}"
    redundancy_key = f"redundancy_rate_at_{k}"
    snippet_present_key = f"snippet_present_at_{k}"
    snippet_sections_key = f"snippet_sections_at_{k}"
    locale_counts = [item["locale_contamination"]["locale_contamination_count"] for item in items]
    contaminated = sum(1 for count in locale_counts if count > 0)
    return {
        f"unique_sources_at_{k}_avg": round(
            sum(item["source_diversity"].get(unique_key, 0) for item in items) / len(items), 4
        ),
        f"redundancy_rate_at_{k}_avg": round(
            sum(item["source_diversity"].get(redundancy_key, 0.0) for item in items) / len(items), 4
        ),
        f"snippet_present_at_{k}_rate": round(
            sum(1 for item in items if item["snippet_presence"].get(snippet_present_key)) / len(items), 4
        ),
        f"snippet_sections_at_{k}_avg": round(
            sum(item["snippet_presence"].get(snippet_sections_key, 0) for item in items) / len(items), 4
        ),
        "locale_contamination_count": sum(locale_counts),
        "locale_contamination_rate": round(contaminated / len(items), 4),
    }


def run_retrieval_eval(
    *,
    dataset_path: str,
    agent,
    config,
    mode: str = "lexical",
    limit: int = 10,
    budget: int = 10_000,
    allow_degraded: bool = True,
) -> dict[str, Any]:
    dataset = load_golden_dataset(dataset_path)
    accumulator = MetricAccumulator()
    items: list[dict[str, Any]] = []
    mode = mode.lower()

    for item in dataset.items:
        start = time.perf_counter()
        failures: dict[str, str] = {}
        if mode == "lexical":
            chunks = agent.query(item.query, limit=limit, budget=budget)
            mode_used = "lexical"
        else:
            from docmancer.cli.commands import _run_dispatch_query

            chunks, _contributions, failures, mode_used, _candidate_counts = _run_dispatch_query(
                agent=agent,
                config=config,
                query=item.query,
                mode=mode,
                limit=limit,
                budget=budget,
                expand=None,
                allow_degraded=allow_degraded,
            )
        latency_ms = (time.perf_counter() - start) * 1000
        relevance = relevance_for_chunks(chunks, item)
        facts = required_fact_results(chunks, item)
        forbidden_sources = forbidden_source_hits(chunks, item)
        forbidden_versions = forbidden_version_hits(chunks, item)
        unknown_versions = unknown_version_hits(chunks, item)
        accumulator.add(relevance, latency_ms)
        first_hit_rank = next((idx for idx, value in enumerate(relevance, start=1) if value), None)
        items.append(
            {
                "id": item.id,
                "query": item.query,
                "taxonomy_class": item.taxonomy_class,
                "mode_used": mode_used,
                "first_hit_rank": first_hit_rank,
                "hit_at_5": first_hit_rank is not None and first_hit_rank <= 5,
                "latency_ms": round(latency_ms, 3),
                "failures": failures,
                "required_facts": facts,
                "required_facts_passed": all(facts.values()) if facts else True,
                "forbidden_source_hits": forbidden_sources,
                "forbidden_version_hits": forbidden_versions,
                "unknown_version_hits": unknown_versions,
                "forbidden_checks_passed": not forbidden_sources and not forbidden_versions,
                "token_metrics": token_metrics(chunks),
                "source_diversity": source_diversity_metrics(chunks, k=min(5, limit)),
                "locale_contamination": locale_contamination(chunks),
                "snippet_presence": snippet_presence_metrics(chunks, k=min(5, limit)),
                "snippet_relevance": snippet_relevance_metrics(chunks, item),
                "explain_context": explain_contract_metrics(chunks, item),
                "results": [
                    {
                        "rank": rank,
                        "source": chunk.source,
                        "title": (chunk.metadata or {}).get("title"),
                        "section_id": (chunk.metadata or {}).get("section_id"),
                        "has_code_snippet": bool((chunk.metadata or {}).get("has_code_snippet") or (chunk.metadata or {}).get("code_snippets")),
                        "relevant": relevance[rank - 1],
                    }
                    for rank, chunk in enumerate(chunks, start=1)
                ],
            }
        )

    summary = accumulator.summary()
    summary["quality"] = aggregate_quality_metrics(items, k=min(5, limit))
    return {
        "schema_version": 1,
        "dataset": dataset_path,
        "corpus_snapshot": dataset.corpus_snapshot,
        "mode": mode,
        "metrics": summary,
        "items": items,
    }


def format_eval_report(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    hit_at = metrics["hit_at"]
    lines = [
        f"Retrieval eval: {report['dataset']}",
        f"mode: {report['mode']}  queries: {metrics['queries']}",
        f"Hit@1={hit_at.get('1', 0):.2f}  Hit@3={hit_at.get('3', 0):.2f}  Hit@5={hit_at.get('5', 0):.2f}  MRR={metrics['mrr']:.2f}",
        f"Latency p50={metrics['latency_ms']['p50']:.1f}ms  p95={metrics['latency_ms']['p95']:.1f}ms",
        "---",
    ]
    for item in report["items"]:
        hit = "hit" if item["first_hit_rank"] else "miss"
        rank = item["first_hit_rank"] or "-"
        lines.append(f"{item['id']}: {hit} rank={rank} class={item['taxonomy_class']}")
    return "\n".join(lines)


def run_task_context_benchmark(*, scenarios: list[dict[str, Any]], runners: dict[str, Any]) -> dict[str, Any]:
    """Run a reviewable task-level benchmark across controlled docs-tool lanes.

    Runner callables receive one scenario dict and return observed task metrics.
    This keeps live model/tool execution outside the evaluator while standardizing
    the artifact shape for Context7-only, Docmancer-cold, and Docmancer-warm runs.
    """
    items: list[dict[str, Any]] = []
    for scenario in scenarios:
        scenario_id = str(scenario.get("id") or scenario.get("name") or "scenario")
        lane_results: dict[str, Any] = {}
        for lane, runner in runners.items():
            start = time.perf_counter()
            observation = dict(runner(scenario) or {})
            wall_clock_ms = round((time.perf_counter() - start) * 1000, 3)
            lane_results[lane] = {
                "task_completion": bool(observation.get("task_completion", False)),
                "tests_passed": bool(observation.get("tests_passed", False)),
                "wrong_version_api_usage": bool(observation.get("wrong_version_api_usage", False)),
                "project_rule_violation": bool(observation.get("project_rule_violation", False)),
                "docs_tool_calls": int(observation.get("docs_tool_calls", 0) or 0),
                "total_docs_tokens": int(observation.get("total_docs_tokens", 0) or 0),
                "wall_clock_ms": wall_clock_ms,
                "correction_loops": int(observation.get("correction_loops", 0) or 0),
                "artifact": observation.get("artifact"),
            }
        items.append({"id": scenario_id, "description": scenario.get("description"), "lanes": lane_results})

    lanes = sorted(runners)
    summary: dict[str, Any] = {}
    for lane in lanes:
        lane_items = [item["lanes"][lane] for item in items]
        count = len(lane_items) or 1
        summary[lane] = {
            "task_completion_rate": round(sum(1 for item in lane_items if item["task_completion"]) / count, 4),
            "tests_passed_rate": round(sum(1 for item in lane_items if item["tests_passed"]) / count, 4),
            "wrong_version_api_usage_rate": round(sum(1 for item in lane_items if item["wrong_version_api_usage"]) / count, 4),
            "project_rule_violation_rate": round(sum(1 for item in lane_items if item["project_rule_violation"]) / count, 4),
            "docs_tool_calls_avg": round(sum(item["docs_tool_calls"] for item in lane_items) / count, 4),
            "total_docs_tokens_avg": round(sum(item["total_docs_tokens"] for item in lane_items) / count, 4),
            "wall_clock_ms_avg": round(sum(item["wall_clock_ms"] for item in lane_items) / count, 4),
            "correction_loops_avg": round(sum(item["correction_loops"] for item in lane_items) / count, 4),
        }
    return {"schema_version": 1, "benchmark_type": "task_context", "lanes": lanes, "metrics": summary, "items": items}
