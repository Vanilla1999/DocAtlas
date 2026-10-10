from __future__ import annotations

import hashlib

import pytest

from eval.task_level.literal_contract_reduction import unknown_tail_pairs

from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.answer_units import AnswerUnit, local_proof_for_obligation
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.domain.project_answer_contract import (
    ProofObligation,
    build_project_answer_contract,
    can_authorize_docs_answer,
)
from docmancer.docs.domain.question_frame_core import split_question_clause_spans
from docmancer.docs.domain.question_ownership import (
    FROZEN_OWNERSHIP_CASES, classify_question_ownership,
)
from docmancer.docs.domain.question_plan import compile_question_plan
from docmancer.docs.domain.question_retrieval_needs import retrieval_needs


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

_KNOWN_PREFIXES = (
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
)
_TAIL_PAIRS = unknown_tail_pairs(_KNOWN_PREFIXES, _ADVERSARIAL_TAILS)


def _unit(text: str) -> AnswerUnit:
    return AnswerUnit(
        unit_id="premise-proof-test",
        kind="sentence",
        text=text,
        char_start=0,
        char_end=len(text),
        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        proposition=True,
    )


def _assert_literal_context_boundary(question: str) -> None:
    """Untyped text stays retrievable without supplying semantic authority."""
    plan = compile_question_plan(question)
    assert plan.clauses == (question,), "literal_original_question"
    assert plan.unresolved_parts == ("unresolved_question_semantics",), "literal_unresolved_semantics"
    assert not plan.facets, "literal_no_inferred_facets"
    assert not plan.consumed_spans
    assert plan.component_scope_complete is False

    needs = retrieval_needs(question)
    assert len(needs) == 1
    need = needs[0]
    assert (need.query_span_start, need.query_span_end, need.query_span_text) == (
        0, len(question), question,
    )
    assert need.subject == ""
    assert need.relation == "unresolved"
    assert need.context == ""

    contract = build_project_answer_contract(question)
    assert not contract.proof_obligations, "critical_question_contract_no_inferred_obligations"
    assert not contract.subjects
    assert not contract.retrieval_hints
    assert not contract.concept_queries
    assert contract.component_scope_complete is False
    assert can_authorize_docs_answer(contract) is False, "literal_no_answer_authority"


def test_governance_question_models_scope_and_every_including_facet() -> None:
    question = (
        "What project rules govern the shared browser and scan Android permission "
        "preflight on Android 13+, including policy ownership, notification "
        "permission, deferred background location, and the pinned "
        "permission_handler version?"
    )

    # The original governance request must survive in full. Its phrasing does
    # not authorize inferred facets, expected answers or policy instructions.
    _assert_literal_context_boundary(question)
    query, = build_documentation_query_plan(question).queries
    assert query.text == question
    assert query.query_id == "query-original" and query.coverage_required


def test_governance_question_supports_bounded_russian_surface() -> None:
    question = (
        "Какие проектные правила определяют общий preflight разрешений, включая "
        "владение политикой, разрешение уведомлений и отложенную геолокацию?"
    )

    _assert_literal_context_boundary(question)
    query, = build_documentation_query_plan(question).queries
    assert query.text == question
    assert query.query_id == "query-original" and query.coverage_required


def test_governance_question_rejects_nested_request_tail() -> None:
    question = (
        "What project rules govern permission preflight, including ownership, "
        "notification permission, and what is the Bitcoin price?"
    )

    plan = compile_question_plan(question)

    assert plan.unresolved_parts


@pytest.mark.parametrize("prefix,tail", _TAIL_PAIRS, ids=[f"{tail}-{prefix}" for prefix, tail in _TAIL_PAIRS])
def test_known_frame_never_authorizes_an_unknown_tail(prefix: str, tail: str) -> None:
    question = prefix + tail
    plan = compile_question_plan(question)

    assert plan.handled
    assert plan.unresolved_parts, (question, plan)
    _assert_literal_context_boundary(question)

    contract = build_project_answer_contract(question)
    assert contract.question_hash != build_project_answer_contract(prefix).question_hash, "literal_unknown_tail_identity"

    # A real, explicit host lookup may retrieve the prefix. It cannot replace
    # the original request or claim coverage of its unknown tail.
    queries = build_documentation_query_plan(question, lookup_queries=(prefix,))
    assert queries.original_question == question
    assert [row.text for row in queries.queries] == [question, prefix], "literal_explicit_lookup_text"
    original, lookup = queries.queries
    assert (original.query_id, original.origin, original.coverage_required) == (
        "query-original", "original", True,
    ), "literal_original_coverage_preserved"
    assert (lookup.origin, lookup.relation, lookup.coverage_required) == (
        "host_lookup", "host_lookup", False,
    ), "literal_lookup_no_coverage_credit"
    assert all(row.public_parent_query_id is None for row in queries.queries), "literal_lookup_no_parent_credit"
    assert not queries.component_contract
    assert queries.component_scope_complete is False


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
    _assert_literal_context_boundary(question)
    assert requirements.component_scope_complete is False
    assert not requirements.required_entities
    assert not requirements.required_facets
    assert not requirements.retrieval_hints
    assert not requirements.concept_queries
    assert all(row.kind == "exact_term" and not row.mandatory for row in requirements)

    # The conservative question boundary still carries explicit requirements;
    # it must not make this negative pass by discarding every request.
    explicit = build_requirements(
        question,
        profile="project_docs_answer",
        required_evidence_paths=("docs/fixture-evidence.md",),
    )
    paths = [row for row in explicit if row.kind == "evidence_path"]
    assert len(paths) == 1
    assert (paths[0].value, paths[0].source_path, paths[0].public_provenance) == (
        "docs/fixture-evidence.md", "docs/fixture-evidence.md", "required_evidence_paths",
    )
    assert paths[0].mandatory is True
    assert explicit.component_scope_complete is False
    with pytest.raises(ValueError, match="unsupported evidence requirement provenance"):
        build_requirements(question, public_requirements=({
            "value": "fixture fact", "public_provenance": "inferred_question_semantics",
        },))

def test_legacy_behavior_usage_fallback_rejects_extra_compound_tail() -> None:
    question = (
        "What does docs_status report and when should it be used, and tell me the Bitcoin price?"
    )
    _assert_literal_context_boundary(question)


def test_plan_retains_exact_source_spans_after_wrapper_and_whitespace_normalization() -> None:
    question = "Please,   Which source   types are supported for indexing?"
    _assert_literal_context_boundary(question)
    queries = build_documentation_query_plan(question)
    assert [row.text for row in queries.queries] == [question]
    assert queries.original_question == question
    # Wrappers and whitespace are literal input, not permission to rewrite it.
    normalized = "Which source types are supported for indexing?"
    assert build_project_answer_contract(question).question_hash != (
        build_project_answer_contract(normalized).question_hash
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
    assert [row.text for row in clauses] == [question], "literal_paragraphs_only"

    # Blank paragraphs are structural boundaries. Sentence punctuation and
    # noun coordination alone do not establish independent semantic requests.
    first = "How does indexing split documents into sections and chunks?"
    second = "What is contamination protection in the eval protocols?"
    paragraphs = first + "\n\n" + second
    split = split_question_clause_spans(paragraphs)
    assert [row.text for row in split] == [first, second]
    assert [(row.start, row.end) for row in split] == [
        (0, len(first)), (len(first) + 2, len(paragraphs)),
    ]
    assert all(paragraphs[row.start:row.end] == row.text for row in split)


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
    for question, retired_facet_count in questions_and_counts:
        # Retain the historical inputs; the former facet count is not a
        # current promise that prose establishes an answer contract.
        _assert_literal_context_boundary(question)
        query, = build_documentation_query_plan(question).queries
        assert query.text == question and query.coverage_required

    # Preserve all historical ownership inputs once, rather than re-running
    # their retired semantic signatures in each fallback parametrization.
    for historical in FROZEN_OWNERSHIP_CASES:
        _assert_literal_context_boundary(historical.question)
        ownership = classify_question_ownership(historical.question)
        assert ownership.owner == "unsupported" and ownership.signature == ()
        assert ownership.unresolved_parts == ("unresolved_question_semantics",)

    premise_question = "Why does clear-index always delete remote Qdrant collections?"
    _assert_literal_context_boundary(premise_question)
    # Explicit legacy DTOs remain constructible, but a local prose matcher is
    # not an independent entailment oracle, even for a caller-supplied premise.
    premise = ProofObligation(
        "historical-premise", "relation", "clear-index",
        relation="premise_check", target="delete remote Qdrant collections",
        expected_value="always",
    )
    assert premise.expected_value == "always"
    assert local_proof_for_obligation(
        premise,
        _unit("`clear-index` never deletes remote Qdrant collections; remote collections are preserved."),
    ).valid is False
    assert local_proof_for_obligation(
        premise,
        _unit("`clear-index` always deletes remote Qdrant collections."),
    ).valid is False
    assert local_proof_for_obligation(
        premise,
        _unit("`clear-index` always deletes remote Qdrant collections because the remote store is explicitly configured for purge."),
    ).valid is False
    assert local_proof_for_obligation(
        premise,
        _unit("`clear-index` deletes remote Qdrant collections only when --force is set."),
    ).valid is False
    assert local_proof_for_obligation(
        premise,
        _unit("`clear-index` never deletes local cache entries."),
    ).valid is False

    russian_question = "Почему clear-index всегда удаляет remote Qdrant collections?"
    _assert_literal_context_boundary(russian_question)
    russian_premise = premise
    assert russian_premise.expected_value == "always"
    assert local_proof_for_obligation(
        russian_premise,
        _unit("`clear-index` never deletes remote Qdrant collections."),
    ).valid is False

    cardinality_question = "Why are there four public Docs MCP tools?"
    _assert_literal_context_boundary(cardinality_question)
    cardinality = ProofObligation(
        "historical-cardinality", "relation", "Docs MCP",
        relation="premise_check", expected_value="four",
    )
    assert cardinality.expected_value == "four"
    assert local_proof_for_obligation(
        cardinality,
        _unit("Docs MCP exposes exactly three public tools: get_docs_context, prepare_docs, and docs_status."),
    ).valid is False
    assert local_proof_for_obligation(
        cardinality,
        _unit("Docs MCP exposes exactly four public tools."),
    ).valid is False
    assert local_proof_for_obligation(
        cardinality,
        _unit("Docs MCP exposes exactly four public tools because the fourth tool is a dedicated audit surface."),
    ).valid is False
    _assert_literal_context_boundary("Why are there four storage layers?")


def test_russian_ambiguous_inventory_and_action_frames_fail_closed() -> None:
    cases = (
        ("Какие маркеры доступны?", "unresolved_inventory_category:markers"),
        ("Перечисли форматы.", "unresolved_inventory_category:formats"),
        ("Как обновить индекс документации?", "unresolved_requested_operation"),
    )
    for question, former_semantic_reason in cases:
        plan = compile_question_plan(question)
        assert not plan.facets
        _assert_literal_context_boundary(question)
        assert former_semantic_reason not in plan.unresolved_parts


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
    _assert_literal_context_boundary(question)
    ownership = classify_question_ownership(question)
    assert ownership.owner == "unsupported"
    assert ownership.signature == ()
    assert ownership.unresolved_parts == ("unresolved_question_semantics",)
    # The frozen legacy signature table describes the retired NL compiler;
    # current ownership must not manufacture those historical obligations.
