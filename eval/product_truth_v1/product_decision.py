from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

from eval.product_truth_v1.comparative_contract import (
    verify_report as verify_comparative_report,
)
from eval.product_truth_v1.execution_gate import (
    verify_report as verify_execution_report,
)
from eval.product_truth_v1.protocol import (
    canonical_json,
    load_json,
    validate_protocol,
)
from eval.product_truth_v1.task_pack import verify_report as verify_task_pack_report


SCHEMA_VERSION = 1
PROTOCOL = "product-truth-product-decision-v1"
PHASE = "P2_PRODUCT_TRUTH"
OUTCOME = "PRODUCT_TRUTH_NOT_PROVEN"
ABSOLUTE_PATH_RE = re.compile(
    r"(?:^|[\s'\"])(?:/tmp/|/home/|/Users/|[A-Za-z]:\\Users\\)",
)
SOURCE_PATHS = {
    "protocol": "eval/product_truth_v1/protocol.lock.json",
    "positive_controls": "eval/product_truth_v1/results/positive-controls.json",
    "task_pack": "eval/product_truth_v1/results/task-pack.json",
    "comparative_harness": "eval/product_truth_v1/results/comparative-harness.json",
    "execution_gate": "eval/product_truth_v1/results/execution-gate.json",
}
SCORECARD_IDS = (
    "P2.1A",
    "P2.1B",
    "P2.1C",
    "P2.2A",
    "P2.2B",
    "P2.2C",
    "P2.3",
)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


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
        raise ValueError(f"unable to hash {path}: {completed.stderr.strip()[:200]}")
    value = completed.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError(f"invalid Git blob identity: {value!r}")
    return value


def _mapping(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    child = value.get(key)
    if not isinstance(child, dict):
        raise ValueError(f"P2.3 source report omitted {key}")
    return child


def _validate_positive_controls(report: Mapping[str, Any], protocol_sha256: str) -> None:
    if report.get("schema_version") != 1:
        raise ValueError("P2.1B positive-control schema mismatch")
    if report.get("protocol") != "product-truth-positive-controls-v1":
        raise ValueError("P2.1B positive-control identity mismatch")
    if report.get("protocol_sha256") != protocol_sha256:
        raise ValueError("P2.1B positive-control protocol mismatch")
    summary = _mapping(report, "summary")
    expected = {
        "task_count": 3,
        "gold_reproducible": 3,
        "oracle_evidence_present": 1,
        "real_model_oracle_passed": 0,
        "valid_tasks": 0,
    }
    if {key: summary.get(key) for key in expected} != expected:
        raise ValueError("P2.1B measured positive-control result changed")
    boundary = _mapping(report, "claim_boundary")
    if boundary.get("product_truth_proven") is not False:
        raise ValueError("P2.1B overclaims Product Truth")
    if boundary.get("provider_free_run_counts_as_oracle_control") is not False:
        raise ValueError("P2.1B accepts a provider-free oracle substitute")
    if boundary.get("product_maturity") != "Beta":
        raise ValueError("P2.1B promotes product maturity")


def _source_reports(repo_root: Path) -> dict[str, dict[str, str]]:
    return {
        key: {
            "path": relative,
            "git_blob_sha1": git_blob_sha(repo_root / relative, repo_root=repo_root),
        }
        for key, relative in SOURCE_PATHS.items()
    }


def build_report(*, repo_root: Path) -> dict[str, Any]:
    sources = {
        key: load_json(repo_root / relative)
        for key, relative in SOURCE_PATHS.items()
    }
    protocol = sources["protocol"]
    positive = sources["positive_controls"]
    task_pack = sources["task_pack"]
    comparative = sources["comparative_harness"]
    execution = sources["execution_gate"]

    validate_protocol(protocol)
    protocol_sha = str(protocol["protocol_sha256"])
    _validate_positive_controls(positive, protocol_sha)
    verify_task_pack_report(task_pack)
    verify_comparative_report(comparative)
    verify_execution_report(execution)

    for label, source in (
        ("task pack", task_pack),
        ("comparative harness", comparative),
        ("execution gate", execution),
    ):
        if source.get("protocol_sha256") != protocol_sha:
            raise ValueError(f"P2.3 {label} protocol identity mismatch")

    positive_summary = _mapping(positive, "summary")
    task_summary = _mapping(task_pack, "summary")
    task_requirements = _mapping(task_pack, "requirements")
    comparative_authorization = _mapping(comparative, "authorization")
    comparative_plans = _mapping(comparative, "plans")
    execution_decision = _mapping(execution, "decision")
    execution_authorization = _mapping(execution, "authorization")

    if task_summary.get("task_pack_ready") is not False:
        raise ValueError("P2.3 expected the preregistered task-pack gate to remain closed")
    if task_summary.get("valid_tasks") != 0:
        raise ValueError("P2.3 current evidence unexpectedly contains valid Product Truth tasks")
    if comparative_authorization.get("canary_authorized") is not False:
        raise ValueError("P2.3 current evidence unexpectedly authorizes the canary")
    if comparative_authorization.get("full_pilot_authorized") is not False:
        raise ValueError("P2.3 current evidence unexpectedly authorizes the full pilot")
    if execution_authorization.get("scored_execution_authorized") is not False:
        raise ValueError("P2.3 current evidence unexpectedly authorizes scored execution")
    if execution_decision.get("scored_runs") != 0:
        raise ValueError("P2.3 current evidence unexpectedly contains scored runs")
    if execution_decision.get("comparative_metrics_available") is not False:
        raise ValueError("P2.3 current evidence unexpectedly contains comparative metrics")

    measured_facts = {
        "positive_control_tasks": positive_summary["task_count"],
        "gold_reproducible_tasks": positive_summary["gold_reproducible"],
        "oracle_evidence_tasks": positive_summary["oracle_evidence_present"],
        "real_model_oracle_passed_tasks": positive_summary["real_model_oracle_passed"],
        "task_specs_total": task_summary["task_specs_total"],
        "materialized_fixture_tasks": task_summary["materialized_fixture_tasks"],
        "structurally_complete_tasks": task_summary["structurally_complete_tasks"],
        "two_clean_gold_tasks": task_summary["two_clean_gold_tasks"],
        "valid_tasks": task_summary["valid_tasks"],
        "required_valid_tasks": task_requirements["minimum_valid_tasks"],
        "required_repositories": task_requirements["minimum_repositories"],
        "required_tasks_per_repository": task_requirements[
            "minimum_tasks_per_repository"
        ],
        "canary_planned_runs": _mapping(comparative_plans, "canary")[
            "planned_runs"
        ],
        "canary_executed_runs": _mapping(execution, "canary")["executed_runs"],
        "full_pilot_planned_runs": _mapping(comparative_plans, "full_pilot")[
            "planned_runs"
        ],
        "full_pilot_executed_runs": _mapping(execution, "full_pilot")[
            "executed_runs"
        ],
        "comparative_metrics_available": execution_decision[
            "comparative_metrics_available"
        ],
    }

    report = {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "phase": PHASE,
        "protocol_sha256": protocol_sha,
        "execution_status": "CLOSED",
        "outcome": OUTCOME,
        "evidence_disposition": "preregistered_eligibility_block",
        "product_maturity": "Beta",
        "source_reports": _source_reports(repo_root),
        "source_report_set_sha256": sha256_json(_source_reports(repo_root)),
        "scorecard": [
            {
                "id": "P2.1A",
                "title": "Preregister Product Truth protocol and schemas",
                "execution_status": "closed",
                "evidence_status": "green_preregistered_protocol",
                "decision": (
                    "The causal protocol, schemas, budgets, conditions and "
                    "decision thresholds are frozen before scored execution."
                ),
            },
            {
                "id": "P2.1B",
                "title": "Gold-patch and oracle-evidence positive controls",
                "execution_status": "closed",
                "evidence_status": "negative_zero_valid_tasks",
                "decision": (
                    "Gold controls reproduce for three tasks, but no task has "
                    "a passing real-model oracle control."
                ),
            },
            {
                "id": "P2.1C",
                "title": "Preregistered valid task pack",
                "execution_status": "closed",
                "evidence_status": "blocked_task_pack_not_ready",
                "decision": (
                    "The repository has zero valid tasks and insufficient "
                    "cross-repository structural capacity for the frozen 24-task gate."
                ),
            },
            {
                "id": "P2.2A",
                "title": "Isolated four-condition comparative harness",
                "execution_status": "closed",
                "evidence_status": "green_harness_execution_blocked",
                "decision": (
                    "A/B/C/D isolation and randomization are implemented, but "
                    "no executable run identities are emitted while eligibility is closed."
                ),
            },
            {
                "id": "P2.2B",
                "title": "Sixteen-run canary",
                "execution_status": "closed",
                "evidence_status": "not_executed_by_preregistered_gate",
                "decision": (
                    "The canary was not authorized or run; this is not a model failure "
                    "and cannot support a product claim."
                ),
            },
            {
                "id": "P2.2C",
                "title": "Full 576-720-run pilot",
                "execution_status": "closed",
                "evidence_status": "not_executed_by_preregistered_gate",
                "decision": (
                    "The full pilot was not authorized or run; no comparative "
                    "correctness, safety, cost or latency metric exists."
                ),
            },
            {
                "id": "P2.3",
                "title": "Product and Stable decision",
                "execution_status": "closed",
                "evidence_status": "product_truth_not_proven",
                "decision": (
                    "Do not promote to Stable, do not authorize conditional expansion, "
                    "and retain Beta until a valid preregistered experiment is executed."
                ),
            },
        ],
        "measured_facts": measured_facts,
        "claim_boundary": {
            "p2_work_items_complete": True,
            "comparative_experiment_executed": False,
            "product_truth_proven": False,
            "product_failure_proven": False,
            "real_coding_outcome_improvement_proven": False,
            "correct_patch_comparison_available": False,
            "safety_comparison_available": False,
            "stable_claim_allowed": False,
            "p3_conditional_expansion_authorized": False,
            "retrieval_expansion_authorized": False,
            "production_runtime_changed": False,
            "public_api_changed": False,
            "public_release_truth_closed": False,
        },
        "decision": {
            "stable_decision": "DO_NOT_PROMOTE",
            "conditional_expansion_decision": "NOT_AUTHORIZED",
            "retrieval_expansion_decision": "PAUSE",
            "accepted_production_changes": [],
            "interpretation": (
                "Product Truth is not proven because the preregistered eligibility "
                "gate prevented the comparative experiment; product failure is also "
                "not proven."
            ),
            "next_step": (
                "Reopen Product Truth only after constructing a preregistered valid "
                "task pack and passing real-model oracle controls."
            ),
        },
        "reopening_conditions": {
            "minimum_valid_tasks": 24,
            "minimum_repositories": 3,
            "minimum_valid_tasks_per_repository": 8,
            "clean_gold_repetitions_per_task": 2,
            "real_model_oracle_pass_required_per_task": True,
            "oracle_uses_same_model_tools_and_budgets": True,
            "gold_oracle_and_hidden_artifacts_model_visible": False,
            "protocol_preregistered_before_scored_runs": True,
            "canary_runs_after_eligibility": 16,
            "canary_can_support_product_claim": False,
            "full_pilot_minimum_runs_after_green_canary": 576,
            "full_pilot_maximum_runs_after_green_canary": 720,
        },
    }
    verify_report(report)
    return report


def verify_report(report: Mapping[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("P2.3 schema version mismatch")
    if report.get("protocol") != PROTOCOL or report.get("phase") != PHASE:
        raise ValueError("P2.3 report identity mismatch")
    if report.get("execution_status") != "CLOSED":
        raise ValueError("P2.3 worklist is not closed")
    if report.get("outcome") != OUTCOME:
        raise ValueError("P2.3 falsifies the Product Truth outcome")
    if report.get("evidence_disposition") != "preregistered_eligibility_block":
        raise ValueError("P2.3 evidence disposition mismatch")
    if report.get("product_maturity") != "Beta":
        raise ValueError("P2.3 promotes product maturity")

    sources = report.get("source_reports")
    if not isinstance(sources, dict) or set(sources) != set(SOURCE_PATHS):
        raise ValueError("P2.3 source report inventory mismatch")
    for key, relative in SOURCE_PATHS.items():
        row = sources.get(key)
        if not isinstance(row, dict) or row.get("path") != relative:
            raise ValueError(f"P2.3 source path mismatch: {key}")
        if not re.fullmatch(r"[0-9a-f]{40}", str(row.get("git_blob_sha1") or "")):
            raise ValueError(f"P2.3 source identity invalid: {key}")
    if report.get("source_report_set_sha256") != sha256_json(sources):
        raise ValueError("P2.3 source report set hash mismatch")

    rows = report.get("scorecard")
    if not isinstance(rows, list):
        raise ValueError("P2.3 scorecard missing")
    if tuple(row.get("id") for row in rows if isinstance(row, dict)) != SCORECARD_IDS:
        raise ValueError("P2.3 scorecard is incomplete or reordered")
    if len(rows) != len(SCORECARD_IDS):
        raise ValueError("P2.3 scorecard contains a non-object row")
    if any(row.get("execution_status") != "closed" for row in rows):
        raise ValueError("P2.3 scorecard contains an open work item")
    expected_statuses = {
        "P2.1A": "green_preregistered_protocol",
        "P2.1B": "negative_zero_valid_tasks",
        "P2.1C": "blocked_task_pack_not_ready",
        "P2.2A": "green_harness_execution_blocked",
        "P2.2B": "not_executed_by_preregistered_gate",
        "P2.2C": "not_executed_by_preregistered_gate",
        "P2.3": "product_truth_not_proven",
    }
    if {row["id"]: row.get("evidence_status") for row in rows} != expected_statuses:
        raise ValueError("P2.3 scorecard evidence status mismatch")

    facts = report.get("measured_facts")
    if not isinstance(facts, dict):
        raise ValueError("P2.3 measured facts missing")
    expected_facts = {
        "positive_control_tasks": 3,
        "gold_reproducible_tasks": 3,
        "oracle_evidence_tasks": 1,
        "real_model_oracle_passed_tasks": 0,
        "task_specs_total": 21,
        "materialized_fixture_tasks": 15,
        "structurally_complete_tasks": 12,
        "two_clean_gold_tasks": 3,
        "valid_tasks": 0,
        "required_valid_tasks": 24,
        "required_repositories": 3,
        "required_tasks_per_repository": 8,
        "canary_planned_runs": 0,
        "canary_executed_runs": 0,
        "full_pilot_planned_runs": 0,
        "full_pilot_executed_runs": 0,
        "comparative_metrics_available": False,
    }
    if facts != expected_facts:
        raise ValueError("P2.3 measured facts do not match the frozen evidence")

    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("P2.3 claim boundary missing")
    if boundary.get("p2_work_items_complete") is not True:
        raise ValueError("P2.3 did not close every planned work item")
    if boundary.get("comparative_experiment_executed") is not False:
        raise ValueError("P2.3 invents a comparative experiment")
    for key in (
        "product_truth_proven",
        "product_failure_proven",
        "real_coding_outcome_improvement_proven",
        "correct_patch_comparison_available",
        "safety_comparison_available",
        "stable_claim_allowed",
        "p3_conditional_expansion_authorized",
        "retrieval_expansion_authorized",
        "production_runtime_changed",
        "public_api_changed",
        "public_release_truth_closed",
    ):
        if boundary.get(key) is not False:
            raise ValueError(f"P2.3 overclaims {key}")

    decision = report.get("decision")
    if not isinstance(decision, dict):
        raise ValueError("P2.3 decision missing")
    if decision.get("stable_decision") != "DO_NOT_PROMOTE":
        raise ValueError("P2.3 Stable decision mismatch")
    if decision.get("conditional_expansion_decision") != "NOT_AUTHORIZED":
        raise ValueError("P2.3 improperly authorizes conditional expansion")
    if decision.get("retrieval_expansion_decision") != "PAUSE":
        raise ValueError("P2.3 does not pause retrieval expansion")
    if decision.get("accepted_production_changes") != []:
        raise ValueError("P2.3 accepts an unproven production change")
    interpretation = str(decision.get("interpretation") or "")
    if "Product Truth is not proven" not in interpretation:
        raise ValueError("P2.3 interpretation hides the Product Truth boundary")
    if "product failure is also not proven" not in interpretation:
        raise ValueError("P2.3 interpretation misclassifies the negative evidence")

    reopening = report.get("reopening_conditions")
    if reopening != {
        "minimum_valid_tasks": 24,
        "minimum_repositories": 3,
        "minimum_valid_tasks_per_repository": 8,
        "clean_gold_repetitions_per_task": 2,
        "real_model_oracle_pass_required_per_task": True,
        "oracle_uses_same_model_tools_and_budgets": True,
        "gold_oracle_and_hidden_artifacts_model_visible": False,
        "protocol_preregistered_before_scored_runs": True,
        "canary_runs_after_eligibility": 16,
        "canary_can_support_product_claim": False,
        "full_pilot_minimum_runs_after_green_canary": 576,
        "full_pilot_maximum_runs_after_green_canary": 720,
    }:
        raise ValueError("P2.3 reopening conditions changed")

    if ABSOLUTE_PATH_RE.search(canonical_json(report)):
        raise ValueError("P2.3 report contains an absolute local path")


__all__ = [
    "OUTCOME",
    "PHASE",
    "PROTOCOL",
    "SCHEMA_VERSION",
    "build_report",
    "verify_report",
]
