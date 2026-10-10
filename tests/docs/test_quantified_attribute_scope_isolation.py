"""Explicit numeric-statement coverage is literal evidence, not NL entailment."""
from __future__ import annotations

from copy import deepcopy
import hashlib

from docmancer.docs.application.action_packet import (
    build_action_packet, refresh_action_packet_estimate, validate_action_packet,
)
from docmancer.docs.application.model_visible_projection import (
    project_patch_context, validate_model_visible_projection,
)
from docmancer.docs.domain.canonical import canonical_hash
from docmancer.docs.domain.project_answer_contract import build_project_answer_contract


QUESTION = "How many retry attempts does ProjectRetryPolicy allow?"
NUMERIC_STATEMENT = "ProjectRetryPolicy allows at most two retry attempts with bounded exponential backoff."


def _source(text):
    return {
        "path": "docs/retry-policy.md", "source_class": "project_doc", "doc_scope": "project",
        "project_identity": "project:retry-unit", "authority": "canonical", "freshness": "current",
        "content": text, "display_text": text, "stable_chunk_id": "retry-policy:child",
        "parent_logical_id": "retry-policy:parent",
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "char_start": 120, "char_end": 120 + len(text),
        "line_start": 5, "line_end": 5 + text.count("\n"),
    }


def _packet(source, *, facts=(NUMERIC_STATEMENT,)):
    before = deepcopy(source)
    packet = build_action_packet(
        question=QUESTION, context_pack=[source], public_requirements=facts,
        project_identity="project:retry-unit",
    )
    assert source == before
    assert validate_action_packet(packet, evidence_items=[source]) == []
    projected, snapshot = project_patch_context(packet=packet, evidence_items=[source])
    assert validate_model_visible_projection(projected, snapshot=snapshot) == []
    assert projected.get("sources", []) == packet.get("sources", [])
    assert projected.get("requirements", []) == packet.get("requirements", [])
    assert projected["edit_ready"] is packet["edit_ready"] is False
    return packet, projected, snapshot


def _numeric_requirement(packet):
    requirement = next(row for row in packet["requirements"] if row["value"] == NUMERIC_STATEMENT)
    assert requirement["kind"] == "required_fact" and requirement["mandatory"] is True
    assert requirement["public_provenance"] == "public_task_contract"
    return requirement


def test_numeric_requirement_is_explicit_and_does_not_come_from_question_prose():
    contract = build_project_answer_contract(QUESTION)
    assert contract.question_hash == canonical_hash(QUESTION)
    assert not contract.proof_obligations and not contract.subjects
    source = _source("# Retry policy\n\n" + NUMERIC_STATEMENT)
    plain, _, _ = _packet(source, facts=())
    assert not any(row["kind"] == "required_fact" for row in plain["requirements"])
    explicit, _, _ = _packet(source)
    _numeric_requirement(explicit)
    assert explicit["result"] == "data" and explicit["completeness"] == "complete"
    assert len(explicit["requirements"]) == len(plain["requirements"]) + 1


def test_subject_mention_without_numeric_statement_cannot_cover_explicit_requirement():
    text = "OrderSubmission validates a draft and delegates network retry decisions to ProjectRetryPolicy."
    packet, projected, _ = _packet(_source(text))
    requirement = _numeric_requirement(packet)
    assert packet["result"] == projected["result"] == "data"
    assert packet["completeness"] == projected["completeness"] == "partial"
    assert requirement["requirement_id"] in packet["missing"]
    assert not any(row["requirement_id"] == requirement["requirement_id"]
                   for row in packet.get("assignments", []))
    positive, _, _ = _packet(_source(NUMERIC_STATEMENT))
    assert positive["completeness"] == "complete"
    assert any(row["requirement_id"] == requirement["requirement_id"] for row in positive["assignments"])


def test_numeric_statement_has_exact_source_bound_witness_not_edit_authority():
    text = "# Retry policy\n\n" + NUMERIC_STATEMENT
    source = _source(text)
    packet, projected, snapshot = _packet(source)
    assert packet["completeness"] == projected["completeness"] == "complete"
    requirement = _numeric_requirement(packet)
    assignment = next(row for row in packet["assignments"] if row["requirement_id"] == requirement["requirement_id"])
    start = text.index(NUMERIC_STATEMENT)
    assert assignment["unit_char_start"] == start and assignment["unit_char_end"] == len(text)
    assert text[assignment["unit_char_start"]:assignment["unit_char_end"]] == NUMERIC_STATEMENT
    assert assignment["char_start"] == 120 + start and assignment["char_end"] == 120 + len(text)
    assert assignment["line_start"] == assignment["line_end"] == 7
    assert assignment["unit_content_hash"] == hashlib.sha256(NUMERIC_STATEMENT.encode()).hexdigest()
    assert assignment["projected_content_hash"] == assignment["unit_content_hash"]
    assert assignment["unit_id"] and assignment["unit_kind"] == "sentence"
    assert packet["sources"][0]["text"] == text
    assert packet["sources"][0]["content_sha256"] == hashlib.sha256(text.encode()).hexdigest()

    # Rehashing changed bytes does not validate the old packet or manufacture
    # coverage of the original requirement. Both source and visible views matter.
    changed = _source(text.replace("two", "six"))
    assert validate_action_packet(packet, evidence_items=[changed])
    different, _, _ = _packet(changed)
    assert requirement["requirement_id"] in different["missing"]
    assert different["completeness"] == "partial"
    forged = deepcopy(projected)
    forged["sources"][0]["text"] = changed["content"]
    forged["sources"][0]["content_sha256"] = changed["display_content_hash"]
    refresh_action_packet_estimate(forged)
    assert validate_model_visible_projection(forged, snapshot=snapshot)
    for field, value in (("unit_content_hash", "0" * 64), ("char_start", 121), ("unit_char_end", len(text) - 1)):
        forged = deepcopy(packet)
        forged["assignments"][0][field] = value
        refresh_action_packet_estimate(forged)
        assert validate_action_packet(forged, evidence_items=[source])
    for change in ({"freshness": "stale"}, {"project_identity": "project:foreign"},
                   {"display_content_hash": "0" * 64}):
        excluded, _, _ = _packet({**source, **change})
        assert excluded["completeness"] != "complete"
        assert requirement["requirement_id"] in excluded["missing"]
    forged = deepcopy(packet)
    forged["edit_ready"] = True
    refresh_action_packet_estimate(forged)
    assert validate_action_packet(forged, evidence_items=[source])
