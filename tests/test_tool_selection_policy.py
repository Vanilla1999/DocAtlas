from __future__ import annotations

from eval.tool_selection_benchmark import evaluate, load_cases
from docmancer.docs.domain.tool_selection import (
    PUBLIC_DOCS_TOOLS,
    select_public_docs_tool,
)


def test_tool_selection_golden_has_balanced_core_and_adversarial_cases():
    cases = load_cases()

    assert len(cases) == 132
    counts = {
        tool: sum(case["expected_tool"] == tool for case in cases)
        for tool in PUBLIC_DOCS_TOOLS
    }
    assert counts == {
        "get_docs_context": 66,
        "prepare_docs": 33,
        "docs_status": 33,
    }


def test_tool_selection_golden_meets_target():
    report = evaluate(load_cases())

    assert report["accuracy"] >= 0.95, report["failures"]


def test_returned_prepare_next_action_has_priority():
    decision = select_public_docs_tool(
        "How does authentication work?",
        next_action_tool="prepare_docs",
    )

    assert decision.tool == "prepare_docs"
    assert decision.reason_code == "returned_next_action"


def test_natural_docs_question_defaults_to_context():
    assert select_public_docs_tool(
        "Обновлялся ли API авторизации в последней версии?"
    ).tool == "get_docs_context"


def test_adversarial_question_wording_does_not_trigger_mutation_or_status():
    prompts = [
        "How do I remove docs from a Python list?",
        "Explain how to refresh docs in CI.",
        "Show how docs status works in an MCP client.",
        "Почему документация устарела после релиза?",
    ]

    assert {select_public_docs_tool(prompt).tool for prompt in prompts} == {"get_docs_context"}
