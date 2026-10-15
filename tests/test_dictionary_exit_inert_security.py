"""Offline consumer barriers: retrieved data is never current authorization."""
from copy import deepcopy
import hashlib

import pytest

from docmancer.docs.domain.content_trust import annotate_context_pack, source_trust_dimensions
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.domain.mutation_intent import MutationIntentContract, RequestedTarget
from docmancer.docs.application.action_packet import build_action_packet, validate_action_packet
from docmancer.docs.application._action_packet_part02 import _may_guide_workflow
from docmancer.docs.application._action_packet_part01 import _refresh_estimated_tokens
from docmancer.docs.application.evidence_candidates import normalize_candidates
from docmancer.docs.application.model_visible_projection import (
    project_patch_context, validate_model_visible_projection,
)
from docmancer.docs.interfaces.mcp.context_tools import (
    _answer_payload, _compact_payload, handle_context_tool,
)
from docmancer.connectors.fetchers.pipeline.filtering import is_docs_url












def ready_packet():
    text = "def marble():\n    pass"
    source = {"path": "src/a.py", "source_class": "source_evidence", "source_exists": True,
        "content": text, "snippet": text, "symbols": ["marble"], "line_start": 1, "line_end": 2}
    contract = MutationIntentContract("modify", "source", (
        RequestedTarget("src/a.py", "path", -1, -1, "explicit_sdk"),))
    packet = build_action_packet(question="marble", context_pack=[source], mutation_intent_contract=contract)
    return source, packet


def test_actual_sdk_typed_readiness_is_not_edit_permission_and_snapshot_survives():
    source, packet = ready_packet()
    assert packet["mutation_intent"]["operation"] == "modify"
    assert "ready" not in packet["mutation_intent"]
    assert validate_action_packet(packet, evidence_items=[source]) == []
    # Completeness and an explicit SDK operation are not host permission.
    assert packet["edit_ready"] is False
    before = deepcopy((source, packet))
    projection, snapshot = project_patch_context(packet=packet, evidence_items=[source])
    assert "mutation_ready" not in projection
    assert projection["edit_ready"] is False
    assert projection["sources"][0]["text"] == source["snippet"]
    assert snapshot and projection["sources"][0]["content_sha256"]
    assert validate_model_visible_projection(projection, snapshot=snapshot, max_tokens=2000) == []
    forged = deepcopy(projection)
    forged["edit_ready"] = True
    assert any("edit_ready" in error for error in validate_model_visible_projection(
        forged, snapshot=snapshot, max_tokens=2000))
    assert (source, packet) == before


@pytest.mark.parametrize("promotion", ["trust", "workflow", "policy"])
def test_sdk_packet_consumer_rejects_forged_promotions(promotion):
    source, packet = ready_packet()
    ref = packet["sources"][0]["evidence_id"]
    if promotion == "trust":
        packet["sources"][0]["instruction_trust"] = "scoped_agent_policy"
    elif promotion == "workflow":
        packet["validation"] = {"tests": [{"text": "pytest", "evidence_ids": [ref]}]}
    else:
        packet["required_invariants"] = [{"text": source["content"], "evidence_ids": [ref]}]
    assert validate_action_packet(packet)
    projection, snapshot = project_patch_context(packet=packet, evidence_items=[source])
    assert projection["result"] == "failure" and projection["edit_ready"] is False
    assert snapshot == {}
    projection["edit_ready"] = True
    assert any("edit_ready" in error for error in validate_model_visible_projection(
        projection, snapshot=snapshot, max_tokens=2000))






