from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.product_truth_v1.comparative_contract import verify_report as verify_comparative
from eval.product_truth_v1.positive_controls import load_json
from eval.product_truth_v1.task_pack import verify_report as verify_task_pack


SCHEMA_VERSION = 1
PROTOCOL = "product-truth-execution-gate-v1"


def _execution_artifacts(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "README.md"
    )


def build_report(*, repo_root: Path) -> dict[str, Any]:
    protocol = load_json(repo_root / "eval" / "product_truth_v1" / "protocol.lock.json")
    task_pack = load_json(repo_root / "eval" / "product_truth_v1" / "results" / "task-pack.json")
    comparative = load_json(
        repo_root / "eval" / "product_truth_v1" / "results" / "comparative-harness.json"
    )
    verify_task_pack(task_pack)
    verify_comparative(comparative)

    task_ready = task_pack["summary"]["task_pack_ready"] is True
    comparative_authorized = (
        comparative["authorization"]["canary_authorized"] is True
        and comparative["authorization"]["full_pilot_authorized"] is True
    )
    authorized = bool(task_ready and comparative_authorized)
    artifact_root = repo_root / "eval" / "product_truth_v1" / "executions"
    artifacts = _execution_artifacts(artifact_root)

    if authorized:
        raise ValueError(
            "P2.2B/C authorized execution requires a separately reviewed provider-backed run carrier; "
            "this evidence-only gate must not start model runs implicitly"
        )
    if artifacts:
        raise ValueError(
            "P2.2B/C found execution artifacts while the task-pack authorization gate is closed"
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "protocol_sha256": protocol["protocol_sha256"],
        "authorization": {
            "task_pack_ready": task_ready,
            "comparative_harness_authorized": comparative_authorized,
            "scored_execution_authorized": authorized,
            "blocked_reason": "task_pack_not_ready",
        },
        "canary": {
            "preregistered_scored_runs": protocol["canary"]["scored_runs"],
            "planned_runs": comparative["plans"]["canary"]["planned_runs"],
            "executed_runs": 0,
            "status": "blocked_not_executed",
            "classification": "preregistered_eligibility_block",
            "model_failures": 0,
            "infrastructure_failures": 0,
            "artifact_files": [],
            "product_claim_allowed": False,
        },
        "full_pilot": {
            "minimum_scored_runs": protocol["benchmark_design"]["minimum_scored_runs"],
            "maximum_scored_runs": protocol["benchmark_design"]["maximum_scored_runs"],
            "planned_runs": comparative["plans"]["full_pilot"]["planned_runs"],
            "executed_runs": 0,
            "status": "blocked_not_executed",
            "classification": "preregistered_eligibility_block",
            "model_failures": 0,
            "infrastructure_failures": 0,
            "artifact_files": [],
        },
        "evidence": {
            "execution_root": "eval/product_truth_v1/executions",
            "unexpected_artifacts": artifacts,
            "task_pack_outcome": task_pack["decision"]["outcome"],
            "task_pack_blockers": task_pack["decision"]["blocking_reasons"],
            "comparative_blocked_reason": comparative["authorization"]["blocked_reason"],
        },
        "claim_boundary": {
            "p2_2b_canary_execution_complete": True,
            "p2_2c_full_pilot_execution_complete": True,
            "execution_complete_means_gate_evaluated_not_runs_performed": True,
            "product_truth_proven": False,
            "no_run_is_not_model_failure": True,
            "canary_product_claim_allowed": False,
            "correct_patch_comparison_available": False,
            "production_runtime_changed": False,
            "public_api_changed": False,
            "product_maturity": "Beta",
        },
        "decision": {
            "p2_2b_outcome": "not_executed_by_preregistered_gate",
            "p2_2c_outcome": "not_executed_by_preregistered_gate",
            "scored_runs": 0,
            "comparative_metrics_available": False,
            "next_step": "P2.3 product decision and closure scorecard",
        },
    }
    verify_report(report)
    return report


def verify_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION or report.get("protocol") != PROTOCOL:
        raise ValueError("P2.2B/C report identity mismatch")
    authorization = report.get("authorization")
    if not isinstance(authorization, dict):
        raise ValueError("P2.2B/C authorization missing")
    if authorization != {
        "task_pack_ready": False,
        "comparative_harness_authorized": False,
        "scored_execution_authorized": False,
        "blocked_reason": "task_pack_not_ready",
    }:
        raise ValueError("P2.2B/C authorization does not match the closed task-pack gate")

    canary = report.get("canary")
    full = report.get("full_pilot")
    if not isinstance(canary, dict) or not isinstance(full, dict):
        raise ValueError("P2.2B/C execution rows missing")
    if canary.get("preregistered_scored_runs") != 16:
        raise ValueError("P2.2B canary cardinality changed")
    if full.get("minimum_scored_runs") != 576 or full.get("maximum_scored_runs") != 720:
        raise ValueError("P2.2C pilot cardinality changed")
    for label, row in (("canary", canary), ("full_pilot", full)):
        if row.get("planned_runs") != 0 or row.get("executed_runs") != 0:
            raise ValueError(f"P2.2B/C {label} contains runs despite closed authorization")
        if row.get("status") != "blocked_not_executed":
            raise ValueError(f"P2.2B/C {label} status falsifies the gate outcome")
        if row.get("classification") != "preregistered_eligibility_block":
            raise ValueError(f"P2.2B/C {label} classification falsifies the gate outcome")
        if row.get("model_failures") != 0 or row.get("infrastructure_failures") != 0:
            raise ValueError(f"P2.2B/C {label} invents a model or infrastructure failure")
        if row.get("artifact_files") != []:
            raise ValueError(f"P2.2B/C {label} retains unauthorized execution artifacts")
    if canary.get("product_claim_allowed") is not False:
        raise ValueError("P2.2B lets a canary support a product claim")

    evidence = report.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("unexpected_artifacts") != []:
        raise ValueError("P2.2B/C hides unauthorized execution artifacts")
    if evidence.get("task_pack_outcome") != "task_pack_not_ready":
        raise ValueError("P2.2B/C task-pack evidence mismatch")
    if evidence.get("comparative_blocked_reason") != "task_pack_not_ready":
        raise ValueError("P2.2B/C comparative evidence mismatch")

    boundary = report.get("claim_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("P2.2B/C claim boundary missing")
    for key in (
        "product_truth_proven",
        "canary_product_claim_allowed",
        "correct_patch_comparison_available",
        "production_runtime_changed",
        "public_api_changed",
    ):
        if boundary.get(key) is not False:
            raise ValueError(f"P2.2B/C overclaims {key}")
    for key in (
        "p2_2b_canary_execution_complete",
        "p2_2c_full_pilot_execution_complete",
        "execution_complete_means_gate_evaluated_not_runs_performed",
        "no_run_is_not_model_failure",
    ):
        if boundary.get(key) is not True:
            raise ValueError(f"P2.2B/C lost required boundary {key}")
    if boundary.get("product_maturity") != "Beta":
        raise ValueError("P2.2B/C promotes product maturity")

    decision = report.get("decision")
    if not isinstance(decision, dict):
        raise ValueError("P2.2B/C decision missing")
    if decision.get("p2_2b_outcome") != "not_executed_by_preregistered_gate":
        raise ValueError("P2.2B outcome mismatch")
    if decision.get("p2_2c_outcome") != "not_executed_by_preregistered_gate":
        raise ValueError("P2.2C outcome mismatch")
    if decision.get("scored_runs") != 0 or decision.get("comparative_metrics_available") is not False:
        raise ValueError("P2.2B/C invents comparative results")


__all__ = ["PROTOCOL", "SCHEMA_VERSION", "build_report", "verify_report"]
