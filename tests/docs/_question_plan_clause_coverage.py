"""Private clause-coverage test shard collected through test_question_plan_v4."""
from __future__ import annotations

from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.project_answer_contract import (
    PROJECT_ANSWER_CONTRACT_SCHEMA_V4,
    build_project_answer_contract,
)


def test_full_question_coverage_rejects_unknown_tails_across_boundary_forms():
    questions = (
        "Which command syncs project docs after file changes; what is the Bitcoin price?",
        "Which command syncs project docs after file changes. What is the Bitcoin price?",
        "Which command syncs project docs after file changes? What is the Bitcoin price?",
        "Which command syncs project docs after file changes plus tell me the Bitcoin price?",
        "Which command syncs project docs after file changes then calculate 2+2.",
        "Which command syncs project docs after file changes as well as tell me the Bitcoin price?",
        "Which command syncs project docs after file changes along with tell me the Bitcoin price?",
        "How do I sync project docs after changing a file and rebuild vectors?",
    )
    for question in questions:
        contract = build_project_answer_contract(question)
        assert contract.schema_version == PROJECT_ANSWER_CONTRACT_SCHEMA_V4
        assert contract.unresolved_parts, question
        assert any(
            row.startswith("unresolved_question_clause:")
            for row in contract.unresolved_parts
        ), (question, contract.unresolved_parts)
        requirements = build_requirements(question, profile="project_docs_answer")
        assert any(row.kind == "unsupported_query" for row in requirements), question



def test_existing_compounds_and_noun_coordination_survive_stricter_clause_coverage():
    public_tools = build_project_answer_contract(
        "What are the three public Docs MCP tools and when do I use each one?"
    )
    assert not public_tools.unresolved_parts
    assert len(public_tools.proof_obligations) == 3

    markers = build_project_answer_contract(
        "What test markers are available and how do I run the offline suite?"
    )
    assert not markers.unresolved_parts
    assert len(markers.proof_obligations) == 2

    chunking = build_project_answer_contract(
        "How does indexing split documents into sections and chunks?"
    )
    assert not chunking.unresolved_parts
    assert [(row.subject, row.relation) for row in chunking.proof_obligations] == [
        ("indexing", "chunking")
    ]

    storage = build_project_answer_contract(
        "What is the storage mutation coordination contract for cleanup and refresh?"
    )
    assert not storage.unresolved_parts
    assert len(storage.proof_obligations) == 1
