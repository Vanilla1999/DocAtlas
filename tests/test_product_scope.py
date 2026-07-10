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

    assert len(tasks) == 3
    for task in tasks:
        assert task["fairness"] == {"reviewed": True, "clean": True, "hidden_oracle_only": False}
        assert set(task["visible_requirement_sources"]) == {"issue", "project_doc", "lockfile", "library_doc"}
        assert task["benchmark_metric"] == "repeated policy-clean public_and_hidden_test_pass_rate"
        assert len(task["required_context"]) == 4
