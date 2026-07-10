from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_leads_with_one_docs_mcp_journey_before_advanced_surfaces() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    beginner = text.split("## Advanced surfaces", maxsplit=1)[0]

    assert "install → get_docs_context → follow a returned prepare_docs action when needed → answer with sources" in beginner
    assert "MCP Packs" not in beginner
    assert "get_patch_constraints" not in beginner


def test_installer_prints_the_docs_mcp_happy_path() -> None:
    text = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")

    assert "Ask it to call get_docs_context first" in text
    assert "prepare_docs next action" in text
    assert "Answer from the returned sources" in text


def test_three_real_project_task_designs_are_fairness_screened_and_distributed() -> None:
    payload = json.loads((ROOT / "eval" / "task_level" / "product_scope_proof_tasks.json").read_text(encoding="utf-8"))
    tasks = payload["tasks"]
    registered = {
        item["task_id"]: item
        for line in (ROOT / "eval" / "task_level" / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
        for item in [json.loads(line)]
    }

    assert len(tasks) == 3
    for task in tasks:
        assert task["fixture_status"] == "validated"
        assert task["fairness_status"] == "passed"
        assert task["selection_status"] == "rejected_too_easy"
        assert task["benchmark_metric"] == "repeated policy-clean public_and_hidden_test_pass_rate"
        assert len(task["required_context"]) == 4
        assert any(path.endswith("pubspec.lock") for path in task["required_context"])
        assert any(path.endswith("docs") for path in task["required_context"])
        assert any(path.startswith("docs/") or path.endswith("ARCHITECTURE.md") for path in task["required_context"])

        spec = registered[task["task_id"]]
        assert spec["task_type"] == "real"
        assert spec["suite"] == "differentiation"
        assert spec["repo"] == f"fixture://{task['task_id']}"
        assert any(dependency["name"] == "permission_handler" for dependency in spec["dependencies"])
        assert "pubspec.lock" in spec["expected_project_docs"]
        assert "pub.dev" in spec["expected_docs_domains"]

        artifacts = task["artifacts"]
        assert (ROOT / artifacts["template"]).is_dir()
        assert (ROOT / artifacts["hidden_tests"]).is_dir()
        assert (ROOT / artifacts["gold_patch"]).is_file()

        validation = json.loads((ROOT / artifacts["validation"]).read_text(encoding="utf-8"))
        assert validation["task_id"] == task["task_id"]
        assert validation["status"] == "validated"
        assert validation["oracle_isolated"] is True
        assert validation["gold"]["public_tests_passed"] is True
        assert validation["gold"]["hidden_tests_passed"] is True

        fairness = (ROOT / artifacts["fairness_review"]).read_text(encoding="utf-8")
        assert "hidden" in fairness.lower()
        assert "visible" in fairness.lower()
        assert "| no |" not in fairness
        assert (
            "No hidden requirement is oracle-only" in fairness
            or "Fairness clean for strict-offline screening" in fairness
        )
