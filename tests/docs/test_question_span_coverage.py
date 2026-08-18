from __future__ import annotations

import pytest

from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.domain.question_frame_core import split_question_clause_spans
from docmancer.docs.domain.question_ownership import frozen_ownership_mismatches
from docmancer.docs.domain.question_plan import compile_question_plan


_ADVERSARIAL_TAILS = (
    ", what is the Bitcoin price?",
    ": what is the Bitcoin price?",
    " — what is the Bitcoin price?",
    " / what is the Bitcoin price?",
    " and also what is the Bitcoin price?",
    " while also telling me the Bitcoin price?",
    " plus also tell me the Bitcoin price?",
    " besides that, what is the Bitcoin price?",
    " by the way, what is the Bitcoin price?",
    " another thing: what is the Bitcoin price?",
    " one more question: what is the Bitcoin price?",
    ", Bitcoin price",
    " Bitcoin price",
    "; calculate 2+2",
    ". Tell me the Bitcoin price.",
    "\nWhat is the Bitcoin price?",
)


@pytest.mark.parametrize(
    "prefix",
    (
        "Which source types are supported for indexing",
        "Which command syncs project docs after file changes",
        "Which command starts the Docs MCP server",
        "How do I run the offline test suite for DocAtlas",
        "How do I run the project answer quality v4 protocol",
        "How does the two-cell smoke procedure verify provider-call cardinality",
        "Which docs files must stay under the 1000-line release limit",
        "What is the storage mutation coordination contract for cleanup and refresh",
        "What happens if remove_library_docs runs while a library refresh is in flight",
        "What is the release checklist and what gates block release",
        "What is the model-visible projection and how is the answer token-bounded",
        "What does clear-index do when a live process holds the index",
        "How do I configure a project in docmancer.yaml",
        "How does evidence selection choose which candidates are selected",
        "What is contamination protection in the eval protocols",
        "What is the two-cell smoke procedure for local Task 33 benchmarks",
        "What does the two-cell smoke procedure require",
        "How do I sync project docs after changing a file",
    ),
)
@pytest.mark.parametrize("tail", _ADVERSARIAL_TAILS)
def test_known_frame_never_authorizes_an_unknown_tail(prefix: str, tail: str) -> None:
    question = prefix + tail
    plan = compile_question_plan(question)

    assert plan.handled
    assert plan.unresolved_parts, (question, plan)
    assert any(
        row.startswith("unresolved_question_clause:")
        for row in plan.unresolved_parts
    )

    contract = build_project_answer_contract(question)
    assert contract.unresolved_parts


@pytest.mark.parametrize(
    "question",
    (
        "Which source types are supported for indexing, what is the Bitcoin price?",
        "Which command syncs project docs after file changes — calculate 2+2",
        "How do I run the offline suite Bitcoin price?",
    ),
)
def test_unresolved_residue_reaches_the_requirements_gate(question: str) -> None:
    requirements = build_requirements(question, profile="project_docs_answer")
    assert any(row.kind == "unsupported_query" for row in requirements)


def test_plan_retains_exact_source_spans_after_wrapper_and_whitespace_normalization() -> None:
    question = "Please,   Which source   types are supported for indexing?"
    plan = compile_question_plan(question)

    assert not plan.unresolved_parts
    assert plan.consumed_spans == ((0, len(question)),)
    assert len(plan.facets) == 1
    facet = plan.facets[0]
    assert facet.query_span_start is not None
    assert facet.query_span_end is not None
    assert question[facet.query_span_start:facet.query_span_end] == (
        "Which source   types are supported for indexing?"
    )

    contract = build_project_answer_contract(question)
    obligation = contract.proof_obligations[0]
    assert (
        obligation.query_span_start,
        obligation.query_span_end,
        obligation.query_span_text,
    ) == (
        facet.query_span_start,
        facet.query_span_end,
        question[facet.query_span_start:facet.query_span_end],
    )


def test_clause_scanner_preserves_original_offsets_and_noun_coordination() -> None:
    question = (
        "How does indexing split documents into sections and chunks? "
        "What is contamination protection in the eval protocols?"
    )
    clauses = split_question_clause_spans(question)

    assert tuple(question[row.start:row.end] for row in clauses) == tuple(
        row.text for row in clauses
    )
    assert [row.text for row in clauses] == [
        "How does indexing split documents into sections and chunks",
        "What is contamination protection in the eval protocols?",
    ]


def test_existing_compounds_and_paraphrases_remain_supported() -> None:
    questions_and_counts = (
        ("What are the three public Docs MCP tools and when do I use each one?", 3),
        ("What test markers are available and how do I run the offline suite?", 2),
        ("How does indexing split documents into sections and chunks?", 1),
        ("What is the storage mutation coordination contract for cleanup and refresh?", 1),
        ("How should I refresh project documentation after editing a file?", 1),
        ("Как синхронизировать документацию проекта после изменения файла?", 1),
        ("Could you please tell me which source types are supported for indexing?", 1),
        (
            "Which source types are supported for indexing; "
            "Which file formats are supported for indexing?",
            2,
        ),
        (
            "Please, what test markers are available and how do I run the offline suite?",
            2,
        ),
    )
    for question, count in questions_and_counts:
        plan = compile_question_plan(question)
        assert not plan.unresolved_parts, (question, plan.unresolved_parts)
        assert len(plan.facets) == count, question
        assert plan.consumed_spans, question


def test_russian_ambiguous_inventory_and_action_frames_fail_closed() -> None:
    cases = (
        ("Какие маркеры доступны?", "unresolved_inventory_category:markers"),
        ("Перечисли форматы.", "unresolved_inventory_category:formats"),
        ("Как обновить индекс документации?", "unresolved_requested_operation"),
    )
    for question, reason in cases:
        plan = compile_question_plan(question)
        assert not plan.facets
        assert reason in plan.unresolved_parts


@pytest.mark.parametrize(
    "question",
    (
        "How does prepare_docs sync_project_docs work?",
        "What are the three public Docs MCP tools?",
        (
            "What does Phase 3.1 require for RetrievalDispatcher, the raw topic, "
            "EvidenceRequirementSet hints, and vector or embedding calls?"
        ),
        "What does docs_status report and when should it be used?",
    ),
)
def test_legacy_fallback_questions_remain_unclaimed_by_question_plan(question: str) -> None:
    plan = compile_question_plan(question)
    assert not plan.handled, (question, plan)
    assert not frozen_ownership_mismatches()

