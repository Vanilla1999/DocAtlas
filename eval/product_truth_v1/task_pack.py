from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from eval.product_truth_v1.positive_controls import load_json, load_tasks, verify_report as verify_positive_controls
from eval.task_level.fixtures.builder import FIXTURE_TASKS, HIDDEN_TEST_ROOT, ORACLE_ROOT, TEMPLATE_ROOT
from eval.task_level.schemas import VALIDATION_ROOT


SCHEMA_VERSION = 1
PROTOCOL = "product-truth-task-pack-v1"
MINIMUM_VALID_TASKS = 24
MINIMUM_REPOSITORIES = 3
MINIMUM_TASKS_PER_REPOSITORY = 8


def _validation(path: Path) -> tuple[bool, str | None]:
    if not path.is_file():
        return False, None
    payload = load_json(path)
    return payload.get("status") == "validated", str(payload.get("fixture_hash") or "") or None


def build_report(*, repo_root: Path) -> dict[str, Any]:
    protocol = load_json(repo_root / "eval" / "product_truth_v1" / "protocol.lock.json")
    protocol_sha = str(protocol["protocol_sha256"])
    positive_path = repo_root / "eval" / "product_truth_v1" / "results" / "positive-controls.json"
    positive = load_json(positive_path)
    verify_positive_controls(positive)
    positive_rows = {str(row["task_id"]): row for row in positive["tasks"]}
    tasks = load_tasks(repo_root / "eval" / "task_level" / "tasks.jsonl")
    oracle_control_root = repo_root / "eval" / "product_truth_v1" / "oracle-controls"

    rows: list[dict[str, Any]] = []
    for task_id in sorted(FIXTURE_TASKS):
        task = tasks.get(task_id)
        if task is None:
            raise ValueError(f"materialized fixture has no task spec: {task_id}")
        validation_ok, fixture_hash = _validation(VALIDATION_ROOT / f"{task_id}.json")
        template = TEMPLATE_ROOT / task_id
        patch = ORACLE_ROOT / f"{task_id}.patch"
        context = ORACLE_ROOT / f"{task_id}.context.json"
        hidden = HIDDEN_TEST_ROOT / task_id
        oracle_control = oracle_control_root / f"{task_id}.json"
        positive_row = positive_rows.get(task_id)
        two_clean_gold = bool(positive_row and positive_row.get("gold_reproducible") is True)
        real_model_oracle = bool(
            positive_row
            and positive_row.get("oracle_model_control", {}).get("status") == "passed"
            and positive_row.get("oracle_model_control", {}).get("real_model") is True
            and positive_row.get("oracle_model_control", {}).get("correct_patch") is True
        )
        structural = bool(
            template.is_dir()
            and patch.is_file()
            and hidden.is_dir()
            and validation_ok
            and context.is_file()
        )
        valid = bool(structural and two_clean_gold and real_model_oracle)
        missing: list[str] = []
        if not template.is_dir():
            missing.append("materialized_fixture")
        if not patch.is_file():
            missing.append("gold_patch")
        if not hidden.is_dir():
            missing.append("hidden_tests")
        if not validation_ok:
            missing.append("validated_gold_baseline")
        if not context.is_file():
            missing.append("oracle_evidence")
        if not two_clean_gold:
            missing.append("two_clean_gold_control")
        if not real_model_oracle:
            missing.append("real_model_oracle_control")
        rows.append({
            "task_id": task_id,
            "source_project": task.source_project or task.repo,
            "task_type": task.task_type,
            "ecosystem": task.ecosystem,
            "fixture_hash": fixture_hash,
            "assets": {
                "materialized_fixture": template.is_dir(),
                "gold_patch": patch.is_file(),
                "hidden_tests": hidden.is_dir(),
                "validated_gold_baseline": validation_ok,
                "oracle_evidence": context.is_file(),
                "oracle_model_control_file": oracle_control.is_file(),
            },
            "two_clean_gold_control": two_clean_gold,
            "real_model_oracle_control": real_model_oracle,
            "structurally_complete": structural,
            "task_valid": valid,
            "missing_requirements": missing,
        })

    all_by_project = Counter(str(row["source_project"]) for row in rows)
    structural_by_project = Counter(
        str(row["source_project"]) for row in rows if row["structurally_complete"]
    )
    valid_by_project = Counter(
        str(row["source_project"]) for row in rows if row["task_valid"]
    )
    capacity_repositories = sum(
        count >= MINIMUM_TASKS_PER_REPOSITORY for count in structural_by_project.values()
    )
    valid_repositories = sum(
        count >= MINIMUM_TASKS_PER_REPOSITORY for count in valid_by_project.values()
    )
    structural_capacity_met = bool(
        sum(structural_by_project.values()) >= MINIMUM_VALID_TASKS
        and capacity_repositories >= MINIMUM_REPOSITORIES
    )
    pack_ready = bool(
        sum(valid_by_project.values()) >= MINIMUM_VALID_TASKS
        and valid_repositories >= MINIMUM_REPOSITORIES
    )

    report = {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "protocol_sha256": protocol_sha,
        "requirements": {
            "minimum_valid_tasks": MINIMUM_VALID_TASKS,
            "minimum_repositories": MINIMUM_REPOSITORIES,
            "minimum_tasks_per_repository": MINIMUM_TASKS_PER_REPOSITORY,
        },
        "summary": {
            "task_specs_total": len(tasks),
            "materialized_fixture_tasks": len(rows),
            "structurally_complete_tasks": sum(row["structurally_complete"] for row in rows),
            "two_clean_gold_tasks": sum(row["two_clean_gold_control"] for row in rows),
            "real_model_oracle_tasks": sum(row["real_model_oracle_control"] for row in rows),
            "valid_tasks": sum(row["task_valid"] for row in rows),
            "all_tasks_by_project": dict(sorted(all_by_project.items())),
            "structural_tasks_by_project": dict(sorted(structural_by_project.items())),
            "valid_tasks_by_project": dict(sorted(valid_by_project.items())),
            "structural_capacity_met": structural_capacity_met,
            "task_pack_ready": pack_ready,
        },
        "tasks": rows,
        "claim_boundary": {
            "product_truth_proven": False,
            "candidate_count_is_not_valid_task_count": True,
            "missing_oracle_control_cannot_be_imputed": True,
            "canary_allowed": pack_ready,
            "full_pilot_allowed": pack_ready,
            "product_maturity": "Beta",
        },
        "decision": {
            "p2_1c_execution": "complete",
            "outcome": "task_pack_ready" if pack_ready else "task_pack_not_ready",
            "blocking_reasons": (
                [] if pack_ready else [
                    "structural_capacity_below_preregistered_minimum"
                    if not structural_capacity_met else
                    "real_model_positive_controls_incomplete"
                ]
            ),
            "next_step": "P2.2A comparative harness; execution remains fail-closed when task_pack_ready=false",
        },
    }
    verify_report(report)
    return report


def verify_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != PROTOCOL:
        raise ValueError("P2.1C report identity mismatch")
    requirements = report.get("requirements")
    if requirements != {
        "minimum_valid_tasks": MINIMUM_VALID_TASKS,
        "minimum_repositories": MINIMUM_REPOSITORIES,
        "minimum_tasks_per_repository": MINIMUM_TASKS_PER_REPOSITORY,
    }:
        raise ValueError("P2.1C preregistered cardinality changed")
    rows = report.get("tasks")
    if not isinstance(rows, list) or not rows:
        raise ValueError("P2.1C task rows missing")
    ids = [str(row.get("task_id") or "") for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or len(ids) != len(set(ids)):
        raise ValueError("P2.1C task identities invalid")
    for row in rows:
        assets = row.get("assets")
        if not isinstance(assets, dict):
            raise ValueError(f"{row.get('task_id')}: asset inventory missing")
        structural = all(
            assets.get(key) is True
            for key in (
                "materialized_fixture",
                "gold_patch",
                "hidden_tests",
                "validated_gold_baseline",
                "oracle_evidence",
            )
        )
        if row.get("structurally_complete") is not structural:
            raise ValueError(f"{row.get('task_id')}: structural completeness hidden or invented")
        valid = bool(
            structural
            and row.get("two_clean_gold_control") is True
            and row.get("real_model_oracle_control") is True
        )
        if row.get("task_valid") is not valid:
            raise ValueError(f"{row.get('task_id')}: task validity hidden or invented")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("P2.1C summary missing")
    structural_rows = [row for row in rows if row["structurally_complete"]]
    valid_rows = [row for row in rows if row["task_valid"]]
    structural_by_project = Counter(str(row["source_project"]) for row in structural_rows)
    valid_by_project = Counter(str(row["source_project"]) for row in valid_rows)
    structural_capacity = bool(
        len(structural_rows) >= MINIMUM_VALID_TASKS
        and sum(count >= MINIMUM_TASKS_PER_REPOSITORY for count in structural_by_project.values())
        >= MINIMUM_REPOSITORIES
    )
    ready = bool(
        len(valid_rows) >= MINIMUM_VALID_TASKS
        and sum(count >= MINIMUM_TASKS_PER_REPOSITORY for count in valid_by_project.values())
        >= MINIMUM_REPOSITORIES
    )
    expected = {
        "materialized_fixture_tasks": len(rows),
        "structurally_complete_tasks": len(structural_rows),
        "two_clean_gold_tasks": sum(row["two_clean_gold_control"] for row in rows),
        "real_model_oracle_tasks": sum(row["real_model_oracle_control"] for row in rows),
        "valid_tasks": len(valid_rows),
        "structural_tasks_by_project": dict(sorted(structural_by_project.items())),
        "valid_tasks_by_project": dict(sorted(valid_by_project.items())),
        "structural_capacity_met": structural_capacity,
        "task_pack_ready": ready,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise ValueError(f"P2.1C summary mismatch: {key}")
    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("P2.1C claim boundary missing")
    if boundary.get("product_truth_proven") is not False:
        raise ValueError("P2.1C overclaims Product Truth")
    if boundary.get("canary_allowed") is not ready or boundary.get("full_pilot_allowed") is not ready:
        raise ValueError("P2.1C execution authorization mismatch")
    if boundary.get("product_maturity") != "Beta":
        raise ValueError("P2.1C promotes product maturity")
    expected_outcome = "task_pack_ready" if ready else "task_pack_not_ready"
    if report.get("decision", {}).get("outcome") != expected_outcome:
        raise ValueError("P2.1C decision mismatch")


__all__ = [
    "MINIMUM_REPOSITORIES",
    "MINIMUM_TASKS_PER_REPOSITORY",
    "MINIMUM_VALID_TASKS",
    "PROTOCOL",
    "SCHEMA_VERSION",
    "build_report",
    "verify_report",
]
