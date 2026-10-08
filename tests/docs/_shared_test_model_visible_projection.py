from __future__ import annotations

from copy import deepcopy

import pytest

from docmancer.docs.application.action_packet import build_action_packet, validate_action_packet
from docmancer.docs.application.model_visible_projection import (
    FORBIDDEN_MODEL_KEYS,
    bound_insufficient_projection,
    canonical_projection_bytes,
    estimate_projection_tokens,
    project_docs_answer,
    project_insufficient,
    project_patch_context,
    sanitized_projection_manifest,
    validate_model_visible_projection,
)
from docmancer.mcp.docs_server import call_docs_tool_payload


def _forbidden_occurrences(value):
    if isinstance(value, dict):
        return [key for key, child in value.items() if key in FORBIDDEN_MODEL_KEYS] + [
            found for child in value.values() for found in _forbidden_occurrences(child)
        ]
    if isinstance(value, list):
        return [found for child in value for found in _forbidden_occurrences(child)]
    return []


def _decode_support_envelope(value):
    import base64
    import json
    import zlib

    encoded = value["data"]
    encoded += "=" * (-len(encoded) % 4)
    return json.loads(zlib.decompress(base64.urlsafe_b64decode(encoded)))


def _ready_patch_fixture(*, policy_content: str | None = None):
    policy_text = policy_content or (
        "The patch must preserve source IDs.\n"
        "Run pytest tests/docs/test_mcp_boundary.py."
    )
    policy = {
        "path": "AGENTS.md",
        "heading_path": "Rules",
        "authority": "canonical",
        "repository_authority": "explicit_agent_policy",
        "instruction_trust": "scoped_agent_policy",
        "scope_verified": True,
        "policy_scope": "/project",
        "content": policy_text,
    }
    target = {
        "path": "src/projection.py",
        "heading_path": "project_patch_context",
        "authority": "official",
        "source_class": "code_graph",
        "symbols": ["project_patch_context"],
        "content": "def project_patch_context(packet, evidence_items): pass",
        "snippet": "def project_patch_context(packet, evidence_items): pass",
    }
    evidence = [policy, target]
    packet = build_action_packet(
        question="Update src/projection.py",
        context_pack=evidence,
        project_path="/project",
    )
    assert packet["status"] == "ok"
    assert packet["mutation_intent"]["ready"] is True
    assert validate_action_packet(
        packet, evidence_items=evidence, project_path="/project",
    ) == []
    return packet, evidence


def _assert_oversized_insufficient_projection_fidelity(budget):
    payload = {
        "status": "insufficient_evidence",
        "kind": "docs_answer",
        "missing": ["missing " * 2_000],
        "recommended_next_action": {
            "tool": "prepare_docs",
            "observations": {"unbounded": "value " * 2_000},
            "requires_confirmation": True,
            "confirmation_reason": "project_docs_preflight",
            "auto_execute": False,
        },
        "answer_supported": False,
        "answer_available": False,
        "edit_ready": False,
        "documentation_supported": False,
        "hard_stop": True,
        "requires_confirmation": True,
        "support_status": "insufficient_evidence",
        "missing_requirement_ids": [f"requirement-{index}" for index in range(100)],
        "requirements_hash": "a" * 64,
        "selector_config_hash": "b" * 64,
        "eligibility_contract_hash": "c" * 64,
        "candidate_trace_hash": "d" * 64,
        "selection_hash": "e" * 64,
        "assignment_hash": "f" * 64,
        "decision_hash": "0" * 64,
    }
    original = deepcopy(payload)

    bound_insufficient_projection(payload, max_tokens=budget)

    # These legacy budgets must not discard an already-formed public DTO.
    # Expected content comes from the input, independently of the projector.
    measured_tokens = estimate_projection_tokens(payload)
    assert measured_tokens > budget
    assert payload == {**original, "estimated_tokens": measured_tokens}
    assert payload["missing"] == original["missing"]
    assert payload["missing_requirement_ids"] == original["missing_requirement_ids"]
    assert payload["recommended_next_action"] == original["recommended_next_action"]
    assert payload["answer_supported"] is payload["answer_available"] is False
    assert payload["edit_ready"] is payload["documentation_supported"] is False
    assert payload["hard_stop"] is payload["requires_confirmation"] is True
    assert payload["recommended_next_action"]["requires_confirmation"] is True
    assert payload["recommended_next_action"]["auto_execute"] is False
    assert "support_envelope" not in payload
    assert validate_model_visible_projection(payload, snapshot={}, max_tokens=budget) == []

    # Removing a representation cap must not weaken format, disclosure, or
    # fail-closed authority validation. Each mutation targets its own guard.
    for field, value, error in (
        ("kind", "invalid", "invalid projection kind"),
        ("status", "invalid", "invalid projection status"),
        ("answer_supported", True, "insufficient evidence has inconsistent answer_supported"),
        ("answer_available", True, "insufficient evidence has inconsistent answer_available"),
        ("support_status", "ok", "insufficient evidence has inconsistent support_status"),
        ("edit_ready", True, "context projection must not authorize edits"),
        ("implementation_guidance", ["Edit without source evidence."],
         "insufficient evidence must not authorize edits"),
        ("diagnostics", {"internal": "not public"}, "forbidden model-visible keys: diagnostics"),
    ):
        tampered = deepcopy(payload)
        tampered[field] = value
        tampered["estimated_tokens"] = estimate_projection_tokens(tampered)
        assert error in validate_model_visible_projection(
            tampered, snapshot={}, max_tokens=budget,
        )
