from __future__ import annotations

import json
from pathlib import Path


DESIGN = Path("eval/task_level/results/task_selection/nbo_hard_task_design.md")
SUMMARY = Path("eval/task_level/results/task_selection/summary.json")

EXPECTED_CANDIDATES = {
    "real_project_nbo_distributed_permission_policy_001",
    "real_project_nbo_generated_policy_source_001",
    "real_project_nbo_permission_handler_version_001",
    "real_project_nbo_cross_module_permission_contract_001",
}


def test_hard_task_design_exists_and_defines_candidates():
    text = DESIGN.read_text(encoding="utf-8")

    for task_id in EXPECTED_CANDIDATES:
        assert task_id in text


def test_hard_task_candidates_have_docatlas_relevance():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    by_id = {candidate["task_id"]: candidate for candidate in summary}

    assert EXPECTED_CANDIDATES <= set(by_id)
    for task_id in EXPECTED_CANDIDATES:
        relevance = set(by_id[task_id]["docatlas_relevance"])
        assert relevance & {"project_docs", "pinned_dependency", "architecture_constraint", "generated_file_constraint", "private_local_context"}


def test_hard_task_candidates_define_tempting_wrong_locations():
    text = DESIGN.read_text(encoding="utf-8")

    assert text.count("Tempting wrong locations:") >= 4
    assert "provider/UI layer patch" in text
    assert "*.freezed.dart" in text
    assert "latest `permission_handler` API" in text
    assert "fix only one flow" in text


def test_no_hidden_oracle_only_requirements_for_implemented_candidates():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    implemented = [candidate for candidate in summary if candidate["candidate_status"] in {"implemented", "accepted"}]

    for candidate in implemented:
        assert candidate["fairness"]["reviewed"] is True
        assert candidate["fairness"]["clean"] is True
        assert candidate["fairness"]["hidden_oracle_only"] is False
