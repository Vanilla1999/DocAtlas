from __future__ import annotations

from eval.task_level.evaluators.actionability import requirements_for_task


TASK_ID = "real_project_nbo_001"


def test_real_project_hidden_requirements_have_visible_sources():
    requirements = requirements_for_task(TASK_ID)

    assert requirements
    assert all(requirement.allowed_for_agent for requirement in requirements)
    assert all(requirement.source_type in {"issue", "project_doc", "code_symbol", "library_doc"} for requirement in requirements)
    assert all(requirement.expected_files for requirement in requirements)
    assert not [requirement for requirement in requirements if requirement.source_type == "hidden_test"]


def test_real_project_fairness_review_has_no_undiscoverable_requirement():
    review = "eval/task_level/results/task_fairness_review/real_project_nbo_001.md"
    text = open(review, encoding="utf-8").read()

    assert "discoverability | decision" in text
    assert "| no |" not in text
    assert "No hidden requirement is oracle-only" in text
