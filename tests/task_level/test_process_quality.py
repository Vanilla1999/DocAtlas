from __future__ import annotations

import json
from pathlib import Path

from eval.task_level.evaluators.process_quality import evaluate_process_quality


def test_process_quality_observes_repairs_without_inventing_first_edit_correctness(tmp_path: Path):
    trajectory = tmp_path / "trajectory.normalized.json"
    trajectory.write_text(json.dumps([
        {"tool_name": "Edit", "arguments": {"changes": [{"path": "a.dart"}]}},
        {"tool_name": "Edit", "arguments": {"changes": [{"path": "b.dart"}]}},
        {
            "tool_name": "Bash",
            "arguments": {"command": "pytest -q"},
            "exit_code": 1,
            "execution_status": "failed",
        },
        {"tool_name": "Edit", "arguments": {"changes": [{"path": "a.dart"}]}},
        {
            "tool_name": "Bash",
            "arguments": {"command": "pytest -q"},
            "exit_code": 0,
            "execution_status": "completed",
        },
        {
            "tool_name": "Bash",
            "arguments": {"command": "pytest tests/other -q"},
            "exit_code": 1,
            "execution_status": "failed",
        },
        {
            "tool_name": "Bash",
            "arguments": {"command": "rg -n PermissionService lib tests"},
            "exit_code": 0,
            "execution_status": "completed",
        },
    ]), encoding="utf-8")
    result = {
        "resolved": False,
        "public_tests_passed": True,
        "hidden_tests_passed": False,
        "compile_success": True,
        "forbidden_changes": [],
        "metrics": {
            "required_evidence_found": 3,
            "required_evidence_total": 4,
            "uncached_input_tokens": 1_000,
            "output_tokens": 100,
        },
    }

    quality = evaluate_process_quality(result, trajectory_path=trajectory)

    assert quality["first_edit_correctness"] is None
    assert quality["first_edit_correctness_status"] == "not_observed:no_validation_before_next_edit"
    assert quality["repair_count"] == 1
    assert quality["regression_count"] == 1
    assert quality["validation_breadth"]["test_runs_observed"] == 3
    assert quality["validation_breadth"]["distinct_test_commands"] == 2
    assert quality["search_efficiency"]["required_evidence_recall"] == 0.75
    assert quality["search_efficiency"]["exploration_calls"] == 1
    assert quality["provider_efficiency"]["correct_runs_per_100k_uncached_tokens"] == 0.0
    assert quality["patch_robustness"]["robust"] is False
