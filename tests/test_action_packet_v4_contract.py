"""Offline v4 producer and adversarial canonical-binding checks."""
from copy import deepcopy
from dataclasses import replace
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
from docmancer.docs.application._action_packet_part03 import _candidate_source, _mutation_payload, _mutation_requirements
from docmancer.docs.application._action_packet_shared import _compact_value
from docmancer.docs.domain.mutation_intent import MutationIntentContract, RequestedTarget, ResolvedTarget
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






































def _structural_mutation_packet(tmp_path):
    evidence = [{**_evidence("src/component.py", "final_epoch = enabled"),
                 "source_class": "code_graph", "module_path": "src",
                 "collision_free_targets": ["src/new.py"]}]
    packet = build_action_packet(question="epoch", context_pack=evidence,
                                 public_requirements=(evidence[0]["content"],), project_path=str(tmp_path))
    assert packet["completeness"] == "complete"
    evidence_id = packet["sources"][0]["evidence_id"]
    contract = MutationIntentContract("create", "source", (
        RequestedTarget("src/new.py", "path", 0, 10),
    ), destination="src/new.py", resolved_targets=(
        ResolvedTarget("src/new.py", "src/component.py", None, evidence_id,
                       "source", False, True, "parent_context"),
        ResolvedTarget("src/new.py", "src/new.py", None, evidence_id,
                       "source", False, True, "destination_context"),
    ))
    packet["mutation_intent"] = _mutation_payload(contract)
    refresh_action_packet_estimate(packet)
    return packet, evidence, contract



















