"""Offline v4 producer and adversarial canonical-binding checks."""
from copy import deepcopy
import hashlib
import inspect
import json
import math

import pytest
from jsonschema import Draft202012Validator

from docmancer.docs.application.action_packet import (
    ACTION_PACKET_OUTPUT_SCHEMA, build_action_packet, evidence_identity_for_item,
    refresh_action_packet_estimate, serialize_action_packet, validate_action_packet,
)
from docmancer.docs.application.evidence_selection import (
    build_requirements, normalize_candidates, patch_selection_config, select_evidence,
)
from docmancer.docs.application._action_packet_part03 import _candidate_source, _mutation_payload
from docmancer.docs.application._action_packet_shared import _compact_value
from docmancer.docs.domain.mutation_intent import MutationIntentContract, RequestedTarget
from docmancer.docs.domain.patch_request_plan import PatchClause, PatchRequestPlan, PatchTarget


def _evidence(path="docs/cache.md", text="The cache uses the epoch_token to invalidate entries."):
    return {"path": path, "content": text, "title": "Cache contract", "authority": "canonical",
            "source_class": "project_doc", "char_start": 100, "char_end": 100 + len(text),
            "line_start": 7, "line_end": 7 + text.count("\n")}


def _canonical_packet():
    evidence = [_evidence()]
    requirements = build_requirements("cache", public_requirements=(evidence[0]["content"],))
    config = patch_selection_config() if not inspect.signature(patch_selection_config).parameters else patch_selection_config(2000)
    decision = select_evidence(evidence, question="cache", requirements=requirements, config=config)
    assert decision.assignments and decision.assignments[0].unit_id
    packet = {"schema_version": 4, "result": "data", "completeness": "complete",
              "edit_ready": False, "sources": [_candidate_source(row) for row in decision.selected_candidates],
              "requirements": [_compact_value(row) for row in decision.requirements],
              "assignments": [_compact_value(row) for row in decision.assignments]}
    refresh_action_packet_estimate(packet)
    return packet, evidence, decision.requirements


def test_canonical_witness_roundtrip():
    packet, evidence, requirements = _canonical_packet()
    assert validate_action_packet(packet, evidence_items=evidence, requirements=requirements) == []
    assert validate_action_packet(packet) == []
    assert list(Draft202012Validator(ACTION_PACKET_OUTPUT_SCHEMA).iter_errors(packet)) == []
    assert evidence_identity_for_item(evidence[0])[0] == packet["sources"][0]["evidence_id"]


def test_compact_unicode_estimate_and_final_metadata_refresh():
    packet = {"schema_version": 4, "result": "failure", "completeness": "unavailable",
              "edit_ready": False, "missing": ["недоступно"]}
    refresh_action_packet_estimate(packet)
    expected = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert serialize_action_packet(packet) == expected
    assert packet["estimated_tokens"] == math.ceil(len(expected.encode("utf-8")) / 4)
    assert validate_action_packet(packet) == []
    packet["kind"] = "patch_context"
    refresh_action_packet_estimate(packet)
    assert packet["estimated_tokens"] == math.ceil(len(serialize_action_packet(packet).encode("utf-8")) / 4)


@pytest.mark.parametrize("field,value", [
    ("unit_content_hash", "0" * 64), ("projected_content_hash", "1" * 64),
    ("unit_char_start", 2), ("unit_char_end", 3), ("char_start", 0),
    ("line_start", 0), ("unit_kind", "invented"), ("unit_id", "invented"),
    ("proof_role", "target_identity"), ("evidence_id", "invented"),
    ("requirement_id", "invented"), ("qualifiers", ["proposed"]),
])
def test_forged_witness_rejected(field, value):
    packet, evidence, _ = _canonical_packet()
    packet["assignments"][0][field] = value
    refresh_action_packet_estimate(packet)
    assert validate_action_packet(packet, evidence_items=evidence)


@pytest.mark.parametrize("field,value", [
    ("text", "invented text"), ("path", "docs/other.md"), ("symbol_or_section", "invented"),
    ("authority", "supporting"), ("instruction_trust", "trusted"),
    ("scope", "other"), ("version_binding", "invented"), ("char_start", 1),
    ("stable_id", "invented"), ("evidence_id", "ev-" + "0" * 16),
])
def test_forged_source_rejected(field, value):
    packet, evidence, _ = _canonical_packet()
    packet["sources"][0][field] = value
    if field == "text":
        packet["sources"][0]["content_sha256"] = hashlib.sha256(value.encode()).hexdigest()
    refresh_action_packet_estimate(packet)
    assert validate_action_packet(packet, evidence_items=evidence)


def test_requirement_fidelity_and_complete_coverage():
    packet, evidence, requirements = _canonical_packet()
    changed = deepcopy(packet)
    changed["requirements"][0]["public_provenance"] = "invented"
    refresh_action_packet_estimate(changed)
    assert validate_action_packet(changed, evidence_items=evidence, requirements=requirements)
    changed = deepcopy(packet)
    changed.pop("assignments")
    refresh_action_packet_estimate(changed)
    assert validate_action_packet(changed, evidence_items=evidence)
    changed["completeness"] = "partial"
    changed["missing"] = ["visible_content_assignment_required"]
    refresh_action_packet_estimate(changed)
    assert validate_action_packet(changed, evidence_items=evidence) == []


@pytest.mark.parametrize("extra", ["objective", "status", "policy", "max_tokens", "ready"])
def test_unknown_fields_and_non_authorization(extra):
    packet, _, _ = _canonical_packet()
    packet[extra] = "unexpected"
    refresh_action_packet_estimate(packet)
    assert validate_action_packet(packet)
    packet.pop(extra)
    packet["edit_ready"] = True
    refresh_action_packet_estimate(packet)
    assert validate_action_packet(packet)


def test_explicit_mutation_request_plan_lossless_and_hash_bound():
    long_value = "新" * 700
    target = PatchTarget(long_value, "symbol", 0, len(long_value), "mutate")
    clause = PatchClause("acceptance", "retain every explicit clause " * 80, 0, 800)
    plan = PatchRequestPlan("modify", (target,), acceptance_conditions=(clause,))
    contract = MutationIntentContract("modify", "source", (
        RequestedTarget(long_value, "symbol", 0, len(long_value)),
    ), destination="目的/" + long_value, acceptance_conditions=(clause.text,), request_plan=plan)
    packet = {"schema_version": 4, "result": "failure", "completeness": "unavailable",
              "edit_ready": False, "missing": ["no_admitted_evidence"],
              "mutation_intent": _mutation_payload(contract)}
    refresh_action_packet_estimate(packet)
    assert packet["mutation_intent"]["requested_targets"][0]["value"] == long_value
    assert packet["mutation_intent"]["request_plan"]["acceptance_conditions"][0]["text"] == clause.text
    assert validate_action_packet(packet, mutation_intent_contract=contract) == []
    packet["mutation_intent"]["request_plan"]["acceptance_conditions"][0]["text"] += "tampered"
    refresh_action_packet_estimate(packet)
    assert validate_action_packet(packet)


def test_max_tokens_is_not_silently_accepted():
    with pytest.raises(TypeError):
        build_action_packet(question="cache", context_pack=[], max_tokens=2000)
    with pytest.raises(TypeError):
        validate_action_packet({}, max_tokens=2000)


def test_builder_retains_partial_evidence_and_explicit_requirements(tmp_path):
    evidence = [_evidence()]
    packet = build_action_packet(question="cache", context_pack=evidence, project_path=str(tmp_path),
                                 public_requirements=(evidence[0]["content"], "missing_literal"))
    assert packet["result"] == "data" and packet["completeness"] == "partial"
    assert packet["sources"][0]["text"] == evidence[0]["content"]
    assert packet["edit_ready"] is False and "mutation_intent" not in packet
    assert len(packet["requirements"]) == 2
    assert validate_action_packet(packet, evidence_items=evidence, project_path=str(tmp_path)) == []


def test_builder_long_many_target_requirements_without_mutation_scaffold():
    paths = [f"src/{index}/" + "識" * 600 + ".py" for index in range(18)]
    packet = build_action_packet(question="inspect", context_pack=[], required_target_paths=paths)
    assert {row["value"] for row in packet["requirements"]} == set(paths)
    assert "mutation_intent" not in packet
    assert packet["result"] == "failure" and packet["completeness"] == "unavailable"
    assert validate_action_packet(packet) == []


def test_builder_unique_necessary_content_exceeds_old_cap(tmp_path):
    evidence = [_evidence(f"docs/component_{index}.md", "\n".join(
        f"Component {index} attribute field_{index}_{part} preserves epoch_{index}_{part}."
        for part in range(24)
    )) for index in range(9)]
    obligations = tuple({"kind": "exact_term", "value": f"epoch_{index}_0"} for index in range(9))
    packet = build_action_packet(question="component", context_pack=evidence,
                                 public_requirements=obligations, project_path=str(tmp_path))
    assert len(packet["sources"]) == 9
    assert packet["estimated_tokens"] > 2000
    assert {row["text"] for row in packet["sources"]} == {row["content"] for row in evidence}
    assert packet["completeness"] == "complete" and not packet["edit_ready"]
    assert validate_action_packet(packet, evidence_items=evidence, project_path=str(tmp_path)) == []


def test_builder_distinct_attribution_not_deduplicated(tmp_path):
    evidence = [_evidence("docs/one.md"), _evidence("docs/two.md")]
    packet = build_action_packet(question="cache", context_pack=evidence,
                                 required_evidence_paths=("docs/one.md", "docs/two.md"),
                                 public_requirements=(evidence[0]["content"],), project_path=str(tmp_path))
    assert {row["path"] for row in packet["sources"]} == {"docs/one.md", "docs/two.md"}
    assert validate_action_packet(packet, evidence_items=evidence, project_path=str(tmp_path)) == []


@pytest.mark.parametrize("change", [
    {"schema_version": 4.0}, {"estimated_tokens": 1.0}, {"edit_ready": 0},
    {"sources": []}, {"assignments": []}, {"requirements": []},
    {"missing": []}, {"missing": ["z", "a"]},
])
def test_failure_shape_and_strict_scalar_types(change):
    packet = {"schema_version": 4, "result": "failure", "completeness": "unavailable",
              "edit_ready": False, "missing": ["no_admitted_evidence"]}
    refresh_action_packet_estimate(packet)
    packet.update(change)
    if "estimated_tokens" not in change:
        refresh_action_packet_estimate(packet)
    assert validate_action_packet(packet)


def test_visible_source_invalid_character_window_is_rejected():
    packet, evidence, _ = _canonical_packet()
    packet["sources"][0]["char_end"] += 1
    evidence[0]["char_end"] += 1
    refresh_action_packet_estimate(packet)
    assert validate_action_packet(packet, evidence_items=evidence)


def test_duplicate_requirements_assignments_and_sources_rejected():
    packet, evidence, _ = _canonical_packet()
    for key in ("requirements", "assignments", "sources"):
        changed = deepcopy(packet)
        changed[key].append(deepcopy(changed[key][0]))
        refresh_action_packet_estimate(changed)
        assert validate_action_packet(changed, evidence_items=evidence)
