from __future__ import annotations

import json

from eval.task_level.execution import count_jsonl_records, write_run_progress


def test_artifact_integrity_records_network_and_docatlas_fields(tmp_path):
    results = [{
        "task_id": "real_project_nbo_001",
        "condition_id": "repo_only_web_audited",
        "repeat": 0,
        "status": "completed",
        "resolved": False,
        "public_tests_passed": True,
        "hidden_tests_passed": True,
        "policy_clean": True,
        "policy": {"network_attempts": 1},
        "docatlas": {"agent_calls": 0, "context_used": False, "fallback_used": False},
        "actionability": {"checklist_items": [], "action_checklist_used": False},
    }]

    write_run_progress(tmp_path, results, total_runs=1, current=None, finished=True)
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))

    assert status["artifact_integrity"]["ok"] is True
    assert count_jsonl_records(tmp_path / "runs.jsonl") == 1
