from __future__ import annotations

from importlib.resources import files

from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts


def _get_docs_context_tool() -> dict[str, object]:
    return next(
        tool for tool in runtime_public_tool_dicts()
        if tool["name"] == "get_docs_context"
    )


def test_runtime_tool_teaches_one_concrete_question_per_call() -> None:
    tool = _get_docs_context_tool()
    description = str(tool["description"]).casefold()
    properties = tool["inputSchema"]["properties"]
    question_description = str(properties["question"]["description"]).casefold()
    lookup_description = str(properties["lookup_queries"]["description"]).casefold()

    assert "one concrete user question" in description
    assert "independent questions" in description
    assert "separate" in description
    assert "meta" in description

    assert "one concrete user question" in question_description
    assert "separate" in question_description
    assert "meta" in question_description

    assert "same question" in lookup_description
    assert "independent questions" in lookup_description
    assert "not" in lookup_description


def test_agent_contract_forbids_batching_independent_questions_into_lookups() -> None:
    contract = public_agent_contract()
    lookup = contract["workflow"]["free_form_lookup"]

    assert lookup["independent_questions_use_separate_calls"] is True
    assert lookup["lookup_queries_must_refine_same_question"] is True
    assert lookup["meta_request_must_not_replace_concrete_question"] is True

    example = next(
        item for item in contract["examples"]
        if item["id"] == "cross-language-single-question"
    )
    assert example["tool"] == "get_docs_context"
    assert example["arguments"]["question"].startswith("Как ")
    assert len(example["arguments"]["lookup_queries"]) == 2


def test_installed_agent_contract_repeats_question_grouping_rule() -> None:
    text = files("docmancer.templates").joinpath("agent_contract.md").read_text(
        encoding="utf-8"
    ).casefold()

    assert "independent questions" in text
    assert "separate `get_docs_context` calls" in text
    assert "same question" in text
    assert "meta" in text
