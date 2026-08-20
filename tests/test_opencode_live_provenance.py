from __future__ import annotations

import json
from pathlib import Path

from scripts.run_agent_developer_opencode_chat import (
    _load_reusable_results,
    benchmark_contract_sha256,
)


ROOT = Path(__file__).resolve().parents[1]
AGENT_REPORT = ROOT / "eval" / "agent_developer_v1" / "results" / "model-benchmark.json"


def test_committed_opencode_agent_report_matches_current_benchmark_contract() -> None:
    report = json.loads(AGENT_REPORT.read_text(encoding="utf-8"))
    if report.get("provider_id") != "opencode-chat":
        return

    expected = benchmark_contract_sha256()
    usage_rows = [
        row
        for task in report.get("tasks") or []
        for row in task.get("usage") or []
    ]
    assert usage_rows
    assert all(
        row.get("benchmark_contract_sha256") == expected
        for row in usage_rows
    )


def test_resume_rejects_results_without_exact_contract_fingerprint(tmp_path: Path) -> None:
    task_id = "module_definition_supported"
    output = tmp_path / "model-benchmark.json"
    base_result = {
        "task_id": task_id,
        "passed": False,
        "score": {"passed": False},
        "trajectory": [],
        "usage": [{"request_id": "session"}],
    }
    report = {
        "provider_id": "opencode-chat",
        "model": "gpt-5.6-luna",
        "protocol": "agent-developer-model-v1",
        "tasks": [base_result],
    }
    output.write_text(json.dumps(report), encoding="utf-8")

    assert _load_reusable_results(output, selected_ids={task_id}) == []

    base_result["usage"][0]["benchmark_contract_sha256"] = benchmark_contract_sha256()
    output.write_text(json.dumps(report), encoding="utf-8")
    reusable = _load_reusable_results(output, selected_ids={task_id})
    assert [row["task_id"] for row in reusable] == [task_id]
