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
