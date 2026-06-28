from __future__ import annotations

from eval.task_level.evaluators.actionability import requirements_for_task


TASK_IDS = (
    "real_project_nbo_001",
    "real_project_nbo_permission_002",
    "real_project_nbo_generated_source_001",
    "real_project_nbo_distributed_permission_policy_001",
)


def test_real_project_hidden_requirements_have_visible_sources():
    requirements = [requirement for task_id in TASK_IDS for requirement in requirements_for_task(task_id)]

    assert requirements
    assert all(requirement.allowed_for_agent for requirement in requirements)
    assert all(requirement.source_type in {"issue", "project_doc", "code_symbol", "library_doc"} for requirement in requirements)
    assert all(requirement.expected_files for requirement in requirements)
    assert not [requirement for requirement in requirements if requirement.source_type == "hidden_test"]


def test_real_project_fairness_review_has_no_undiscoverable_requirement():
    texts = [
        open(f"eval/task_level/results/task_fairness_review/{task_id}.md", encoding="utf-8").read()
        for task_id in TASK_IDS
    ]

    assert all("discoverability | decision" in text for text in texts)
    assert all("| no |" not in text for text in texts)
    assert all("No hidden requirement is oracle-only" in text for text in texts)
