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




def test_original_public_requirement_repro_closed_and_context_preserved():
    raw = row(metadata={"code_snippets": [{"code": "erase_all()"}]})
    d = select_evidence([raw], question="inspect", config=patch_selection_config(), public_requirements=[{"kind": "code_group", "value": '["erase_all()"]'}])
    assert d.status == "insufficient_evidence" and not d.assignments
    p, snapshot = project_docs_answer(question="inspect", retrieval={"status": "success", "context_pack": [raw]})
    assert p["sources"][0]["snippet"] == raw["content"]
    assert not p["answer_supported"] and not p["answer_available"] and not p["edit_ready"]
    assert validate_model_visible_projection(p, snapshot=snapshot, max_tokens=800) == []











