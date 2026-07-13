from __future__ import annotations

import copy
import random
import re
from collections import Counter, defaultdict
from statistics import mean, median
from typing import Any, Callable


REQUIRED_CONDITIONS = (
    "repo_only_strict_offline",
    "repo_plus_audited_external_context",
    "docatlas_tool_optional",
    "docatlas_tool_recommended",
)
REQUIRED_CONTROLS = (
    "same_model",
    "same_prompt_policy",
    "same_context_limits",
    "same_attempt_budget",
    "same_starting_state",
)
PREDECLARED_DECISION_RULE = {
    "resolved_rate_improvement_min": 0.10,
    "median_total_tokens_increase_max": 0.10,
    "resolved_rate_equivalence_margin": 0.02,
    "median_total_tokens_reduction_min": 0.25,
    "median_latency_increase_max": 0.10,
    "confidence_level": 0.95,
    "fail_closed_on_missing_metrics": True,
}


def validate_protocol(protocol: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    raw_tasks = protocol.get("tasks")
    tasks = raw_tasks if isinstance(raw_tasks, list) else []
    domains = {
        str(task.get("domain") or task.get("source_project"))
        for task in tasks
        if isinstance(task, dict) and (task.get("domain") or task.get("source_project"))
    }
    if len(domains) < 3:
        errors.append("at_least_three_independent_domains_required")
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("task_id") or "unknown")
        for field in ("fixture_hash", "oracle_sha256", "external_context_sha256"):
            value = task.get(field)
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                errors.append(f"immutable_task_artifact_missing:{task_id}:{field}")
    if list(protocol.get("conditions") or []) != list(REQUIRED_CONDITIONS):
        errors.append("required_condition_matrix_mismatch")
    if int(protocol.get("repeats_per_task_condition") or 0) < 3:
        errors.append("at_least_three_repeats_required")
    raw_controls = protocol.get("controls")
    controls = raw_controls if isinstance(raw_controls, dict) else {}
    for name in REQUIRED_CONTROLS:
        if controls.get(name) is not True:
            errors.append(f"controlled_comparison_invariant_missing:{name}")
    if protocol.get("frozen_before_results") is not True:
        errors.append("protocol_not_frozen_before_results")
    if protocol.get("decision_rule") != PREDECLARED_DECISION_RULE:
        errors.append("predeclared_decision_rule_mismatch")
    return errors


def apply_protocol_amendment(protocol: dict[str, Any], amendment: dict[str, Any]) -> dict[str, Any]:
    """Apply a screening-only task replacement without permitting rule drift."""
    if amendment.get("schema_version") != "task23-protocol-amendment-1":
        raise ValueError("schema_version")
    if amendment.get("base_protocol_id") != protocol.get("protocol_id"):
        raise ValueError("base_protocol_id")
    for field in ("frozen_before_replacement_results", "conditions_unchanged", "decision_rule_unchanged"):
        if amendment.get(field) is not True:
            raise ValueError(field)
    if amendment.get("reason") != "predeclared_screening_exclusion":
        raise ValueError("reason")
    if amendment.get("excluded_screening_status") not in {"rejected_too_easy", "rejected_invalid"}:
        raise ValueError("excluded_screening_status")

    excluded = amendment.get("excluded_task_id")
    tasks = list(protocol.get("tasks", []))
    if sum(task.get("task_id") == excluded for task in tasks) != 1:
        raise ValueError("excluded_task_id")
    replacement = amendment.get("replacement_task")
    if not isinstance(replacement, dict):
        raise ValueError("replacement_task")

    effective = copy.deepcopy(protocol)
    effective["tasks"] = [task for task in tasks if task.get("task_id") != excluded] + [copy.deepcopy(replacement)]
    errors = validate_protocol(effective)
    if errors:
        raise ValueError("invalid_effective_protocol:" + ",".join(errors))
    effective["amendment_id"] = amendment.get("amendment_id")
    effective["base_protocol_id"] = protocol.get("protocol_id")
    return effective


def evaluate_predeclared_rule(
    rows: list[dict[str, Any]],
    *,
    protocol: dict[str, Any],
    baseline_condition: str = "repo_only_strict_offline",
    candidate_condition: str = "docatlas_tool_recommended",
    bootstrap_samples: int = 4000,
    seed: int = 23,
) -> dict[str, Any]:
    errors = validate_protocol(protocol)
    if "predeclared_decision_rule_mismatch" in errors:
        raise ValueError("predeclared_decision_rule_mismatch")

    reasons = [error for error in errors if error != "predeclared_decision_rule_mismatch"]
    pairs = _paired_rows(rows, baseline_condition, candidate_condition)
    paired_rows = list(pairs.values())
    expected_repeats = int(protocol.get("repeats_per_task_condition") or 0)
    counts = Counter(task_id for (task_id, _repeat) in pairs)
    if not pairs or any(count < expected_repeats for count in counts.values()):
        reasons.append("incomplete_task_repeat_matrix")
    if any(pair[0].get("total_tokens") is None or pair[1].get("total_tokens") is None for pair in paired_rows):
        reasons.append("missing_total_tokens")
    if any(pair[0].get("wall_time_seconds") is None or pair[1].get("wall_time_seconds") is None for pair in paired_rows):
        reasons.append("missing_wall_time_seconds")
    if reasons:
        return {
            "decision": "INCONCLUSIVE",
            "threshold_met": None,
            "reasons": list(dict.fromkeys(reasons)),
            "pairs": len(pairs),
            "uncertainty": {},
        }

    resolved = _bootstrap_ci(
        pairs,
        lambda sample: mean(float(bool(pair[1]["resolved"])) for pair in sample)
        - mean(float(bool(pair[0]["resolved"])) for pair in sample),
        samples=bootstrap_samples,
        seed=seed,
    )
    token_ratio = _bootstrap_ci(
        pairs,
        lambda sample: _relative_change(
            median(float(pair[0]["total_tokens"]) for pair in sample),
            median(float(pair[1]["total_tokens"]) for pair in sample),
        ),
        samples=bootstrap_samples,
        seed=seed + 1,
    )
    latency_ratio = _bootstrap_ci(
        pairs,
        lambda sample: _relative_change(
            median(float(pair[0]["wall_time_seconds"]) for pair in sample),
            median(float(pair[1]["wall_time_seconds"]) for pair in sample),
        ),
        samples=bootstrap_samples,
        seed=seed + 2,
    )
    rule = PREDECLARED_DECISION_RULE
    quality_met = (
        resolved["lower"] >= rule["resolved_rate_improvement_min"]
        and token_ratio["upper"] <= rule["median_total_tokens_increase_max"]
    )
    efficiency_met = (
        resolved["lower"] >= -rule["resolved_rate_equivalence_margin"]
        and resolved["upper"] <= rule["resolved_rate_equivalence_margin"]
        and token_ratio["upper"] <= -rule["median_total_tokens_reduction_min"]
        and latency_ratio["upper"] <= rule["median_latency_increase_max"]
    )
    threshold = "resolved_rate" if quality_met else "token_efficiency" if efficiency_met else None
    return {
        "decision": "CONTINUE" if threshold else "PIVOT_REQUIRED",
        "threshold_met": threshold,
        "reasons": [] if threshold else ["predeclared_threshold_not_met"],
        "pairs": len(pairs),
        "uncertainty": {
            "resolved_rate_delta": resolved,
            "token_change_ratio": token_ratio,
            "latency_change_ratio": latency_ratio,
        },
    }


def _paired_rows(
    rows: list[dict[str, Any]],
    baseline_condition: str,
    candidate_condition: str,
) -> dict[tuple[str, int], tuple[dict[str, Any], dict[str, Any]]]:
    grouped: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        condition = str(row.get("condition_id") or "")
        if condition not in {baseline_condition, candidate_condition}:
            continue
        key = (str(row.get("task_id") or ""), int(row.get("repeat") or 0))
        grouped[key][condition] = row
    return {
        key: (by_condition[baseline_condition], by_condition[candidate_condition])
        for key, by_condition in grouped.items()
        if baseline_condition in by_condition and candidate_condition in by_condition
    }


def _bootstrap_ci(
    pairs_by_key: dict[tuple[str, int], tuple[dict[str, Any], dict[str, Any]]],
    statistic: Callable[[list[tuple[dict[str, Any], dict[str, Any]]]], float],
    *,
    samples: int,
    seed: int,
) -> dict[str, float]:
    pairs = [pair for _key, pair in sorted(pairs_by_key.items())]
    observed = statistic(pairs)
    rng = random.Random(seed)
    estimates = sorted(statistic(rng.choices(pairs, k=len(pairs))) for _ in range(samples))
    lower_index = int(0.025 * (len(estimates) - 1))
    upper_index = int(0.975 * (len(estimates) - 1))
    return {
        "estimate": round(observed, 6),
        "lower": round(estimates[lower_index], 6),
        "upper": round(estimates[upper_index], 6),
    }


def _relative_change(baseline: float, candidate: float) -> float:
    if baseline <= 0:
        raise ValueError("paired baseline metric must be positive")
    return (candidate - baseline) / baseline
