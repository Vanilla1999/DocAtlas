from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any


def bootstrap_delta_ci(a: list[bool], b: list[bool]) -> tuple[float, float, float] | None:
    if len(a) != len(b) or not a:
        return None
    deltas = [float(x) - float(y) for x, y in zip(a, b)]
    observed = sum(deltas) / len(deltas)
    # Deterministic small-sample paired bootstrap over cyclic resamples.
    samples: list[float] = []
    n = len(deltas)
    for offset in range(max(200, n * 25)):
        sample = [deltas[(offset + i * 7919) % n] for i in range(n)]
        samples.append(sum(sample) / n)
    samples.sort()
    return observed, samples[int(0.025 * (len(samples) - 1))], samples[int(0.975 * (len(samples) - 1))]


def write_report(run_dir: Path, metadata: dict[str, Any], results: list[dict[str, Any]]) -> Path:
    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_condition[result["condition_id"]].append(result)

    lines = [
        "# Task-Level Agent Benchmark Report",
        "",
        "## Executive result",
        metadata.get("executive_result", "Independent causal benchmark not completed."),
        "",
        "## Environment",
        "```json",
        json.dumps(metadata.get("environment", {}), indent=2, sort_keys=True),
        "```",
        "",
        "## Task table",
        "| task | condition | repeat | status | resolved | tests | tokens | time_s |",
        "|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for result in results:
        metrics = result.get("metrics", {})
        lines.append(
            f"| {result['task_id']} | {result['condition_id']} | {result['repeat']} | "
            f"{result['status']} | {result.get('resolved', False)} | {result.get('tests_passed', False)} | "
            f"{metrics.get('total_tokens', '')} | {metrics.get('wall_time_seconds', '')} |"
        )

    lines.extend(["", "## Condition results"])
    for condition, condition_results in sorted(by_condition.items()):
        resolved = [bool(r.get("resolved")) for r in condition_results]
        times = [r.get("metrics", {}).get("wall_time_seconds") for r in condition_results]
        times = [t for t in times if isinstance(t, (int, float))]
        rate = sum(resolved) / len(resolved) if resolved else 0.0
        lines.append(f"- `{condition}`: resolved={sum(resolved)}/{len(resolved)} ({rate:.1%}), median_time={median(times) if times else 'n/a'}")

    lines.extend([
        "",
        "## Paired comparison",
        "Pilot report computes paired deltas when each compared condition has matched task/repeat results. Wide intervals must be treated as directional evidence only.",
        "",
        "## Context utilization",
        "Retrieved/viewed/used/patch-relevant context is recorded per trajectory when an independent runner provides trajectory events.",
        "",
        "## Failures",
        metadata.get("failure_summary", "No independent agent failures were measured in this run."),
        "",
        "## Cold/warm economics",
        metadata.get("cold_warm_economics", "DocAtlas preindex and warm query timing hooks are present; no full preindexed benchmark was executed."),
        "",
        "## Claims we can make",
        metadata.get("claims_can_make", "The harness and curated pilot manifest are reproducible; current output is not a causal task-level result unless independent runner mode is used."),
        "",
        "## Claims we cannot make",
        metadata.get("claims_cannot_make", "Cannot claim DocAtlas improves patch success from harness smoke tests or retrieval scores alone."),
        "",
        "## Next experiment",
        metadata.get("next_experiment", "Run 8 tasks x 4 conditions x 2 repeats with a verified headless runner and isolated storage."),
        "",
        "## Final decision",
        metadata.get("decision", "ITERATE: benchmark harness is ready, independent comparison still needs a verified runner execution."),
        "",
    ])
    path = run_dir / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
