from __future__ import annotations

from docmancer.docs.domain.answer_units import (
    best_local_proof,
    extract_answer_units,
    local_proof_for_obligation,
    materialize_answer_units,
)
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.domain.technical_terms import (
    coerce_technical_term,
    technical_term_present,
    term_sequence_present,
)


def _proof(question: str, text: str, *, path: str = "docs/index-cleanup.md"):
    contract = build_project_answer_contract(question)
    units = extract_answer_units(text, source_fields={"path_or_url": path})
    source = {"path": path, "authority": "source_of_truth"}
    return contract, units, [best_local_proof(row, units, source=source) for row in contract.proof_obligations]


def test_technical_term_aliases_are_separator_stable_but_boundary_exact():
    flag = coerce_technical_term("allow_incomplete", "cli_flag")
    assert technical_term_present(flag, "Use `--allow-incomplete` only after preview.")
    assert not technical_term_present(flag, "A draft may allow incomplete evidence.")

    command = coerce_technical_term("clear-index", "cli_command")
    assert technical_term_present(command, "Run `clear_index` after stopping workers.")
    assert not term_sequence_present("project", "project-local")


def test_purpose_proof_supports_copula_forward_reverse_and_table_forms():
    _, _, hits = _proof(
        "What is the quarantine feature in index cleanup?",
        "Quarantine is the same-filesystem staging area used before final deletion so moved targets can be restored if the move phase fails.",
    )
    assert hits[0] is not None


def test_direct_purpose_proposition_outranks_reverse_configuration_example():
    question = "What is DOCATLAS_HOME used for?"
    text = (
        "`DOCATLAS_HOME` overrides the storage root and defaults to `~/.docmancer`. "
        "Set `DOCATLAS_HOME=/some/path` to use another local root."
    )
    contract = build_project_answer_contract(question)
    units = extract_answer_units(text, include_soft_wrapped_prose=True)
    hit = best_local_proof(
        contract.proof_obligations[0], units,
        source={"path": "wiki/Home.md", "authority": "source_of_truth"},
    )
    assert hit is not None
    assert "overrides the storage root" in hit[0].text
    assert "defaults to" in hit[0].text

    _, _, hits = _proof(
        "What is allow_incomplete in clear-index?",
        "In `clear-index`, `--allow-incomplete` acknowledges that reported unverified vector or cache state will remain; it never bypasses live-process blockers.",
    )
    assert hits[0] is not None

    _, _, hits = _proof(
        "What is DOCATLAS_HOME used for?",
        "Override the storage root with `DOCATLAS_HOME` (defaults to `~/.docmancer`).",
        path="wiki/Configuration.md",
    )
    assert hits[0] is not None



def test_purpose_proof_rejects_negated_or_identity_only_statements():
    question = "What is DOCATLAS_HOME used for?"
    contract = build_project_answer_contract(question)
    source = {"path": "wiki/Reference.md", "authority": "source_of_truth"}
    for text in (
        "`DOCATLAS_HOME` is not used for the storage root.",
        "`DOCATLAS_HOME` is listed in the environment variable reference.",
    ):
        units = extract_answer_units(text, include_soft_wrapped_prose=True)
        assert best_local_proof(contract.proof_obligations[0], units, source=source) is None


def test_purpose_proof_binds_separator_alias_to_the_same_clause():
    _, _, hits = _proof(
        "What is allow_incomplete in clear-index?",
        "In `clear-index`, `allow_incomplete` acknowledges that unverified vector state will remain.",
    )
    assert hits[0] is not None



def test_purpose_predicate_must_not_overlap_the_technical_subject_name():
    question = "What is allow_incomplete in clear-index?"
    contract = build_project_answer_contract(question)
    unit = next(
        item for item in extract_answer_units("`--allow-incomplete` does not bypass a live-process blocker.")
        if item.kind == "sentence"
    )
    proof = local_proof_for_obligation(
        contract.proof_obligations[0], unit,
        source={"path": "docs/index-cleanup.md", "authority": "source_of_truth"},
    )
    assert proof.valid is False
    assert proof.reason == "purpose_subject_context_or_predicate_missing"

def test_effect_proof_rejects_an_unrelated_predicate_in_another_clause():
    question = "What does clear-index delete and preserve?"
    contract = build_project_answer_contract(question)
    text = (
        "`clear-index` previews a reviewed cleanup plan. "
        "Then a maintenance worker deletes unrelated build cache entries."
    )
    group = next(item for item in extract_answer_units(text) if item.kind == "unit_group")
    source = {"path": "docs/unrelated.md", "authority": "source_of_truth"}
    delete = local_proof_for_obligation(contract.proof_obligations[0], group, source=source)
    assert delete.valid is False
    assert delete.reason == "effect_delete_not_locally_bound"


def test_preserve_effect_accepts_relation_local_without_deleting_clause():
    question = "What does clear-index delete and preserve?"
    contract = build_project_answer_contract(question)
    text = "`clear-index` removes derived state without deleting project sources."
    unit = next(item for item in extract_answer_units(text) if item.kind == "sentence")
    source = {"path": "docs/index-cleanup.md", "authority": "source_of_truth"}
    delete = local_proof_for_obligation(contract.proof_obligations[0], unit, source=source)
    preserve = local_proof_for_obligation(contract.proof_obligations[1], unit, source=source)
    assert delete.valid is True
    assert preserve.valid is True

def test_supported_scope_inventory_requires_a_closed_plural_list():
    question = "Which scopes does clear-index support?"
    complete = "`clear-index` supports exactly two scopes: `project-local` and `global`."
    _, _, hits = _proof(question, complete)
    assert hits[0] is not None

    incomplete = "Run `clear-index --scope project-local` for a dedicated project index."
    contract = build_project_answer_contract(question)
    unit = extract_answer_units(incomplete)[0]
    proof = local_proof_for_obligation(
        contract.proof_obligations[0], unit,
        source={"path": "docs/example.md", "authority": "source_of_truth"},
    )
    assert proof.valid is False
    assert proof.reason == "inventory_not_closed_or_not_locally_bound"


def test_delete_and_preserve_use_relation_local_polarity_and_require_both_facets():
    question = "What does clear-index delete and preserve?"
    text = (
        "`clear-index` removes derived index state without deleting project sources. "
        "`clear-index` preserves `docmancer.yaml` and unrelated files."
    )
    contract, _, hits = _proof(question, text)
    assert len(contract.proof_obligations) == 2
    assert all(hit is not None for hit in hits)

    delete_only = "`clear-index` deletes an obsolete temporary database."
    units = extract_answer_units(delete_only)
    source = {"path": "docs/delete-only.md", "authority": "source_of_truth"}
    results = [
        best_local_proof(row, units, source=source)
        for row in contract.proof_obligations
    ]
    assert results[0] is not None
    assert results[1] is None


def test_materialization_preserves_the_largest_overlapping_assigned_witness():
    text = (
        "Prefix. `clear-index` deletes derived state. "
        "It preserves project sources and configuration."
    )
    units = extract_answer_units(text)
    group = next(item for item in units if item.kind == "unit_group")
    nested = next(
        item for item in units
        if item.kind == "sentence" and "deletes derived state" in item.text
    )
    material = materialize_answer_units(text, (group, nested))
    assert "deletes derived state" in material
    assert "preserves project sources" in material
    assert group.text in material


def test_markdown_bullet_continuations_are_one_visible_answer_unit():
    text = (
        "- `--allow-incomplete` acknowledges that unverified vector state\n"
        "  will remain; it never bypasses live-process blockers.\n"
        "- Another rule.\n"
    )
    bullets = [
        item for item in extract_answer_units(text, include_soft_wrapped_prose=True)
        if item.kind == "bullet"
    ]
    assert len(bullets) == 2
    assert "will remain" in bullets[0].text
    assert "never bypasses" in bullets[0].text
