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
        "| task | condition | repeat | status | resolved | public | hidden | harness_docatlas | agent_docatlas | context_injected | context_used | policy_clean |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        docatlas = result.get("docatlas", {}) if isinstance(result.get("docatlas"), dict) else {}
        lines.append(
            f"| {result['task_id']} | {result['condition_id']} | {result['repeat']} | "
            f"{result['status']} | {result.get('resolved', False)} | {result.get('public_tests_passed', result.get('tests_passed', False))} | "
            f"{result.get('hidden_tests_passed', False)} | {docatlas.get('harness_calls', 0)} | {docatlas.get('agent_calls', 0)} | "
            f"{docatlas.get('context_injected', False)} | {docatlas.get('context_used', False)} | {result.get('policy_clean', False)} |"
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
        "DocAtlas adoption and utilization are recorded separately for harness-side context injection and agent-side MCP tool calls.",
    ])
    for condition, condition_results in sorted(by_condition.items()):
        agent_calls = [int(r.get("docatlas", {}).get("agent_calls", 0)) for r in condition_results if isinstance(r.get("docatlas"), dict)]
        used = [bool(r.get("docatlas", {}).get("context_used")) for r in condition_results if isinstance(r.get("docatlas"), dict)]
        if agent_calls:
            lines.append(
                f"- `{condition}`: agent_docatlas_calls={sum(agent_calls)}, context_used={sum(used)}/{len(used)}"
            )

    lines.extend([
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
