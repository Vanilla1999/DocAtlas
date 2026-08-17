from __future__ import annotations

from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.docs.domain.answer_units import AnswerUnit, local_proof_for_obligation
from docmancer.docs.domain.project_answer_contract import (
    PROJECT_ANSWER_CONTRACT_SCHEMA_V4,
    build_project_answer_contract,
)
from docmancer.docs.domain.technical_terms import coerce_technical_term, technical_term_present


def _rows(question: str):
    contract = build_project_answer_contract(question)
    assert contract.schema_version == PROJECT_ANSWER_CONTRACT_SCHEMA_V4
    return contract, contract.proof_obligations


def _unit(text: str) -> AnswerUnit:
    import hashlib
    return AnswerUnit(
        unit_id="unit-test",
        kind="sentence",
        text=text,
        char_start=0,
        char_end=len(text),
        content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        proposition=True,
    )


def test_question_plan_compiles_previously_unrepresentable_queries_without_generic_subjects():
    cases = {
        "Which command syncs project docs after file changes?": [("command", "sync_project_docs", "invocation")],
        "Which command starts the Docs MCP server?": [("command", "docs-serve", "invocation")],
        "Which docs files must stay under the 1000-line release limit?": [("relation", "canonical user-facing release set", "release_line_limit")],
        "What source types are supported for indexing?": [("inventory", "source types", None)],
        "How do I configure a project in docmancer.yaml?": [("workflow", "docmancer.yaml", "configuration")],
        "How do I run the offline test suite for DocAtlas?": [("workflow", "offline suite", "procedure")],
        "How do I run the project answer quality v4 protocol?": [("workflow", "project answer quality v4 protocol", "protocol_run")],
        "How does the two-cell smoke procedure verify provider-call cardinality?": [("relation", "two-cell smoke procedure", "verification")],
        "What is the storage mutation coordination contract for cleanup and refresh?": [("relation", "storage mutation coordination", "storage_coordination")],
        "What happens if remove_library_docs runs while a library refresh is in flight?": [("relation", "remove_library_docs", "conditional_library_removal")],
        "How does evidence selection choose which candidates are selected?": [("behavior", "evidence selection", "selection_policy")],
        "How does indexing split documents into sections and chunks?": [("behavior", "indexing", "chunking")],
        "What does clear-index do when a live process holds the index?": [("relation", "clear-index", "conditional_behavior")],
    }
    for question, expected in cases.items():
        contract, rows = _rows(question)
        assert [(r.kind, r.subject, r.relation) for r in rows] == expected
        assert all(r.subject not in {"project", "request", "workflow", "requested operation", "the"} for r in rows)
        assert contract.parse_trace
        assert not contract.unresolved_parts


def test_question_plan_splits_compound_questions_into_mandatory_facets():
    contract, rows = _rows("What is the release checklist and what gates block release?")
    assert [(r.kind, r.subject, r.relation) for r in rows] == [
        ("purpose", "release checklist", "purpose"),
        ("relation", "release", "blocking_gates"),
    ]
    assert all(r.mandatory for r in rows)
    assert len(contract.clauses) if hasattr(contract, "clauses") else True

    _contract, rows = _rows("What is the model-visible projection and how is the answer token-bounded?")
    assert [(r.kind, r.subject, r.relation) for r in rows] == [
        ("definition", "model-visible projection", None),
        ("relation", "model-visible projection", "token_bounding"),
    ]

    _contract, rows = _rows("What are the three public Docs MCP tools and when do I use each one?")
    assert [(r.kind, r.relation) for r in rows] == [
        ("inventory", None),
        ("relation", "per_tool_usage"),
    ]


def test_legacy_synthetic_fallback_fails_closed_and_is_diagnostic():
    # Deliberately vague behavior: the legacy builder used to invent subject=project.
    contract = build_project_answer_contract("How does the project work?")
    assert contract.schema_version == PROJECT_ANSWER_CONTRACT_SCHEMA_V4
    assert not contract.proof_obligations
    assert contract.unresolved_parts == ("unresolved_query_subject",)

    requirements = build_requirements("How does the project work?", profile="project_docs_answer")
    assert requirements.unresolved_parts == ("unresolved_query_subject",)
    assert any(row.kind == "unsupported_query" for row in requirements)


def test_question_plan_proof_requires_local_subject_binding():
    _contract, rows = _rows("How does evidence selection choose which candidates are selected?")
    obligation = rows[0]
    unrelated = _unit("The project returns a compact context for callers.")
    proof = local_proof_for_obligation(
        obligation,
        unrelated,
        source={"authority": "source_of_truth", "path": "ARCHITECTURE.md"},
    )
    assert proof.valid is False


def test_conditional_behavior_requires_requested_condition_and_blocking_effect():
    _contract, rows = _rows("What does clear-index do when a live process holds the index?")
    obligation = rows[0]
    correct = _unit("`clear-index` treats a live MCP process PID as a hard blocker and refuses cleanup.")
    wrong = _unit("`clear-index` resolves docmancer.yaml before cleanup.")
    assert local_proof_for_obligation(obligation, correct).valid is True
    assert local_proof_for_obligation(obligation, wrong).valid is False


def test_code_symbol_aliases_may_widen_retrieval_but_not_proof_shape():
    symbol = coerce_technical_term("foo_bar", "code_symbol")
    assert technical_term_present(symbol, "The foo bar feature is enabled.", require_kind_shape=True) is False
    assert technical_term_present(symbol, "The `foo_bar` symbol is enabled.", require_kind_shape=True) is True


def test_selection_policy_and_chunking_require_complete_local_semantics():
    _contract, rows = _rows("How does evidence selection choose which candidates are selected?")
    selection = rows[0]
    exact = _unit("Evidence selection chooses candidates by requiring locally bound subject, relation, and value proof; complete exact proof outranks generic text.")
    distractor = _unit("The project selects a configuration candidate for each module.")
    assert local_proof_for_obligation(selection, exact).valid is True
    assert local_proof_for_obligation(selection, distractor).valid is False

    _contract, rows = _rows("How does indexing split documents into sections and chunks?")
    chunking = rows[0]
    exact = _unit("Markdown indexing groups text into heading-scoped parent sections, then splits each parent section into token-bounded child chunks.")
    old_changelog = _unit("Indexing and retrieval use SQLite FTS5 over heading-normalized sections instead of Qdrant.")
    assert local_proof_for_obligation(chunking, exact).valid is True
    assert local_proof_for_obligation(chunking, old_changelog).valid is False


def test_code_block_units_preserve_exact_source_spans_for_projection():
    from docmancer.docs.domain.answer_units import extract_answer_units, materialize_answer_units

    source = "   ```bash\n   python -m example \\n     --flag\n   ```\n\n"
    units = extract_answer_units(source)
    block = next(unit for unit in units if unit.kind == "code_block")
    assert source[block.char_start:block.char_end] == block.text
    assert materialize_answer_units(source, (block,)) == block.text


def test_named_multistep_procedure_summary_outranks_single_command_shape():
    _contract, rows = _rows("What is the two-cell smoke procedure for local Task 33 benchmarks?")
    obligation = rows[0]
    summary = _unit(
        "The two-cell smoke procedure is: run a provider-free preflight, run one canary and exactly two cells, "
        "do not retry failures, audit the event streams, then verify the harness before comparing metrics."
    )
    command = _unit("python -m eval.task_level.task33_codex_exploratory --two-cell-smoke")
    summary_proof = local_proof_for_obligation(obligation, summary)
    command_proof = local_proof_for_obligation(
        obligation, command, source={"authority": "source_of_truth", "title": "Local two-cell smoke procedure"}
    )
    assert summary_proof.valid is True
    assert command_proof.valid is True
    assert summary_proof.completeness_score > command_proof.completeness_score


def test_new_probing_paraphrases_have_locally_provable_units():
    _contract, rows = _rows("Which command starts the Docs MCP server?")
    assert local_proof_for_obligation(
        rows[0], _unit("Start the local stdio server with `doc-atlas mcp docs-serve`.")
    ).valid is True

    _contract, rows = _rows("How do I run the offline test suite for DocAtlas?")
    assert local_proof_for_obligation(
        rows[0],
        _unit(
            'Run the fail-closed offline suite with `DOCMANCER_OFFLINE=1 pytest tests/ '
            '-m "not advanced and not live and not live_network"`.'
        ),
        source={"title": "Test tiers and markers", "path": "docs/testing.md"},
    ).valid is True

    _contract, rows = _rows(
        "How does the two-cell smoke procedure verify provider-call cardinality?"
    )
    assert local_proof_for_obligation(
        rows[0],
        _unit(
            "The two-cell smoke procedure audits exactly three provider event streams "
            "before reporting metrics and then verifies the harness."
        ),
    ).valid is True

    _contract, rows = _rows(
        "Which docs files must stay under the 1000-line release limit?"
    )
    assert local_proof_for_obligation(
        rows[0],
        _unit(
            "The canonical user-facing release set (`README.md`, product brief, Docs MCP "
            "reference, capability reference, release checklist) is at most 1,000 lines."
        ),
    ).valid is True

    _contract, rows = _rows(
        "What is the storage mutation coordination contract for cleanup and refresh?"
    )
    assert local_proof_for_obligation(
        rows[0],
        _unit(
            "Storage mutation coordination is fail-closed: a project sync or library refresh "
            "registers a writer lease; clear-index takes the cleanup barrier and refuses "
            "cleanup while an index writer is active."
        ),
    ).valid is True

    _contract, rows = _rows(
        "What happens if remove_library_docs runs while a library refresh is in flight?"
    )
    assert local_proof_for_obligation(
        rows[0],
        _unit(
            "`remove_library_docs` refuses removal while a writer lease for the shared "
            "storage is active during a library refresh."
        ),
    ).valid is True

    _contract, rows = _rows("How do I run the project answer quality v4 protocol?")
    validation_only = _unit(
        "python eval/project_answer_quality_v4_protocol.py --validate-protocol"
    )
    full_run = _unit(
        "python eval/project_answer_quality_v4_protocol.py --output /tmp/project-answer-quality-v4.json"
    )
    source = {
        "title": "Project answer quality protocol v4",
        "path": "eval/project_answer_quality_v4/README.md",
    }
    assert local_proof_for_obligation(rows[0], validation_only, source=source).valid is False
    assert local_proof_for_obligation(rows[0], full_run, source=source).valid is True
