"""Split-module parity, strict binding and facade observation contracts."""
from copy import deepcopy
from pathlib import Path

from docmancer.docs.application import model_visible_projection as projection
from docmancer.docs.application import _model_visible_patch_projection as patch_core
from docmancer.docs.application import _model_visible_docs_support as docs_core
from docmancer.docs.application.action_packet import build_action_packet, refresh_action_packet_estimate




def test_split_preserves_failure_wire_snapshot_validation_and_tamper_rejection():
    packet = build_action_packet(question='Read absent evidence', context_pack=[])
    visible, snapshot = projection.project_patch_context(packet=packet, evidence_items=[])
    assert visible['result'] == 'failure' and visible['edit_ready'] is False
    assert projection.validate_model_visible_projection(visible, snapshot=snapshot) == []
    changed = deepcopy(visible)
    changed['missing'].append('new_reason')
    changed['missing'].sort()
    refresh_action_packet_estimate(changed)
    assert projection.validate_model_visible_projection(changed, snapshot=snapshot)

