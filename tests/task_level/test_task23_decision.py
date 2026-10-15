from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from eval.task_level.analysis.task23_decision import apply_protocol_amendment, evaluate_predeclared_rule, validate_protocol, validate_protocol_amendment_artifacts
from eval.task_level.fixtures.builder import fixture_hash


REQUIRED_CONDITIONS = [
    "repo_only_strict_offline",
    "repo_plus_audited_external_context",
    "docatlas_tool_optional",
    "docatlas_tool_recommended",
]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _protocol(*, domains: list[str] | None = None, repeats: int = 3) -> dict:
    return {
        "schema_version": "task23-protocol-1",
        "frozen_before_results": True,
        "tasks": [
            {
                "task_id": f"task_{index}",
                "source_project": domain,
                "domain": domain,
                "fixture_hash": "a" * 64,
                "oracle_sha256": "b" * 64,
                "external_context_sha256": "c" * 64,
            }
            for index, domain in enumerate(domains or ["nbo", "help_chat", "viscanner"], start=1)
        ],
        "conditions": REQUIRED_CONDITIONS,
        "repeats_per_task_condition": repeats,
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


def _rows(*, doc_resolved: list[bool], base_resolved: list[bool], doc_tokens: int, base_tokens: int, doc_latency: float, base_latency: float) -> list[dict]:
    rows: list[dict] = []
    for index, (base, doc) in enumerate(zip(base_resolved, doc_resolved, strict=True)):
        task_id = f"task_{index // 3 + 1}"
        repeat = index % 3
        rows.extend(
            [
                {"task_id": task_id, "repeat": repeat, "condition_id": "repo_only_strict_offline", "resolved": base, "total_tokens": base_tokens, "wall_time_seconds": base_latency},
                {"task_id": task_id, "repeat": repeat, "condition_id": "docatlas_tool_recommended", "resolved": doc, "total_tokens": doc_tokens, "wall_time_seconds": doc_latency},
            ]
        )
    return rows





































