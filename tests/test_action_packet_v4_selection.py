"""Offline v4 selection contract tests; no provider or corpus access."""
from dataclasses import asdict, replace
import hashlib
import inspect
import json

import pytest

from docmancer.docs.application import evidence_selection as selector
from docmancer.docs.application.evidence_models import EvidenceRequirement, EvidenceRequirementSet
from docmancer.docs.application.model_visible_projection import project_docs_answer, validate_model_visible_projection
from docmancer.docs.domain.answer_units import extract_answer_units


def row(index, text=None, **overrides):
    text = text or f"const setting_{index} = 'value_{index}';"
    item = {
        "stable_chunk_id": f"child-{index}",
        "parent_logical_id": "shared-parent",
        "path": f"src/config_{index}.py",
        "display_text": text,
        "display_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "char_start": 100,
        "char_end": 100 + len(text),
        "line_start": 3,
        "line_end": 3 + text.count("\n"),
        "retrieval_rank": index + 1,
        "score": 0.8,
    }
    item.update(overrides)
    return item


def select(items, **kwargs):
    return selector.select_evidence(
        items, question=kwargs.pop("question", ""),
        config=selector.patch_selection_config(), **kwargs,
    )




def _assert_docs_profile_fidelity(config):
    facts = [f"Route {index} requires approval {index} before deployment." for index in range(27)]
    long_text = facts[0] + "\n" + "\n".join(
        f"Route 0 field {index} retains its exact configured value {index}." for index in range(120)
    ) + "\nException: route 0 must not retry an opted-out recipient."
    items = [row(index, long_text if index == 0 else fact, path=f"docs/routes_{index // 3}.md")
             for index, fact in enumerate(facts)]
    requirements = EvidenceRequirementSet(tuple(
        EvidenceRequirement(f"fact-{index}", "required_fact", fact)
        for index, fact in enumerate(facts)
    ))
    decision = selector.select_evidence(items, question="", config=config, requirements=requirements)
    assert len(decision.selected_candidates) == len(decision.assignments) == 27
    assert decision.metrics["selected_sources"] == 9
    assert not decision.omissions
    assert not decision.support_decision.answer_supported
    by_id = {item["stable_chunk_id"]: item for item in items}
    by_requirement = {item.requirement_id: item for item in requirements}
    by_candidate = {item.stable_id: item for item in decision.selected_candidates}
    for candidate in decision.selected_candidates:
        original = by_id[candidate.stable_id]
        assert candidate.display_text == candidate.projected_text == original["display_text"]
        assert candidate.content_sha256 == original["display_content_hash"]
        assert (candidate.char_start, candidate.char_end) == (original["char_start"], original["char_end"])
    for assignment in decision.assignments:
        assert selector.validate_assignment_binding(
            by_requirement[assignment.requirement_id], by_candidate[assignment.evidence_id], assignment,
        )
    assert not selector.validate_evidence_sufficiency(decision, result_kind="docs_answer")
    payload, snapshot = project_docs_answer(
        question="", retrieval={"status": "success", "selection_profile": config.profile},
        canonical_selection=decision,
    )
    assert len(payload["sources"]) == len(snapshot) == 27
    assert payload["estimated_tokens"] > 800
    assert {source["evidence_id"]: source["snippet"] for source in payload["sources"]} == {
        item["stable_chunk_id"]: item["display_text"] for item in items
    }
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []









































