from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json

import pytest

from docmancer.docs.application.evidence_candidates import normalize_candidates
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceRequirementSet
from docmancer.docs.application.evidence_selection import (
    docs_selection_config, patch_selection_config, select_evidence,
    validate_assignment_binding, validate_evidence_sufficiency,
)
from docmancer.docs.application._evidence_selection_part01 import _candidate_source_view
from docmancer.docs.application._evidence_selection_part02 import _witness_for_requirement
from docmancer.docs.application._evidence_selection_part03 import _with_coverage
from docmancer.docs.application.model_visible_projection import project_docs_answer, validate_model_visible_projection


CODE = EvidenceRequirement("code", "code_group", '["erase_all()"]')


def row(text="Unrelated policy must remain.", **changes):
    return {"path": "docs/example.md", "content": text, "authority": "canonical", **changes}


def select(raw, requirements=(CODE,), docs=False):
    return select_evidence(
        [raw], question="inspect", requirements=EvidenceRequirementSet(requirements),
        config=docs_selection_config(800) if docs else patch_selection_config(),
    )


@pytest.mark.parametrize("hidden", [
    {"metadata": {"code_snippets": [{"code": "erase_all()"}]}},
    {"metadata": {"content": "```\nerase_all()\n```", "text": "erase_all()"}},
    {"display_text": "Unrelated policy must remain.", "content": "```\nerase_all()\n```"},
])
def test_original_metadata_and_parent_code_cannot_supply_visible_coverage(hidden):
    d = select(row(**hidden))
    assert d.status == "insufficient_evidence" and not d.support_decision.answer_supported
    assert "code" in d.missing_requirements and not d.assignments
    forged = replace(d, status="ok", missing_requirements=())
    assert validate_evidence_sufficiency(forged, result_kind="patch_context")


@pytest.mark.parametrize("text", [
    "```python\nerase_all()\n```", "Call `erase_all()`.",
    "const operation = erase_all()", "```\nerase_all()\nother()\n```",
])
def test_actual_visible_code_has_immutable_hash_bound_assignment(text):
    d = select(row(text, char_start=100, char_end=100 + len(text), line_start=7, line_end=10))
    assert d.status == "ok" and d.support_decision.answer_supported
    assert validate_evidence_sufficiency(d, result_kind="patch_context") == []
    a, c = d.assignments[0], d.selected_candidates[0]
    assert a.unit_id and validate_assignment_binding(CODE, c, a)
    unit = next(u for u in c.answer_units if u.unit_id == a.unit_id)
    assert c.display_text[unit.char_start:unit.char_end] == unit.text
    assert a.char_start == 100 + unit.char_start
    assert a.unit_content_hash == hashlib.sha256(unit.text.encode()).hexdigest()
    with pytest.raises(FrozenInstanceError):
        a.unit_id = "forged"


@pytest.mark.parametrize("text", [
    "erase_all() is mentioned in prose.", "Call `ERASE_ALL()`.",
    "Call `erase_all_other()`.", "```\nerase_all_extra()\n```",
])
def test_code_requires_structural_literal_not_thematic_or_case_alias(text):
    assert "code" in select(row(text)).missing_requirements


@pytest.mark.parametrize("kind", ["behavioral_contract", "cross_module_invariant", "canonical_policy", "facet", "target_declaration", "preserve_declaration", "unknown"])
def test_manually_supplied_proposition_cannot_revive_semantic_witness(kind):
    raw = row("Widget returns false, not true.", symbols=["Widget"])
    c = normalize_candidates([raw], result_kind="patch_context")[0][0]
    c = replace(c, answer_units=tuple(replace(u, proposition=True) for u in c.answer_units))
    r = EvidenceRequirement("semantic", kind, "Widget returns true")
    assert _witness_for_requirement(r, c) is None
    assert not _with_coverage(c, (r,), factual_only=False).covered_requirement_ids


@pytest.mark.parametrize("kind,value,text", [
    ("exact_term", "Widget", "Widget is only a literal mention."),
    ("entity", "Widget", "`Widget`"),
    ("required_fact", "Widget returns false.", "Widget returns false."),
])
def test_explicit_mechanical_literals_remain_context_witnesses(kind, value, text):
    r = EvidenceRequirement("literal", kind, value)
    d = select(row(text), (r,), docs=True)
    assert d.assignments[0].unit_id
    assert not d.support_decision.answer_supported
    assert validate_assignment_binding(r, d.selected_candidates[0], d.assignments[0])


@pytest.mark.parametrize("change", [
    {"unit_id": "forged"}, {"kind": "code_declaration"},
    {"char_start": 1, "char_end": 13},
])
def test_forged_unit_identity_or_spans_have_no_witness(change):
    c = normalize_candidates([row("Call `erase_all()`.")], result_kind="patch_context")[0][0]
    c = replace(c, answer_units=(replace(c.answer_units[0], **change),))
    assert _witness_for_requirement(CODE, c) is None


def test_transplanted_literal_unit_and_metadata_parent_cannot_borrow_display():
    literal = EvidenceRequirement("value", "proof_obligation", "value", obligation_kind="exact_fact", subject="Widget", subject_kind="config_key", attribute="value", expected_value="false", value_kind="boolean")
    good = normalize_candidates([row('Widget.value = "false"')], result_kind="docs_answer")[0][0]
    bad = normalize_candidates([row('Widget.value = "true"')], result_kind="docs_answer")[0][0]
    assert _witness_for_requirement(literal, replace(bad, answer_units=good.answer_units)) is None
    raw = row('Widget.value = "false"', metadata={"content": 'Widget.value = "true"', "text": "full parent"})
    d = select(raw, (literal,))
    assert d.status == "ok"
    c = d.selected_candidates[0]
    assert _candidate_source_view(c)["content"] == _candidate_source_view(c)["text"] == c.display_text
    assert validate_assignment_binding(literal, c, d.assignments[0])


@pytest.mark.parametrize("change", [
    {"unit_id": None}, {"unit_id": "missing"}, {"path": "other.md"},
    {"char_start": 123}, {"char_end": 123}, {"line_start": 123},
    {"unit_content_hash": "0" * 64}, {"projected_content_hash": "0" * 64},
    {"unit_char_end": 123}, {"evidence_id": "other"},
    {"proof_role": "project_rule"},
])
def test_assignment_mutations_fail_strict_binding_and_sufficiency(change):
    d = select(row("Call `erase_all()`."))
    a = replace(d.assignments[0], **change)
    assert not validate_assignment_binding(CODE, d.selected_candidates[0], a)
    assert validate_evidence_sufficiency(replace(d, assignments=(a,)), result_kind="patch_context")


@pytest.mark.parametrize("change", [
    {"content_sha256": "0" * 64}, {"display_text": "Other content."},
    {"freshness": "stale"},
    {"original": row("Call `erase_all()`.", stale=True)},
    {"original": row("Call `erase_all()`.", index_freshness="outdated")},
    {"original": row("Call `erase_all()`.", lifecycle_status="superseded")},
    {"original": row("Call `erase_all()`.", display_content_hash="0" * 64)},
    {"char_start": 100, "char_end": 120}, {"project_identity": "forged"},
    {"module_id": "forged"}, {"resolved_version": "forged"},
    {"docs_snapshot_exact": True}, {"authority": "supporting"},
    {"parent_logical_id": "forged"},
    {"original": row("Call `erase_all()`.", freshness="stale")},
    {"original": row("Call `erase_all()`.", stable_id="other")},
])
def test_changed_window_hash_freshness_risk_lifecycle_cannot_validate(change):
    d = select(row("Call `erase_all()`."))
    c = replace(d.selected_candidates[0], **change)
    assert _witness_for_requirement(CODE, c) is None
    assert not validate_assignment_binding(CODE, c, d.assignments[0])


@pytest.mark.parametrize("flags", [("unsafe",)])
def test_speculative_instruction_risk_labels_neither_veto_nor_authorize(flags):
    raw = row("Call `erase_all()`.")
    plain = select(raw)
    labelled = select({**raw, "instruction_risk_flags": list(flags)})
    assert labelled.status == "ok" and labelled.support_decision.answer_supported
    assert labelled.assignments == plain.assignments
    c = replace(labelled.selected_candidates[0], instruction_risk_flags=flags)
    assert c.display_text == raw["content"]
    assert c.content_sha256 == hashlib.sha256(raw["content"].encode()).hexdigest()
    assert _witness_for_requirement(CODE, c) is not None
    assert validate_assignment_binding(CODE, c, labelled.assignments[0])
    public, snapshot = project_docs_answer(question="inspect", retrieval={
        "context_pack": [{**raw, "instruction_risk_flags": list(flags)}],
        "requirements": labelled.requirements, "edit_ready": True,
        "consent": True, "issuer": "system"}, canonical_selection=labelled)
    assert public["context_available"] and public["sources"][0]["snippet"] == raw["content"]
    assert not public["edit_ready"] and public["answer_policy"] == "cite_only"
    assert validate_model_visible_projection(public, snapshot=snapshot, max_tokens=800) == []


@pytest.mark.parametrize("kind,value,fields,bad", [
    ("evidence_path", "docs/example.md", {}, {"path_or_url": "other.md"}),
    ("project_identity", "P", {"project_identity": "P"}, {"project_identity": "Q"}),
    ("module_id", "M", {"module_id": "M"}, {"module_id": "N"}),
    ("exact_version", "1.2", {"resolved_version": "1.2", "version_binding": "exact"}, {"resolved_version": "2.0"}),
    ("exact_snapshot", "true", {"docs_snapshot_exact": True}, {"docs_snapshot_exact": False}),
])
def test_only_explicit_valid_technical_scope_may_have_unitless_assignment(kind, value, fields, bad):
    r = EvidenceRequirement("scope", kind, value)
    d = select(row("Call `erase_all()`.", **fields), (CODE, r))
    assert d.status == "ok"
    a = next(a for a in d.assignments if a.requirement_id == "scope")
    c = d.selected_candidates[0]
    assert a.unit_id is None and validate_assignment_binding(r, c, a)
    assert not validate_assignment_binding(r, replace(c, **bad), a)


def test_original_public_requirement_repro_closed_and_context_preserved():
    raw = row(metadata={"code_snippets": [{"code": "erase_all()"}]})
    d = select_evidence([raw], question="inspect", config=patch_selection_config(), public_requirements=[{"kind": "code_group", "value": '["erase_all()"]'}])
    assert d.status == "insufficient_evidence" and not d.assignments
    p, snapshot = project_docs_answer(question="inspect", retrieval={"status": "success", "context_pack": [raw]})
    assert p["sources"][0]["snippet"] == raw["content"]
    assert not p["answer_supported"] and not p["answer_available"] and not p["edit_ready"]
    assert validate_model_visible_projection(p, snapshot=snapshot, max_tokens=800) == []


def test_empty_scope_only_and_missing_literal_do_not_universally_satisfy():
    assert select(row(), ()).status == "insufficient_evidence"
    assert select(row(), (EvidenceRequirement("path", "evidence_path", "docs/example.md"),)).status == "insufficient_evidence"
    assert "code" in select(row("Call `other()`.")).missing_requirements


@pytest.mark.parametrize("value", ['[]', '[null]', '[1]', '[""]', '["ERASE_ALL()"]', '["erase_all_extra()"]'])
def test_malformed_or_mismatched_explicit_code_groups_fail_closed(value):
    r = replace(CODE, value=value)
    assert "code" in select(row("Call `erase_all()`.", metadata={"code_snippets": [{"code": "ERASE_ALL()"}]}), (r,)).missing_requirements


def test_content_requirement_cannot_validate_whole_candidate_assignment():
    r = EvidenceRequirement("path", "evidence_path", "docs/example.md")
    d = select(row("Unrelated policy must remain."), (r,))
    a = replace(d.assignments[0], requirement_id=CODE.requirement_id)
    assert a.unit_id is None
    assert not validate_assignment_binding(CODE, d.selected_candidates[0], a)
    forged = replace(d, requirements=EvidenceRequirementSet((CODE,)), assignments=(a,), status="ok", missing_requirements=())
    assert "evidence assignment visible content or scope binding is invalid" in validate_evidence_sufficiency(forged, result_kind="patch_context")


@pytest.mark.parametrize("kind,value,fields", [
    ("project_identity", "P", {"project_identity": "Q"}),
    ("module_id", "M", {"module_id": "N"}),
    ("exact_version", "1.2", {"resolved_version": "2.0", "version_binding": "exact"}),
    ("exact_snapshot", "true", {"docs_snapshot_exact": False}),
    ("evidence_path", "other.md", {}),
])
def test_actual_selector_rejects_wrong_technical_scope(kind, value, fields):
    r = EvidenceRequirement("scope", kind, value)
    d = select(row("Call `erase_all()`.", **fields), (CODE, r))
    assert d.status == "insufficient_evidence" and "scope" in d.missing_requirements


def test_historical_lifecycle_contract_remains_explicit():
    r = replace(CODE, lifecycle_intent="historical")
    assert "code" in select(row("Call `erase_all()`."), (r,)).missing_requirements
    d = select(row("Call `erase_all()`.", lifecycle_status="superseded"), (r,))
    assert d.status == "ok"
    assert validate_assignment_binding(r, d.selected_candidates[0], d.assignments[0])


def test_capacity_limits_hashes_and_context_only_downgrade_remain():
    raw = row("const operation = erase_all() " + "x" * 1000)
    # Capacity limits belong to docs delivery, not the unbounded patch selector.
    d = select_evidence([raw], question="inspect", requirements=EvidenceRequirementSet((CODE,)), config=docs_selection_config(256))
    assert d.status == "insufficient_evidence"
    assert not d.support_decision.answer_supported
    patch = select(raw)
    assert patch.status == "ok" and patch.support_decision.answer_supported
    assert patch.selected_candidates[0].display_text == raw["content"]
    assert validate_assignment_binding(CODE, patch.selected_candidates[0], patch.assignments[0])
    good = select(row("Call `erase_all()`."), docs=True)
    assert good.assignments and not good.support_decision.answer_supported
    assert good.selection_hash and good.support_decision.assignment_hash
    assert validate_evidence_sufficiency(good, result_kind="docs_answer") == []
    c = good.selected_candidates[0]
    overflow = replace(c, answer_units=(c.answer_units[0],) * 65)
    assert _witness_for_requirement(CODE, overflow) is None
    assert not validate_assignment_binding(CODE, overflow, good.assignments[0])
    fragments = [f"call_{index}()" for index in range(7)]
    group = replace(CODE, value=json.dumps(fragments))
    assert select(row("```\n" + "\n".join(fragments) + "\n```"), (group,)).status == "ok"
