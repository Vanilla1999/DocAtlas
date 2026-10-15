from __future__ import annotations

import hashlib

import pytest

from eval.task_level.analysis.task23_report import (
    _publish_report_artifacts,
    _retry_provenance,
    _source_artifact_hashes,
    build_task23_report,
    write_sanitized_run_bundle,
)


CONDITIONS = [
    "repo_only_strict_offline",
    "repo_plus_audited_external_context",
    "docatlas_tool_optional",
    "docatlas_tool_recommended",
]


























def _protocol() -> dict:
    return {
        "schema_version": "task23-protocol-1",
        "protocol_id": "task23-test",
        "frozen_before_results": True,
        "tasks": [
            {
                "task_id": f"task_{index}",
                "source_project": f"project_{index}",
                "domain": f"domain_{index}",
                "fixture_hash": "a" * 64,
                "oracle_sha256": "b" * 64,
                "external_context_sha256": "c" * 64,
            }
            for index in range(3)
        ],
        "conditions": CONDITIONS,
        "repeats_per_task_condition": 3,
        "controls": {
            "same_model": True,
            "same_prompt_policy": True,
            "same_context_limits": True,
            "same_attempt_budget": True,
            "same_starting_state": True,
        },
        "decision_rule": {
            "resolved_rate_improvement_min": 0.10,
            "median_total_tokens_increase_max": 0.10,
            "resolved_rate_equivalence_margin": 0.02,
            "median_total_tokens_reduction_min": 0.25,
            "median_latency_increase_max": 0.10,
            "confidence_level": 0.95,
            "fail_closed_on_missing_metrics": True,
        },
    }


def _rows() -> list[dict]:
    rows = []
    for task_index in range(3):
        for repeat in range(3):
            for condition in CONDITIONS:
                recommended = condition == "docatlas_tool_recommended"
                rows.append({
                    "task_id": f"task_{task_index}",
                    "repeat": repeat,
                    "condition_id": condition,
                    "status": "completed",
                    "resolved": recommended,
                    "compile_success": True,
                    "public_tests_passed": True,
                    "hidden_tests_passed": recommended,
                    "policy_clean": True,
                    "budget": {
                        "max_input_tokens": 2000,
                        "max_output_tokens": 1000,
                        "max_turns": 40,
                        "max_turns_enforced_by_runner": True,
                        "input_tokens_exceeded": False,
                        "output_tokens_exceeded": False,
                    },
                    "metrics": {
                        "total_tokens": 1050 if recommended else 1000,
                        "input_tokens": 900,
                        "output_tokens": 100,
                        "wall_time_seconds": 105 if recommended else 100,
                        "tool_output_tokens_estimate": 100,
                        "useful_context_ratio": None,
                        "docs_output_evidence_coverage": 0.25,
                        "condition_setup_wall_time_seconds": 1.0,
                        "required_evidence_recall": 0.5,
                        "first_required_evidence_rank": 2,
                    },
                })
    return rows





















