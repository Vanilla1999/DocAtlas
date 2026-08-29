from __future__ import annotations

from docmancer.docs.domain.answer_units import (
    best_local_proof,
    extract_answer_units,
    local_proof_for_obligation,
    materialize_answer_units,
)
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract


def _obligation(question: str):
    obligations = build_project_answer_contract(question).proof_obligations
    assert len(obligations) == 1
    return obligations[0]


def test_inventory_requires_a_locally_bound_closed_inventory():
    obligation = _obligation("What are the public tools of the Docs MCP server?")
    branding = extract_answer_units(
        "New user-facing docs should use DocAtlas and the doc-atlas CLI command."
    )
    valid = extract_answer_units(
        "The public tools are `get_docs_context`, `prepare_docs`, and `docs_status`."
    )

    assert best_local_proof(obligation, branding) is None
    match = best_local_proof(obligation, valid)
    assert match is not None
    assert match[1].reason == "inventory"


def test_inventory_count_can_be_proved_by_explicit_count_or_closed_list():
    obligation = _obligation("How many public MCP tools does DocAtlas expose?")
    explicit = extract_answer_units("The Docs MCP server exposes exactly three public tools.")
    names = extract_answer_units(
        "The public tools are `get_docs_context`, `prepare_docs`, and `docs_status`."
    )
    assert best_local_proof(obligation, explicit) is not None
    assert best_local_proof(obligation, names) is not None


def test_command_proof_rejects_troubleshooting_distractor():
    obligation = _obligation(
        "Which command does doc-atlas use to sync project docs after file changes?"
    )
    distractor = extract_answer_units("The agent does not use the Docs MCP workflow.")
    command = extract_answer_units(
        'Call `prepare_docs(action="sync_project_docs", changed_paths=[...])` after file changes.'
    )
    assert best_local_proof(obligation, distractor) is None
    assert best_local_proof(obligation, command) is not None


def test_location_uses_source_field_not_fake_content_offsets():
    obligation = _obligation("Where is the DocAtlas execution roadmap?")
    units = extract_answer_units(
        "Current execution tasks are tracked here.",
        source_fields={"path_or_url": "roadmap/README.md", "section": "Execution roadmap"},
    )
    match = best_local_proof(
        obligation,
        units,
        source={"path_or_url": "roadmap/README.md", "section": "Execution roadmap"},
    )
    assert match is not None
    unit, proof = match
    assert unit.kind == "source_field"
    assert unit.char_start is None and unit.char_end is None
    assert proof.reason == "location"
    project_docs = _obligation("Where is project docs configuration defined?")
    cleanup = extract_answer_units(
        "docs/index-cleanup.md",
        source_fields={"path_or_url": "docs/index-cleanup.md"},
    )
    catalog = extract_answer_units(
        "docs/project-docs-mcp-workflow.md",
        source_fields={"path_or_url": "docs/project-docs-mcp-workflow.md"},
    )
    assert best_local_proof(project_docs, cleanup) is None
    assert best_local_proof(project_docs, catalog) is not None

    answer_contract = _obligation("Where is the project answer contract documented?")
    python_source = extract_answer_units(
        "docmancer/docs/domain/_project_answer_contract_part01.py",
        source_fields={"path_or_url": "docmancer/docs/domain/_project_answer_contract_part01.py"},
    )
    markdown_source = extract_answer_units(
        "docs/project-answer-contract.md",
        source_fields={"path_or_url": "docs/project-answer-contract.md"},
    )
    assert best_local_proof(answer_contract, python_source) is None
    assert best_local_proof(answer_contract, markdown_source) is not None


def test_workflow_requires_one_bounded_contiguous_group():
    obligation = _obligation("How does prepare_docs sync_project_docs work?")
    units = extract_answer_units(
        '`prepare_docs(action="sync_project_docs")` first discovers changed project documents. '
        "Then it removes deleted pages, reindexes changed sections, and publishes the new generation."
    )
    group = next(item for item in units if item.kind == "unit_group")
    assert local_proof_for_obligation(obligation, group).valid is True
    individual = [item for item in units if item.kind == "sentence"]
    assert all(not local_proof_for_obligation(obligation, item).valid for item in individual)


def test_materialization_preserves_short_connective_context_between_assigned_units():
    source = (
        "EvidenceRequirementSet and SupportDecision are canonical selector inputs. "
        "Presentation cannot determine support or drop a mandatory-facet witness. "
        "Every public mode preserves the same decision_hash and selected evidence IDs."
    )
    sentences = [item for item in extract_answer_units(source) if item.kind == "sentence"]
    assert len(sentences) == 3

    material = materialize_answer_units(source, (sentences[0], sentences[2]))

    assert material == source


def test_behavior_proof_accepts_explicit_replacement_relation():
    obligation = _obligation("What does prepare_docs replace?")
    units = extract_answer_units(
        '`prepare_docs(action="sync_project_docs")` replaces the old two-step `inspect -> ingest` loop.'
    )

    match = best_local_proof(obligation, units)

    assert match is not None
    assert match[1].reason == "behavior"


def test_behavior_proof_rejects_a_negative_only_witness():
    obligation = _obligation("What does OrderSubmission do?")

    units = extract_answer_units("OrderSubmission does not validate drafts.")

    assert best_local_proof(obligation, units) is None
