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
        "| task | condition | repeat | status | resolved | public | hidden | behavior | form | project | version | network_attempts | harness_docatlas | agent_docatlas | tokens | wall_time | context_injected | context_used | checklist_items | checklist_used | retrieval_status | fallback | policy_clean | constraint_violations | unknowns | constraint_used | constraint_tokens |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        docatlas = result.get("docatlas", {}) if isinstance(result.get("docatlas"), dict) else {}
        contract = result.get("contract", {}) if isinstance(result.get("contract"), dict) else {}
        actionability = result.get("actionability", {}) if isinstance(result.get("actionability"), dict) else {}
        metrics = result.get("metrics", {}) if isinstance(result.get("metrics"), dict) else {}
        validation = result.get("constraint_validation", {}) if isinstance(result.get("constraint_validation"), dict) else {}
        patch_constraints = result.get("patch_constraints", {}) if isinstance(result.get("patch_constraints"), dict) else {}
        lines.append(
            f"| {result['task_id']} | {result['condition_id']} | {result['repeat']} | "
            f"{result['status']} | {result.get('resolved', False)} | {result.get('public_tests_passed', result.get('tests_passed', False))} | "
            f"{result.get('hidden_tests_passed', False)} | {contract.get('behavioral_contract_score', 'n/a')} | "
            f"{contract.get('form_contract_score', 'n/a')} | {contract.get('project_convention_score', 'n/a')} | "
            f"{contract.get('version_contract_score', 'n/a')} | {result.get('policy', {}).get('network_attempts', 0)} | "
            f"{docatlas.get('harness_calls', 0)} | {docatlas.get('agent_calls', 0)} | "
            f"{metrics.get('input_tokens', '')}/{metrics.get('output_tokens', '')} | {metrics.get('wall_time_seconds', '')} | "
            f"{docatlas.get('context_injected', False)} | {docatlas.get('context_used', False)} | "
            f"{len(actionability.get('checklist_items', []))} | {actionability.get('action_checklist_used', False)} | "
            f"{docatlas.get('docatlas_retrieval_status', '')} | {docatlas.get('fallback_used', False)} | "
            f"{result.get('policy_clean', False)} | {result.get('constraint_violations_after_patch', validation.get('violated', ''))} | "
            f"{validation.get('unknown', result.get('unknown_count', ''))} | {result.get('constraint_used', patch_constraints.get('constraint_used', False))} | "
            f"{result.get('constraint_packet_tokens', metrics.get('constraint_packet_tokens', ''))} |"
        )

    if any(isinstance(result.get("evaluation_execution"), dict) for result in results):
        lines.extend([
            "",
            "## Evaluation execution",
            "| task | condition | setup_phase | setup_status | setup_rc | public_status | public_rc | hidden_status | hidden_rc | compile_gate | contract |",
            "|---|---|---|---|---:|---|---:|---|---:|---|---|",
        ])
        for result in results:
            execution = result.get("evaluation_execution")
            if not isinstance(execution, dict):
                continue
            setup = execution.get("setup") if isinstance(execution.get("setup"), dict) else {}
            public = execution.get("public_tests") if isinstance(execution.get("public_tests"), dict) else {}
            hidden = execution.get("hidden_tests") if isinstance(execution.get("hidden_tests"), dict) else {}
            contract = result.get("evaluation_contract")
            contract = contract if isinstance(contract, dict) else {}
            lines.append(
                f"| {result.get('task_id', '')} | {result.get('condition_id', '')} | "
                f"{setup.get('phase', '')} | {setup.get('status', '')} | {setup.get('returncode', '')} | "
                f"{public.get('status', '')} | {public.get('returncode', '')} | "
                f"{hidden.get('status', '')} | {hidden.get('returncode', '')} | "
                f"{result.get('compile_status', '')} | {contract.get('status', '')} |"
            )

    status_path = run_dir / "status.json"
    if status_path.exists():
        try:
            artifact_integrity = json.loads(status_path.read_text(encoding="utf-8")).get("artifact_integrity")
        except json.JSONDecodeError:
            artifact_integrity = {"ok": False, "reason": "status_json_decode_failed"}
        lines.extend(["", "## Artifact integrity", "```json", json.dumps(artifact_integrity, indent=2, sort_keys=True), "```"])

    lines.extend(["", "## Condition results"])
    for condition, condition_results in sorted(by_condition.items()):
        resolved = [bool(r.get("resolved")) for r in condition_results]
        times = [r.get("metrics", {}).get("wall_time_seconds") for r in condition_results]
        times = [t for t in times if isinstance(t, (int, float))]
        rate = sum(resolved) / len(resolved) if resolved else 0.0
        lines.append(f"- `{condition}`: resolved={sum(resolved)}/{len(resolved)} ({rate:.1%}), median_time={median(times) if times else 'n/a'}")

    if any(result.get("condition_id") in {"docatlas_bounded_direct", "docatlas_bounded_subagent"} for result in results):
        lines.extend([
            "",
            "## Task 33 delivery metrics",
            "| condition | packet_status | packet_tokens | retained_context | parent_tokens | worker_tokens | system_tokens | retrieval_calls | first_edit | total_latency | evidence_fingerprint |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ])
        for result in results:
            if result.get("condition_id") not in {"docatlas_bounded_direct", "docatlas_bounded_subagent"}:
                continue
            metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
            parent_total = metrics.get("total_tokens")
            worker_total = metrics.get("worker_total_tokens")
            lines.append(
                f"| {result.get('condition_id')} | {metrics.get('action_packet_status', '')} | "
                f"{metrics.get('action_packet_tokens', '')} | {metrics.get('parent_retained_context_tokens', '')} | "
                f"{parent_total if parent_total is not None else ''} | {worker_total if worker_total is not None else ''} | "
                f"{metrics.get('system_total_tokens', '')} | {metrics.get('delivery_retrieval_calls', '')} | "
                f"{metrics.get('time_to_first_edit', '')} | {metrics.get('total_latency', '')} | "
                f"{metrics.get('evidence_fingerprint', '')} |"
            )
        completeness = metadata.get("task33c_completeness")
        if isinstance(completeness, dict):
            lines.extend(["", "Task 33C completeness:", "```json", json.dumps(completeness, indent=2, sort_keys=True), "```"])

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

    blocked_statuses = {
        "condition_setup_failed", "runner_unavailable", "runner_failed", "timeout",
    }
    blocked = sum(1 for result in results if result.get("status") in blocked_statuses)
    failure_summary = metadata.get("failure_summary")
    if failure_summary is None and blocked:
        failure_summary = (
            f"{blocked} run(s) did not produce a valid evaluated result because setup, "
            "the independent runner, or its execution budget failed."
        )
    lines.extend([
        "",
        "## Failures",
        failure_summary or "No independent agent failures were measured in this run.",
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
