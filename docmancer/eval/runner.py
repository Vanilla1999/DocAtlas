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
    for rank, chunk in enumerate(chunks, start=1):
        text = _chunk_text(chunk)
        matched = [version for version in item.forbidden_versions if _contains_casefold(text, version)]
        if matched:
            hits.append({"rank": rank, "source": chunk.source, "versions": matched})
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


def source_diversity_metrics(chunks: list[Any], *, k: int = 5) -> dict[str, Any]:
    top = chunks[:k]
    sources = [chunk.source for chunk in top]
    unique = len(set(sources))
    redundancy = 0.0 if not top else round(1.0 - (unique / len(top)), 4)
    return {f"unique_sources_at_{k}": unique, f"redundancy_rate_at_{k}": redundancy}


_LOCALE_PATH_MARKERS = (
    "/ar/", "/bn/", "/de/", "/es/", "/fr/", "/it/", "/ja/", "/ko/", "/ru/", "/tr/", "/zh-Hans/",
)


def locale_contamination(chunks: list[Any]) -> dict[str, Any]:
    hits = [chunk.source for chunk in chunks if any(marker in (chunk.source or "") for marker in _LOCALE_PATH_MARKERS)]
    return {"locale_contamination_count": len(hits), "locale_contamination_sources": hits}


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
                "forbidden_checks_passed": not forbidden_sources and not forbidden_versions,
                "token_metrics": token_metrics(chunks),
                "source_diversity": source_diversity_metrics(chunks, k=min(5, limit)),
                "locale_contamination": locale_contamination(chunks),
                "results": [
                    {
                        "rank": rank,
                        "source": chunk.source,
                        "title": (chunk.metadata or {}).get("title"),
                        "section_id": (chunk.metadata or {}).get("section_id"),
                        "relevant": relevance[rank - 1],
                    }
                    for rank, chunk in enumerate(chunks, start=1)
                ],
            }
        )

    return {
        "schema_version": 1,
        "dataset": dataset_path,
        "corpus_snapshot": dataset.corpus_snapshot,
        "mode": mode,
        "metrics": accumulator.summary(),
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
