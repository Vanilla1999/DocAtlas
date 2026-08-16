from __future__ import annotations

from docmancer.docs.domain.project_answer_contract import build_project_answer_contract


def _only(question: str):
    contract = build_project_answer_contract(question)
    assert len(contract.proof_obligations) == 1
    return contract.proof_obligations[0]


def test_inventory_count_names_and_singular_command_are_distinct_contracts():
    count = _only("How many public MCP tools does DocAtlas expose?")
    assert (count.kind, count.response_mode, count.value_kind) == (
        "inventory", "count", "number",
    )

    names = _only("What are the public tools of the Docs MCP server?")
    assert (names.kind, names.response_mode, names.value_kind) == (
        "inventory", "names", "identifier_list",
    )

    command = _only(
        "Which command does doc-atlas use to sync project docs after file changes?"
    )
    assert command.kind == "command"
    assert command.response_mode == "call"
    assert command.expected_value == "sync_project_docs"


def test_three_tool_surface_binds_cardinality_and_names():
    obligation = _only("What is the three-tool public Docs MCP surface?")
    assert obligation.kind == "inventory"
    assert obligation.response_mode == "names"
    assert obligation.cardinality == 3


def test_interrogative_auxiliary_is_not_a_phantom_subject():
    contract = build_project_answer_contract(
        "Does Task 43 require a verified local adapter before the production-model gate can pass?"
    )
    assert "Does Task" not in contract.subjects
    assert [item.subject for item in contract.proof_obligations] == ["Task 43"]


def test_location_and_compound_workflow_have_explicit_typed_contracts():
    location = _only("Where is the DocAtlas execution roadmap?")
    assert (location.kind, location.response_mode, location.value_kind) == (
        "location", "path", "path",
    )
    assert location.subject == "execution roadmap"

    workflow = _only("How does prepare_docs sync_project_docs work?")
    assert workflow.kind == "workflow"
    assert workflow.response_mode == "workflow"
    assert workflow.subject == "prepare_docs"
    assert workflow.target == "sync_project_docs"
