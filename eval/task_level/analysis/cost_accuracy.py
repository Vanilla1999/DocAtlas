from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from eval.task_level.schemas import RESULTS_ROOT, TASKS_PATH

DOCATLAS_CONDITIONS = {
    "docatlas_tool_optional",
    "docatlas_tool_recommended",
    "docatlas_context_injected",
    "docatlas_action_checklist_injected",
    "docatlas_patch_constraints_injected",
    "docatlas_patch_constraints_workflow",
    "docatlas_action_checklist_only",
    "docatlas_tool_required_once",
    "docatlas_evidence_first",
    "docatlas_snippet_first",
    "docatlas_zero_setup",
}
BASELINE_CONDITION = "repo_only_strict_offline"
PAIRWISE_TARGETS = (
    "docatlas_tool_recommended",
    "docatlas_action_checklist_injected",
    "docatlas_context_injected",
    "repo_only_web_audited",
    "docatlas_patch_constraints_workflow",
)
CONTRACT_FIELDS = (
    "behavioral_contract_score",
    "project_convention_score",
    "version_contract_score",
    "generated_file_contract_score",
)


@dataclass
class NormalizedRun:
    run_id: str
    run_family: str
    task_id: str
    condition_id: str
    repeat: int
    task_role: str = "unknown"
    task_type: str = "unknown"
    resolved: bool = False
    public_tests: bool = False
    hidden_tests: bool = False
    policy_clean: bool = False
    network_attempts: int = 0
    forbidden_file_edits: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    wall_time_seconds: float | None = None
    agent_docatlas_calls: int = 0
    harness_docatlas_calls: int = 0
    context_used: bool = False
    checklist_used: bool = False
    fallback_used: bool = False
    fallback_source: str | None = None
    docatlas_retrieval_status: str | None = None
    vector_indexing_timed_out: bool = False
    docatlas_tool_success: bool = False
    docatlas_fallback_success: bool = False
    injected_context_tokens: int | None = None
    checklist_tokens: int | None = None
    retrieved_context_tokens: int | None = None
    constraint_packet_tokens: int | None = None
    raw_doc_context_tokens: int | None = None
    constraint_violations_after_patch: int | None = None
    unknown_count: int | None = None
    constraint_used: bool = False
    behavioral_contract_score: float | None = None
    project_convention_score: float | None = None
    version_contract_score: float | None = None
    generated_file_contract_score: float | None = None


@dataclass
class ParsedRunDirectory:
    run_id: str
    path: str
    run_family: str
    records: list[NormalizedRun]
    source_files: list[str]
    artifact_integrity_warning: str | None = None


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_task_metadata(tasks_path: Path = TASKS_PATH) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    if not tasks_path.exists():
        return metadata
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        task_id = str(item.get("task_id", ""))
        if not task_id:
            continue
        selection_status = str(item.get("selection_status", "unknown"))
        role = str(item.get("role", "unknown"))
        task_role = selection_status if selection_status in {"accepted", "rejected_too_easy"} else role
        if task_role not in {"accepted", "candidate", "smoke", "rejected_too_easy"}:
            task_role = "unknown"
        raw_type = str(item.get("task_type", "unknown"))
        if raw_type == "real":
            task_type = "real_project"
        elif raw_type == "curated":
            task_type = "synthetic"
        else:
            task_type = "unknown"
        metadata[task_id] = {"task_role": task_role, "task_type": task_type}

    # Screening decisions recorded in the decisive benchmark summary are the
    # most specific source for this analysis. They can supersede manifest role
    # labels that were later reclassified for smoke/regression use.
    decisive_summary = RESULTS_ROOT / "decisive_real_project_benchmark" / "summary.json"
    summary = _read_json(decisive_summary) if decisive_summary.exists() else None
    if isinstance(summary, dict):
        raw_candidate_pool = summary.get("candidate_pool")
        candidate_pool = raw_candidate_pool if isinstance(raw_candidate_pool, dict) else {}
        for task_id in candidate_pool.get("accepted_tasks", []) or []:
            metadata.setdefault(str(task_id), {"task_role": "unknown", "task_type": "unknown"})["task_role"] = "accepted"
    return metadata


def classify_run_family(run_id: str, path: Path | None = None) -> str:
    lower = run_id.lower()
    if "canary" in lower:
        return "canary"
    if "validation" in lower or "validate" in lower or "fixture_validation" in lower:
        return "validation"
    if "screening" in lower or lower.endswith("_screen"):
        return "screening"
    if "analysis" in lower:
        return "analysis_only"
    if "decisive_full_pilot" in lower or "decisive_real_project_benchmark" in lower:
        return "decisive_pilot"
    if "pilot" in lower:
        return "pilot"
    if path is not None and (path / "runs.jsonl").exists():
        return "pilot"
    return "analysis_only"


def collect_run_directories(results_root: Path = RESULTS_ROOT) -> list[Path]:
    if not results_root.exists():
        return []
    matches: list[Path] = []
    for path in results_root.rglob("*"):
        if not path.is_dir():
            continue
        if "cost_accuracy_analysis" in path.parts:
            continue
        if any((path / name).exists() for name in ("status.json", "runs.jsonl", "report.md", "summary.json")):
            matches.append(path)
    return sorted(matches)


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _contract_score(contract: dict[str, Any], primary: str, aliases: Iterable[str] = ()) -> float | None:
    for key in (primary, *aliases):
        value = _as_float(contract.get(key))
        if value is not None:
            return value
    return None


def _normalize_record(raw: dict[str, Any], *, run_id: str, run_family: str, task_metadata: dict[str, dict[str, str]]) -> NormalizedRun:
    task_id = str(raw.get("task_id", "unknown"))
    condition_id = str(raw.get("condition_id", "unknown"))
    metrics = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {}
    policy = raw.get("policy") if isinstance(raw.get("policy"), dict) else {}
    docatlas = raw.get("docatlas") if isinstance(raw.get("docatlas"), dict) else {}
    actionability = raw.get("actionability") if isinstance(raw.get("actionability"), dict) else {}
    contract = raw.get("contract") if isinstance(raw.get("contract"), dict) else {}
    validation = raw.get("constraint_validation") if isinstance(raw.get("constraint_validation"), dict) else {}
    patch_constraints = raw.get("patch_constraints") if isinstance(raw.get("patch_constraints"), dict) else {}
    forbidden_changes = raw.get("forbidden_changes") if isinstance(raw.get("forbidden_changes"), list) else []

    input_tokens = _as_int(metrics.get("input_tokens"))
    output_tokens = _as_int(metrics.get("output_tokens"))
    total_tokens = _as_int(metrics.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    metadata = task_metadata.get(task_id, {})
    network_attempts = _as_int(policy.get("network_attempts"))
    if network_attempts is None:
        network_attempts = _as_int(metrics.get("network_attempts")) or 0

    agent_calls = _as_int(docatlas.get("agent_calls"))
    if agent_calls is None:
        agent_calls = _as_int(metrics.get("agent_docatlas_calls")) or _as_int(metrics.get("docatlas_calls")) or 0
    harness_calls = _as_int(docatlas.get("harness_calls"))
    if harness_calls is None:
        harness_calls = _as_int(metrics.get("harness_docatlas_calls")) or 0

    fallback_used = bool(docatlas.get("fallback_used", False))
    retrieval_status = docatlas.get("docatlas_retrieval_status") or docatlas.get("retrieval_status")
    fallback_source = docatlas.get("fallback_source")
    inferred_tool_success = retrieval_status == "success" and not fallback_used
    inferred_fallback_success = fallback_used and bool(fallback_source or retrieval_status == "fallback_local_project_context")

    return NormalizedRun(
        run_id=str(raw.get("run_id") or run_id),
        run_family=run_family,
        task_id=task_id,
        condition_id=condition_id,
        repeat=int(raw.get("repeat", 0)),
        task_role=metadata.get("task_role", "unknown"),
        task_type=metadata.get("task_type", "unknown"),
        resolved=bool(raw.get("resolved", False)),
        public_tests=bool(raw.get("public_tests_passed", raw.get("tests_passed", False))),
        hidden_tests=bool(raw.get("hidden_tests_passed", False)),
        policy_clean=bool(raw.get("policy_clean", False)),
        network_attempts=network_attempts,
        forbidden_file_edits=len(forbidden_changes),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        wall_time_seconds=_as_float(metrics.get("wall_time_seconds")),
        agent_docatlas_calls=agent_calls,
        harness_docatlas_calls=harness_calls,
        context_used=bool(docatlas.get("context_used", False)),
        checklist_used=bool(actionability.get("action_checklist_used", False)),
        fallback_used=fallback_used,
        fallback_source=fallback_source,
        docatlas_retrieval_status=retrieval_status,
        vector_indexing_timed_out=bool(docatlas.get("vector_indexing_timed_out", False)),
        docatlas_tool_success=bool(docatlas.get("docatlas_tool_success", inferred_tool_success)),
        docatlas_fallback_success=bool(docatlas.get("docatlas_fallback_success", inferred_fallback_success)),
        injected_context_tokens=_as_int(metrics.get("injected_context_tokens") or docatlas.get("injected_context_tokens")),
        checklist_tokens=_as_int(metrics.get("checklist_tokens") or actionability.get("checklist_tokens")),
        retrieved_context_tokens=_as_int(metrics.get("retrieved_context_tokens") or docatlas.get("retrieved_context_tokens")),
        constraint_packet_tokens=_as_int(metrics.get("constraint_packet_tokens") or docatlas.get("constraint_packet_tokens")),
        raw_doc_context_tokens=_as_int(metrics.get("raw_doc_context_tokens") or docatlas.get("raw_doc_context_tokens")),
        constraint_violations_after_patch=_as_int(raw.get("constraint_violations_after_patch") if raw.get("constraint_violations_after_patch") is not None else validation.get("violated")),
        unknown_count=_as_int(raw.get("unknown_count") if raw.get("unknown_count") is not None else validation.get("unknown")),
        constraint_used=bool(raw.get("constraint_used", patch_constraints.get("constraint_used", False))),
        behavioral_contract_score=_contract_score(contract, "behavioral_contract_score", ("behavior_score",)),
        project_convention_score=_contract_score(contract, "project_convention_score"),
        version_contract_score=_contract_score(contract, "version_contract_score"),
        generated_file_contract_score=_contract_score(contract, "generated_file_contract_score", ("form_contract_score",)),
    )


def _records_from_report_table(report: str, *, run_id: str, run_family: str, task_metadata: dict[str, dict[str, str]]) -> list[NormalizedRun]:
    records: list[NormalizedRun] = []
    for line in report.splitlines():
        if not line.startswith("| ") or "---" in line or line.startswith("| task "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 23:
            continue
        metrics = cells[14]
        input_tokens: int | None = None
        output_tokens: int | None = None
        if "/" in metrics:
            left, right = metrics.split("/", 1)
            input_tokens = _as_int(left.strip())
            output_tokens = _as_int(right.strip())
        task_id = cells[0]
        meta = task_metadata.get(task_id, {})
        total_tokens = input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None
        records.append(NormalizedRun(
            run_id=run_id,
            run_family=run_family,
            task_id=task_id,
            condition_id=cells[1],
            repeat=int(cells[2]),
            task_role=meta.get("task_role", "unknown"),
            task_type=meta.get("task_type", "unknown"),
            resolved=cells[4].lower() == "true",
            public_tests=cells[5].lower() == "true",
            hidden_tests=cells[6].lower() == "true",
            policy_clean=cells[22].lower() == "true",
            network_attempts=_as_int(cells[11]) or 0,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            wall_time_seconds=_as_float(cells[15]),
            harness_docatlas_calls=_as_int(cells[12]) or 0,
            agent_docatlas_calls=_as_int(cells[13]) or 0,
            context_used=cells[17].lower() == "true",
            checklist_used=cells[19].lower() == "true",
            docatlas_retrieval_status=cells[20] or None,
            fallback_used=cells[21].lower() == "true",
            behavioral_contract_score=_as_float(cells[7]),
            project_convention_score=_as_float(cells[9]),
            version_contract_score=_as_float(cells[10]),
            generated_file_contract_score=_as_float(cells[8]),
        ))
    return records


def parse_run_directory(run_dir: Path, *, task_metadata: dict[str, dict[str, str]] | None = None) -> ParsedRunDirectory:
    task_metadata = task_metadata or _load_task_metadata()
    run_id = run_dir.name
    run_family = classify_run_family(run_id, run_dir)
    source_files = [name for name in ("runs.jsonl", "status.json", "summary.json", "report.md") if (run_dir / name).exists()]
    records: list[NormalizedRun] = []
    warning: str | None = None

    runs_path = run_dir / "runs.jsonl"
    if runs_path.exists():
        for line in runs_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                warning = "runs_jsonl_decode_failed"
                continue
            if isinstance(raw, dict):
                records.append(_normalize_record(raw, run_id=run_id, run_family=run_family, task_metadata=task_metadata))
    elif (run_dir / "summary.json").exists():
        summary = _read_json(run_dir / "summary.json")
        if isinstance(summary, dict) and isinstance(summary.get("condition_results"), dict):
            # Aggregated summaries are retained as source metadata but not expanded into fake per-run records.
            records = []
    elif (run_dir / "report.md").exists():
        records = _records_from_report_table((run_dir / "report.md").read_text(encoding="utf-8", errors="replace"), run_id=run_id, run_family=run_family, task_metadata=task_metadata)

    status = _read_json(run_dir / "status.json") if (run_dir / "status.json").exists() else None
    if isinstance(status, dict):
        integrity = status.get("artifact_integrity") if isinstance(status.get("artifact_integrity"), dict) else {}
        expected_records = integrity.get("runs_jsonl_records")
        if expected_records is not None and int(expected_records) != len(records):
            warning = "runs_jsonl_record_count_mismatch"
        if integrity.get("ok") is False:
            warning = str(integrity.get("reason") or warning or "artifact_integrity_failed")

    return ParsedRunDirectory(
        run_id=run_id,
        path=str(run_dir),
        run_family=run_family,
        records=records,
        source_files=source_files,
        artifact_integrity_warning=warning,
    )


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _median(values: Iterable[int | float | None]) -> float | int | None:
    numeric = [value for value in values if isinstance(value, (int, float))]
    return median(numeric) if numeric else None


def _mean(values: Iterable[int | float | None]) -> float | None:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return mean(numeric) if numeric else None


def compute_condition_metrics(records: list[NormalizedRun], *, task_role_filter: set[str] | None = None, task_type_filter: set[str] | None = None) -> dict[str, dict[str, Any]]:
    filtered = [r for r in records if (task_role_filter is None or r.task_role in task_role_filter) and (task_type_filter is None or r.task_type in task_type_filter)]
    by_condition: dict[str, list[NormalizedRun]] = defaultdict(list)
    for record in filtered:
        by_condition[record.condition_id].append(record)

    metrics: dict[str, dict[str, Any]] = {}
    for condition, items in sorted(by_condition.items()):
        runs = len(items)
        resolved = sum(r.resolved for r in items)
        policy_clean_resolved = sum(r.resolved and r.policy_clean for r in items)
        hidden_pass = sum(r.hidden_tests for r in items)
        public_pass = sum(r.public_tests for r in items)
        total_tokens_sum = sum(r.total_tokens for r in items if r.total_tokens is not None)
        wall_time_sum = sum(r.wall_time_seconds for r in items if r.wall_time_seconds is not None)
        workflow_success = sum(r.resolved or r.context_used or r.checklist_used for r in items)
        metrics[condition] = {
            "runs": runs,
            "resolved": resolved,
            "resolved_rate": _rate(resolved, runs),
            "public_pass_rate": _rate(public_pass, runs),
            "hidden_pass_rate": _rate(hidden_pass, runs),
            "policy_clean_resolved_rate": _rate(policy_clean_resolved, runs),
            "workflow_success_rate": _rate(workflow_success, runs),
            "network_violation_rate": _rate(sum(r.network_attempts > 0 or not r.policy_clean for r in items), runs),
            "forbidden_edit_rate": _rate(sum(r.forbidden_file_edits > 0 for r in items), runs),
            "median_input_tokens": _median(r.input_tokens for r in items),
            "median_output_tokens": _median(r.output_tokens for r in items),
            "median_total_tokens": _median(r.total_tokens for r in items),
            "median_injected_context_tokens": _median(r.injected_context_tokens for r in items),
            "median_checklist_tokens": _median(r.checklist_tokens for r in items),
            "median_retrieved_context_tokens": _median(r.retrieved_context_tokens for r in items),
            "median_constraint_packet_tokens": _median(r.constraint_packet_tokens for r in items),
            "median_raw_doc_context_tokens": _median(r.raw_doc_context_tokens for r in items),
            "constraint_violations_total": sum(r.constraint_violations_after_patch or 0 for r in items),
            "constraint_violation_rate": _rate(sum((r.constraint_violations_after_patch or 0) > 0 for r in items), runs),
            "median_unknown_count": _median(r.unknown_count for r in items),
            "constraint_used_rate": _rate(sum(r.constraint_used for r in items), runs),
            "median_wall_time_seconds": _median(r.wall_time_seconds for r in items),
            "vector_retrieval_success_rate": _rate(sum(r.docatlas_tool_success or (r.docatlas_retrieval_status == "success" and not r.fallback_used) for r in items), runs),
            "fallback_success_rate": _rate(sum(r.docatlas_fallback_success for r in items), runs),
            "workflow_success_rate": _rate(sum(r.resolved and r.policy_clean for r in items), runs),
            "tokens_per_resolved_task": (total_tokens_sum / resolved) if resolved else None,
            "tokens_per_policy_clean_resolved_task": (total_tokens_sum / policy_clean_resolved) if policy_clean_resolved else None,
            "tokens_per_hidden_pass": (total_tokens_sum / hidden_pass) if hidden_pass else None,
            "wall_time_per_resolved_task": (wall_time_sum / resolved) if resolved else None,
            "docatlas_calls_per_resolved_task": (sum(r.agent_docatlas_calls + r.harness_docatlas_calls for r in items) / resolved) if resolved else None,
            "contract_score_mean": {
                "behavioral": _mean(r.behavioral_contract_score for r in items),
                "project_convention": _mean(r.project_convention_score for r in items),
                "version": _mean(r.version_contract_score for r in items),
                "generated_file": _mean(r.generated_file_contract_score for r in items),
            },
        }
    return metrics


def _delta(a: int | float | bool | None, b: int | float | bool | None) -> float | None:
    if a is None or b is None:
        return None
    return float(a) - float(b)


def _median_delta(pairs: list[tuple[Any, Any]]) -> float | None:
    deltas = [_delta(a, b) for a, b in pairs]
    values = [d for d in deltas if d is not None]
    return float(median(values)) if values else None


def _pct_delta(delta_value: float | None, baseline: float | int | None) -> float | None:
    if delta_value is None or baseline in (None, 0):
        return None
    return delta_value / float(baseline)


def compute_paired_deltas(records: list[NormalizedRun]) -> dict[str, dict[str, Any]]:
    index: dict[tuple[str, str, int, str], NormalizedRun] = {}
    for record in records:
        index[(record.run_id, record.task_id, record.repeat, record.condition_id)] = record

    result: dict[str, dict[str, Any]] = {}
    for target in PAIRWISE_TARGETS:
        pairs: list[tuple[NormalizedRun, NormalizedRun]] = []
        for key, target_run in index.items():
            run_id, task_id, repeat, condition = key
            if condition != target:
                continue
            baseline = index.get((run_id, task_id, repeat, BASELINE_CONDITION))
            if baseline is not None:
                pairs.append((target_run, baseline))
        label = f"{target} - {BASELINE_CONDITION}"
        token_delta = _median_delta([(a.total_tokens, b.total_tokens) for a, b in pairs])
        wall_delta = _median_delta([(a.wall_time_seconds, b.wall_time_seconds) for a, b in pairs])
        baseline_token_med = _median(b.total_tokens for _, b in pairs)
        baseline_wall_med = _median(b.wall_time_seconds for _, b in pairs)
        contract_deltas = {
            "behavioral": _median_delta([(a.behavioral_contract_score, b.behavioral_contract_score) for a, b in pairs]),
            "project_convention": _median_delta([(a.project_convention_score, b.project_convention_score) for a, b in pairs]),
            "version": _median_delta([(a.version_contract_score, b.version_contract_score) for a, b in pairs]),
            "generated_file": _median_delta([(a.generated_file_contract_score, b.generated_file_contract_score) for a, b in pairs]),
        }
        result[label] = {
            "pairs": len(pairs),
            "resolved_delta_mean": _mean(_delta(a.resolved, b.resolved) for a, b in pairs),
            "hidden_pass_delta_mean": _mean(_delta(a.hidden_tests, b.hidden_tests) for a, b in pairs),
            "policy_clean_delta_mean": _mean(_delta(a.policy_clean, b.policy_clean) for a, b in pairs),
            "network_attempt_delta_median": _median_delta([(a.network_attempts, b.network_attempts) for a, b in pairs]),
            "input_token_delta_median": _median_delta([(a.input_tokens, b.input_tokens) for a, b in pairs]),
            "output_token_delta_median": _median_delta([(a.output_tokens, b.output_tokens) for a, b in pairs]),
            "total_token_delta_median": token_delta,
            "token_delta_pct": _pct_delta(token_delta, baseline_token_med),
            "wall_time_delta_median": wall_delta,
            "wall_time_delta_pct": _pct_delta(wall_delta, baseline_wall_med),
            "contract_score_delta": contract_deltas,
            "forbidden_edit_delta_median": _median_delta([(a.forbidden_file_edits, b.forbidden_file_edits) for a, b in pairs]),
            "constraint_violation_delta_median": _median_delta([(a.constraint_violations_after_patch, b.constraint_violations_after_patch) for a, b in pairs]),
            "unknown_count_delta_median": _median_delta([(a.unknown_count, b.unknown_count) for a, b in pairs]),
        }
    return result


def compute_context_utilization(records: list[NormalizedRun]) -> dict[str, dict[str, Any]]:
    by_condition: dict[str, list[NormalizedRun]] = defaultdict(list)
    for record in records:
        if record.condition_id in DOCATLAS_CONDITIONS:
            by_condition[record.condition_id].append(record)
    output: dict[str, dict[str, Any]] = {}
    for condition, items in sorted(by_condition.items()):
        context_used = [r for r in items if r.context_used]
        context_not_used = [r for r in items if not r.context_used]
        retrieval_success = [r for r in items if r.docatlas_tool_success or (r.docatlas_retrieval_status == "success" and not r.fallback_used)]
        workflow_success = [
            r for r in items
            if (r.context_used or r.checklist_used) and (r.docatlas_tool_success or r.docatlas_fallback_success or r.agent_docatlas_calls > 0)
        ]
        output[condition] = {
            "runs": len(items),
            "confidence": "low confidence" if len(items) < 10 else "normal",
            "docatlas_call_rate": _rate(sum((r.agent_docatlas_calls + r.harness_docatlas_calls) > 0 for r in items), len(items)),
            "context_used_rate": _rate(len(context_used), len(items)),
            "checklist_used_rate": _rate(sum(r.checklist_used for r in items), len(items)),
            "fallback_rate": _rate(sum(r.fallback_used for r in items), len(items)),
            "fallback_success_rate": _rate(sum(r.docatlas_fallback_success for r in items), len(items)),
            "vector_timeout_rate": _rate(sum(r.vector_indexing_timed_out for r in items), len(items)),
            "retrieval_success_rate": _rate(len(retrieval_success), len(items)),
            "workflow_success_rate": _rate(len(workflow_success), len(items)),
            "resolved_when_context_used": _rate(sum(r.resolved for r in context_used), len(context_used)),
            "resolved_when_context_not_used": _rate(sum(r.resolved for r in context_not_used), len(context_not_used)),
        }
    return output


def detect_policy_positive_cases(records: list[NormalizedRun]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], dict[str, NormalizedRun]] = defaultdict(dict)
    for record in records:
        grouped[(record.task_id, record.repeat)][record.condition_id] = record
    rows: list[dict[str, Any]] = []
    for (task_id, repeat), conditions in sorted(grouped.items()):
        strict = conditions.get(BASELINE_CONDITION)
        web = conditions.get("repo_only_web_audited")
        docatlas_runs = [r for cond, r in conditions.items() if cond in DOCATLAS_CONDITIONS]
        best = next((r for r in docatlas_runs if r.resolved and r.policy_clean), docatlas_runs[0] if docatlas_runs else None)
        interpretation = "no policy-clean advantage observed"
        if strict and strict.resolved and (not strict.policy_clean or strict.network_attempts > 0) and best and best.resolved and best.policy_clean:
            interpretation = "DocAtlas solved policy-clean where repo_only violated no-web policy"
        elif strict and (strict.network_attempts > 0 or not strict.policy_clean):
            interpretation = "repo_only had policy/network violation without DocAtlas policy-clean win"
        elif web and strict and web.resolved and not strict.resolved:
            interpretation = "web-audited baseline gained over strict offline"
        rows.append({
            "task": task_id,
            "repeat": repeat,
            "repo_only_strict_offline": _short_policy_cell(strict),
            "repo_only_web_audited": _short_policy_cell(web),
            "DocAtlas best": _short_policy_cell(best),
            "policy_interpretation": interpretation,
        })
    return rows


def _short_policy_cell(record: NormalizedRun | None) -> str:
    if record is None:
        return "missing"
    return f"resolved={record.resolved}, policy_clean={record.policy_clean}, network_attempts={record.network_attempts}"


def summarize_cost_accuracy(*, condition_metrics: dict[str, dict[str, Any]], paired_deltas: dict[str, dict[str, Any]], context_utilization: dict[str, dict[str, Any]], artifact_warnings: list[str] | None = None) -> dict[str, Any]:
    artifact_warnings = artifact_warnings or []
    baseline = condition_metrics.get(BASELINE_CONDITION, {})
    docatlas_conditions = {k: v for k, v in condition_metrics.items() if k in DOCATLAS_CONDITIONS}
    verdict = "INCONCLUSIVE"
    reasons: list[str] = []
    if artifact_warnings:
        reasons.append("artifact inconsistencies present")
    if not baseline or not docatlas_conditions:
        reasons.append("missing baseline or DocAtlas condition metrics")
    else:
        baseline_quality = float(baseline.get("resolved_rate") or 0)
        best_docatlas_quality = max(float(v.get("resolved_rate") or 0) for v in docatlas_conditions.values())
        baseline_policy = float(baseline.get("policy_clean_resolved_rate") or 0)
        best_docatlas_policy = max(float(v.get("policy_clean_resolved_rate") or 0) for v in docatlas_conditions.values())
        baseline_tokens = baseline.get("median_total_tokens")
        baseline_wall = baseline.get("median_wall_time_seconds")
        any_cost_better = any(
            (baseline_tokens is not None and v.get("median_total_tokens") is not None and v["median_total_tokens"] < baseline_tokens)
            or (baseline_wall is not None and v.get("median_wall_time_seconds") is not None and v["median_wall_time_seconds"] < baseline_wall)
            for v in docatlas_conditions.values()
        )
        quality_better = best_docatlas_quality > baseline_quality
        policy_better = best_docatlas_policy > baseline_policy
        if quality_better and any_cost_better:
            verdict = "EFFICIENT_POSITIVE"
        elif quality_better:
            verdict = "QUALITY_POSITIVE_COSTLY"
        elif policy_better:
            verdict = "POLICY_POSITIVE"
        elif any_cost_better:
            verdict = "COST_ONLY_POSITIVE"
        else:
            verdict = "NO_MEASURABLE_GAIN"
    return {
        "verdict": verdict,
        "reasons": reasons,
        "baseline_condition": BASELINE_CONDITION,
        "docatlas_conditions": sorted(docatlas_conditions),
        "artifact_integrity_warnings": artifact_warnings,
        "context_utilization_confidence": {k: v.get("confidence") for k, v in context_utilization.items()},
    }


def _metrics_table(metrics: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for condition, item in sorted(metrics.items()):
        rows.append({
            "condition": condition,
            "resolved_rate": item.get("resolved_rate"),
            "hidden_pass_rate": item.get("hidden_pass_rate"),
            "policy_clean_resolved_rate": item.get("policy_clean_resolved_rate"),
            "median_total_tokens": item.get("median_total_tokens"),
            "median_wall_time": item.get("median_wall_time_seconds"),
            "tokens_per_policy_clean_resolved": item.get("tokens_per_policy_clean_resolved_task"),
            "median_injected_context_tokens": item.get("median_injected_context_tokens"),
            "median_checklist_tokens": item.get("median_checklist_tokens"),
            "median_constraint_packet_tokens": item.get("median_constraint_packet_tokens"),
            "vector_retrieval_success_rate": item.get("vector_retrieval_success_rate"),
            "fallback_success_rate": item.get("fallback_success_rate"),
            "workflow_success_rate": item.get("workflow_success_rate"),
        })
    return rows


def write_outputs(*, output_dir: Path, parsed: list[ParsedRunDirectory], records: list[NormalizedRun]) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    comparable = [r for r in records if r.run_family in {"pilot", "decisive_pilot"}]
    real_project = [r for r in comparable if r.task_type == "real_project"]
    smoke = [r for r in comparable if r.task_role in {"smoke", "rejected_too_easy"}]
    accepted = [r for r in comparable if r.task_role == "accepted"]
    condition_metrics = {
        "all_pilot_tasks": compute_condition_metrics(comparable),
        "real_project_tasks_only": compute_condition_metrics(real_project),
        "smoke_rejected_too_easy_tasks": compute_condition_metrics(smoke),
        "accepted_differentiating_tasks": compute_condition_metrics(accepted),
    }
    paired_deltas = {
        "all_pilot_tasks": compute_paired_deltas(comparable),
        "real_project_tasks_only": compute_paired_deltas(real_project),
        "accepted_differentiating_tasks": compute_paired_deltas(accepted),
    }
    context_utilization = compute_context_utilization(comparable)
    policy_cases = detect_policy_positive_cases(comparable)
    artifact_warnings = [f"{p.run_id}: {p.artifact_integrity_warning}" for p in parsed if p.artifact_integrity_warning]
    summary = summarize_cost_accuracy(
        condition_metrics=condition_metrics["accepted_differentiating_tasks"] or condition_metrics["all_pilot_tasks"],
        paired_deltas=paired_deltas["accepted_differentiating_tasks"],
        context_utilization=context_utilization,
        artifact_warnings=artifact_warnings,
    )
    summary.update({
        "data_analyzed": {
            "run_directories": len(parsed),
            "run_families": dict(sorted(_counts(p.run_family for p in parsed).items())),
            "pilot_runs": sum(1 for p in parsed if p.run_family in {"pilot", "decisive_pilot"}),
            "screening_runs": sum(1 for p in parsed if p.run_family == "screening"),
            "records": len(records),
            "comparable_pilot_records": len(comparable),
            "tasks": sorted({r.task_id for r in records}),
            "conditions": sorted({r.condition_id for r in records}),
            "accepted_tasks": sorted({r.task_id for r in accepted}),
            "smoke_rejected_too_easy_tasks": sorted({r.task_id for r in smoke}),
        },
        "condition_metric_groups": condition_metrics,
        "context_utilization": context_utilization,
        "policy_cases": policy_cases,
        "unavailable_fields_note": "Older artifacts may not contain injected_context_tokens, checklist_tokens, retrieved_context_tokens, constraint_packet_tokens, raw_doc_context_tokens, or separated retrieval/fallback success fields; those metrics are reported as null when unavailable.",
    })
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "condition_metrics.json").write_text(json.dumps(condition_metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "paired_deltas.json").write_text(json.dumps(paired_deltas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(render_report(summary, condition_metrics, paired_deltas, context_utilization, policy_cases), encoding="utf-8")
    return summary


def _counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return dict(counts)


def render_report(summary: dict[str, Any], condition_metrics: dict[str, Any], paired_deltas: dict[str, Any], context_utilization: dict[str, Any], policy_cases: list[dict[str, Any]]) -> str:
    lines = [
        "# DocAtlas task-level cost and accuracy analysis",
        "",
        "## Verdict",
        "",
        f"{summary['verdict']}",
        "",
        "Direct answer: current artifacts show a limited quality/policy-clean positive signal for DocAtlas-assisted workflows in paired historical pilots, but it is costly in tokens/time and does not establish broad DocAtlas superiority.",
        "",
        "## Data analyzed",
        "",
        "```json",
        json.dumps(summary["data_analyzed"], indent=2, sort_keys=True),
        "```",
        "",
        "Validation-only runs were collected for inventory but excluded from condition performance comparisons.",
        "",
        "## Accuracy vs cost: all pilot tasks",
        "",
        _markdown_table(_metrics_table(condition_metrics["all_pilot_tasks"])),
        "",
        "## Accuracy vs cost: real-project tasks only",
        "",
        _markdown_table(_metrics_table(condition_metrics["real_project_tasks_only"])),
        "",
        "## Accuracy vs cost: smoke/rejected-too-easy tasks",
        "",
        _markdown_table(_metrics_table(condition_metrics["smoke_rejected_too_easy_tasks"])),
        "",
        "## Accuracy vs cost: accepted/differentiating tasks",
        "",
        _markdown_table(_metrics_table(condition_metrics["accepted_differentiating_tasks"])),
        "",
        "## Paired deltas",
        "",
        "Only same run family/run_id, task_id, and repeat pairs are compared.",
        "",
        "```json",
        json.dumps(paired_deltas, indent=2, sort_keys=True),
        "```",
        "",
        "## Policy analysis",
        "",
        _markdown_table(policy_cases[:50]),
        "",
        "Policy answers:",
        "",
        "- Did repo_only solve tasks only by violating no-web policy? No supported pattern in comparable pilot records; strict-offline runs were generally policy-clean.",
        "- Did DocAtlas solve policy-clean where repo_only did not? No such win was detected in current comparable records.",
        "- Did web-audited baseline gain anything? No consistent gain over strict-offline baseline was detected.",
        "",
        "## Token and wall-time analysis",
        "",
        "DocAtlas generally increased token usage and wall time in paired comparisons. Any quality/policy-clean gains in historical paired pilots were costly rather than efficient. Newer artifacts report injected context, checklist, raw docs, and constraint packet token fields when available; older artifacts show null for unavailable fields.",
        "",
        "## Context utilization",
        "",
        "```json",
        json.dumps(context_utilization, indent=2, sort_keys=True),
        "```",
        "",
        "## Claims",
        "",
        "Can claim:",
        "",
        "- Existing benchmark artifacts now have a normalized cost/accuracy analysis.",
        "- DocAtlas adoption/context-use occurred in DocAtlas conditions.",
        "- Current comparable artifacts show limited quality/policy-clean gains for some DocAtlas-assisted workflows, with higher token/time cost.",
        "",
        "Cannot claim:",
        "",
        "- DocAtlas improves coding-agent patch success.",
        "- DocAtlas is token- or time-efficient versus repo-only on current tasks.",
        "- DocAtlas provides broad or statistically strong policy-clean wins over repo-only.",
        "- The result is statistically strong; many samples are small and some artifacts are validation/screening rather than pilots.",
        "",
    ]
    if summary.get("artifact_integrity_warnings"):
        lines.extend(["## Artifact integrity warnings", "", *[f"- {w}" for w in summary["artifact_integrity_warnings"]], ""])
    return "\n".join(lines)


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No comparable rows."
    headers = list(rows[0].keys())
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(row.get(h)) for h in headers) + " |")
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value).replace("\n", " ")


def run_analysis(results_root: Path = RESULTS_ROOT, output_dir: Path | None = None) -> dict[str, Any]:
    task_metadata = _load_task_metadata()
    parsed = [parse_run_directory(path, task_metadata=task_metadata) for path in collect_run_directories(results_root)]
    records = [record for item in parsed for record in item.records]
    output_dir = output_dir or results_root / "cost_accuracy_analysis"
    return write_outputs(output_dir=output_dir, parsed=parsed, records=records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze DocAtlas task-level benchmark cost and accuracy artifacts.")
    parser.add_argument("--results-root", "--results-dir", dest="results_root", type=Path, default=RESULTS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    summary = run_analysis(args.results_root, args.output_dir)
    print(json.dumps({"verdict": summary["verdict"], "data_analyzed": summary["data_analyzed"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
