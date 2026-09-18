from __future__ import annotations

from importlib.resources import files
from typing import Any

from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts


def _get_docs_context_tool() -> dict[str, Any]:
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

    assert "one call = one concrete question" in description
    assert "original request unchanged" in description
    assert "benchmark/evaluation" in description
    assert "documentation-governance meta-question" in description

    assert "one concrete question" in question_description
    assert "independent questions" in question_description
    assert "separate" in question_description

    assert "same question" in lookup_description
    assert "independent questions" in lookup_description
    assert "never batch" in lookup_description


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
    assert "documentation-governance meta-question" in text


def test_agent_contract_has_explicit_lookup_decomposition_triggers_and_bounds() -> None:
    contract = public_agent_contract()
    lookup = contract["workflow"]["free_form_lookup"]

    assert lookup["recommended_lookup_query_min"] == 1
    assert lookup["recommended_lookup_query_max"] == 3
    assert lookup["simple_single_facet_lookup_required"] is False
    assert set(lookup["decomposition_triggers"]) == {
        "cross_language", "comparison", "conditional", "multiple_dependent_facets",
    }
    assert lookup["original_question_unchanged"] is True
    assert lookup["preserve_exact_technical_anchors"] is True
    assert lookup["preserve_conditions_negation_and_comparison_sides"] is True
    assert lookup["expected_answer_in_lookup_allowed"] is False
    assert lookup["guessed_source_names_in_lookup_allowed"] is False


def test_rendered_agent_contract_teaches_bounded_semantic_decomposition_without_rewrite() -> None:
    from docmancer.cli.commands import _get_template_content

    canonical = files("docmancer.templates").joinpath("agent_contract.md").read_text(
        encoding="utf-8"
    )
    rendered = _get_template_content("agent_contract.md")
    for text in (canonical, rendered):
        lowered = text.casefold()
        assert "1–3" in text or "1-3" in text
        assert "cross-language" in lowered
        assert "comparison" in lowered
        assert "conditional" in lowered
        assert "documentation language" in lowered
        assert "simple single-facet" in lowered
        assert "original question unchanged" in lowered
        assert "exact identifiers" in lowered
        assert "versions" in lowered
        assert "negation" in lowered
        assert "comparison sides" in lowered
        assert "expected answer" in lowered
        assert "guessed source" in lowered


def test_runtime_lookup_schema_teaches_when_to_add_lookups_without_changing_original() -> None:
    tool = _get_docs_context_tool()
    description = str(tool["inputSchema"]["properties"]["lookup_queries"]["description"])
    lowered = description.casefold()

    assert "1–3" in description or "1-3" in description
    assert "cross-language" in lowered
    assert "comparison" in lowered
    assert "conditional" in lowered
    assert "documentation language" in lowered
    assert "simple single-facet" in lowered
    assert "original question" in lowered and "unchanged" in lowered
    assert "exact identifiers" in lowered
    assert "versions" in lowered
    assert "negation" in lowered
    assert "comparison sides" in lowered
    assert "expected answer" in lowered
    assert "guessed source" in lowered

def test_host_gap_policy_preserves_question_and_targets_missing_fact() -> None:
    workflow = public_agent_contract()["workflow"]
    policy = workflow["gap_resolution"]

    assert policy["trigger"] == "concrete_missing_requested_fact"
    assert policy["known_source_first"] == "issued_bounded_source_read"
    assert policy["unknown_source_next"] == "one_targeted_same_need_query"
    assert policy["root_question_immutable"] is True
    assert policy["bridge_values_require_source_reference"] is True
    assert policy["subquestions_preserve_conditions_and_comparison"] is True
    assert policy["stop_when_sufficient_or_no_progress"] is True
    assert policy["first_call_before_split"] == "original_root_question"
    assert policy["split_requires"] == "concrete_missing_requested_part_after_first_packet"
    assert policy["comparison_alone_triggers_split"] is False
    assert workflow["retrieval_only_answer"]["false_or_unverified_flags_require_read"] is False
    assert workflow["retrieval_only_answer"]["authorizes_edit"] is False

def test_agent_surfaces_repeat_gap_directed_follow_up_rule() -> None:
    from pathlib import Path
    from docmancer.mcp._docs_server_resources import MCP_RESOURCES

    skill = Path("SKILL.md").read_text(encoding="utf-8")
    template = files("docmancer.templates").joinpath("agent_contract.md").read_text(encoding="utf-8")
    quickstart = next(
        item["text"] for item in MCP_RESOURCES
        if item["uri"] == "docmancer://agent/quickstart"
    )
    for text in (skill, template, quickstart):
        lowered = text.casefold()
        assert "gap-directed follow-up" in lowered
        assert "root" in lowered and "unchanged" in lowered
        assert "concrete missing requested fact" in lowered
        assert "bounded source read" in lowered
        assert "one targeted" in lowered
        assert "source reference" in lowered
        assert "conditions" in lowered and "comparison" in lowered
        assert "no progress" in lowered
        assert "unverified" in lowered and "does not require" in lowered
        assert "do not pre-split" in lowered
        assert "first packet" in lowered
