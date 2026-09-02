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
