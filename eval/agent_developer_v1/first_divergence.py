from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


PROTOCOL = "agent-developer-first-divergence-v1"
SCHEMA_VERSION = 1
EXPECTED_CLASS_COUNTS = {
    "module_selector_cardinality": 8,
    "retrieval_query_drift": 2,
    "trajectory_order": 1,
}
ALLOWED_CLASSES = frozenset(EXPECTED_CLASS_COUNTS)
ALLOWED_STAGES = frozenset({
    "model_action_validation",
    "model_planning",
    "retrieval",
})
ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|[\s'\"])(?:/tmp/|/home/|/Users/|[A-Za-z]:\\Users\\)",
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def git_blob_sha(path: Path, *, repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "hash-object", str(path)],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"unable to compute Git blob identity for {path}: "
            f"{completed.stderr.strip()[:200]}"
        )
    value = completed.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError(f"invalid Git blob identity for {path}: {value!r}")
    return value


def _scope_signature(call: dict[str, Any]) -> str:
    scope = str(call.get("scope") or "").strip()
    mode = str(call.get("mode") or "").strip()
    if not scope and mode == "dependency":
        scope = "dependency"
    parts = [scope or "unknown"]
    for key in ("module", "module_path"):
        value = str(call.get(key) or "").strip()
        if value:
            parts.append(f"{key}={value}")
    return ";".join(parts)


def _expected_trajectory(oracle_task: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    for call in oracle_task.get("calls") or ():
        if not isinstance(call, dict):
            continue
        steps.append(f"get_docs_context|{_scope_signature(call)}")
        recovery = call.get("target_recovery")
        retry = recovery.get("retry") if isinstance(recovery, dict) else None
        if isinstance(retry, dict):
            steps.append("docs_status|project")
            steps.append(f"get_docs_context|{_scope_signature(retry)}")
    return steps


def _actual_trajectory(report_task: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    for record in report_task.get("trajectory") or ():
        if not isinstance(record, dict):
            continue
        action = record.get("action")
        action = action if isinstance(action, dict) else {}
        tool = str(record.get("tool") or action.get("action") or "unknown")
        status = str(record.get("status") or "") or "none"
        steps.append(f"{tool}|{_scope_signature(action)}|status={status}")
    return steps


def _classify(report_task: dict[str, Any], oracle_task: dict[str, Any]) -> dict[str, Any]:
    expected = _expected_trajectory(oracle_task)
    actual = _actual_trajectory(report_task)
    score = report_task.get("score")
    score = score if isinstance(score, dict) else {}
    errors = [str(value)[:500] for value in score.get("errors") or ()][:8]
    error_text = "\n".join(errors).lower()

    if not actual and "module retrieval requires exactly one of module or module_path" in error_text:
        stage = "model_action_validation"
        failure_class = "module_selector_cardinality"
        model_reason = (
            "The first module retrieval was rejected because the action did not satisfy "
            "the exactly-one-of module/module_path contract."
        )
        server_reason = "No get_docs_context request reached MCP retrieval."
        repair = (
            "Build the same first call with only the exact module_path derivable from "
            "working_path; do not send module at the same time."
        )
        limit = (
            "The historical report retained the validation error but not the rejected "
            "action, so missing-selector and both-selectors cases cannot be separated."
        )
    elif expected and actual and actual[0].split("|status=", 1)[0] != expected[0]:
        stage = "model_planning"
        failure_class = "trajectory_order"
        model_reason = (
            "The model chose a schema-valid evidence lane, but started with a later lane "
            "instead of the evaluator-required first step."
        )
        server_reason = f"Expected first step {expected[0]!r}; observed {actual[0]!r}."
        repair = (
            "Execute the required module-local call first, then request dependency evidence "
            "within the existing two-call budget."
        )
        limit = None
    else:
        stage = "retrieval"
        failure_class = "retrieval_query_drift"
        model_reason = (
            "The model selected the correct scope but replaced the frozen exact identity "
            "question with a broader paraphrase."
        )
        server_reason = (
            "The server returned insufficient_evidence without the required source; the "
            "first divergence is retrieval/proofability rather than schema validation."
        )
        repair = (
            "Keep the selected scope and ask the exact named-identity question frozen by "
            "the evaluator contract."
        )
        limit = (
            "This is historical in-process model evidence, not a fresh installed-wheel "
            "provider run."
        )

    return {
        "task_id": str(report_task.get("task_id") or ""),
        "expected_trajectory": expected,
        "actual_trajectory": actual,
        "first_divergence": {
            "stage": stage,
            "failure_class": failure_class,
        },
        "model_visible_reason": model_reason,
        "server_side_reason": server_reason,
        "minimal_successful_repair": repair,
        "evidence_limit": limit,
    }


def derive_atlas(
    *,
    report: dict[str, Any],
    oracle: dict[str, Any],
    public_tasks: dict[str, Any],
    source_identities: dict[str, str],
) -> dict[str, Any]:
    report_rows = report.get("tasks")
    oracle_rows = oracle.get("trajectories")
    public_rows = public_tasks.get("tasks")
    if not isinstance(report_rows, list) or not isinstance(oracle_rows, list):
        raise ValueError("historical report and oracle must contain task arrays")
    if not isinstance(public_rows, list):
        raise ValueError("public task contract must contain a task array")

    report_by_id = {
        str(row.get("task_id") or ""): row
        for row in report_rows
        if isinstance(row, dict)
    }
    oracle_by_id = {
        str(row.get("id") or ""): row
        for row in oracle_rows
        if isinstance(row, dict)
    }
    public_ids = [
        str(row.get("id") or "")
        for row in public_rows
        if isinstance(row, dict)
    ]
    if set(report_by_id) != set(oracle_by_id) or set(public_ids) != set(report_by_id):
        raise ValueError("historical report, oracle and public task identities differ")

    rows = [
        _classify(report_by_id[task_id], oracle_by_id[task_id])
        for task_id in public_ids
    ]
    counts = dict(sorted(Counter(
        row["first_divergence"]["failure_class"] for row in rows
    ).items()))
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "status": "complete_historical_atlas",
        "claim_boundary": {
            "historical_model_report": True,
            "fresh_installed_model_run": False,
            "autonomous_agent_truth_proven": False,
            "public_api_change_authorized": False,
        },
        "source_identities": source_identities,
        "source_metrics": {
            "task_count": int(report.get("task_count") or 0),
            "passed_tasks": int(report.get("passed_tasks") or 0),
            "false_supported": int(report.get("false_supported") or 0),
            "forbidden_source_contamination": int(
                report.get("forbidden_source_contamination") or 0
            ),
            "provider_id": str(report.get("provider_id") or ""),
            "model": str(report.get("model") or ""),
        },
        "summary": {
            "task_count": len(rows),
            "failure_class_counts": counts,
            "repeated_failure_classes": [
                key for key, value in counts.items() if value > 1
            ],
        },
        "tasks": rows,
        "decision": {
            "p1_2": "closed_with_historical_evidence",
            "next_step": "run P1.3 ablations against the repeated failure classes",
            "api_freeze": True,
        },
    }


def verify_atlas(atlas: dict[str, Any]) -> None:
    if atlas.get("schema_version") != SCHEMA_VERSION or atlas.get("protocol") != PROTOCOL:
        raise ValueError("first-divergence atlas identity mismatch")
    tasks = atlas.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 11:
        raise ValueError("first-divergence atlas must contain exactly 11 tasks")
    ids = [str(row.get("task_id") or "") for row in tasks if isinstance(row, dict)]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise ValueError("first-divergence task identities are invalid or duplicated")
    counts: Counter[str] = Counter()
    for row in tasks:
        if not isinstance(row, dict):
            raise ValueError("every first-divergence row must be an object")
        divergence = row.get("first_divergence")
        if not isinstance(divergence, dict):
            raise ValueError("first-divergence row omitted its divergence")
        stage = str(divergence.get("stage") or "")
        failure_class = str(divergence.get("failure_class") or "")
        if stage not in ALLOWED_STAGES or failure_class not in ALLOWED_CLASSES:
            raise ValueError("first-divergence row has an unsupported class or stage")
        if not isinstance(row.get("expected_trajectory"), list):
            raise ValueError("first-divergence row omitted expected trajectory")
        if not isinstance(row.get("actual_trajectory"), list):
            raise ValueError("first-divergence row omitted actual trajectory")
        for key in (
            "model_visible_reason",
            "server_side_reason",
            "minimal_successful_repair",
        ):
            if not str(row.get(key) or "").strip():
                raise ValueError(f"first-divergence row omitted {key}")
        counts[failure_class] += 1
    if dict(sorted(counts.items())) != EXPECTED_CLASS_COUNTS:
        raise ValueError(f"historical failure class counts changed: {dict(counts)!r}")
    summary = atlas.get("summary")
    if not isinstance(summary, dict) or summary.get("failure_class_counts") != EXPECTED_CLASS_COUNTS:
        raise ValueError("atlas summary does not match classified rows")
    metrics = atlas.get("source_metrics")
    if not isinstance(metrics, dict):
        raise ValueError("atlas omitted source metrics")
    if metrics.get("task_count") != 11 or metrics.get("passed_tasks") != 0:
        raise ValueError("atlas no longer describes the frozen historical 0/11 run")
    if metrics.get("false_supported") != 0 or metrics.get("forbidden_source_contamination") != 0:
        raise ValueError("unsafe historical outcomes cannot be hidden by the atlas")
    boundary = atlas.get("claim_boundary")
    if not isinstance(boundary, dict) or any(
        boundary.get(key) is not False
        for key in (
            "fresh_installed_model_run",
            "autonomous_agent_truth_proven",
            "public_api_change_authorized",
        )
    ):
        raise ValueError("atlas overclaims fresh evidence or API authorization")
    if ABSOLUTE_PATH_RE.search(canonical_json(atlas)):
        raise ValueError("atlas contains an absolute local path")


def derive_from_paths(
    *,
    repo_root: Path,
    report_path: Path,
    oracle_path: Path,
    tasks_path: Path,
) -> dict[str, Any]:
    return derive_atlas(
        report=load_json(report_path),
        oracle=load_json(oracle_path),
        public_tasks=load_json(tasks_path),
        source_identities={
            "historical_report_git_blob_sha1": git_blob_sha(
                report_path, repo_root=repo_root
            ),
            "oracle_git_blob_sha1": git_blob_sha(
                oracle_path, repo_root=repo_root
            ),
            "public_tasks_git_blob_sha1": git_blob_sha(
                tasks_path, repo_root=repo_root
            ),
        },
    )
