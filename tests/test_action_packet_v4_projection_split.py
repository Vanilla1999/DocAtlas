"""Split-module parity, strict binding and facade observation contracts."""
from copy import deepcopy
from pathlib import Path

from docmancer.docs.application import model_visible_projection as projection
from docmancer.docs.application import _model_visible_patch_projection as patch_core
from docmancer.docs.application import _model_visible_docs_support as docs_core
from docmancer.docs.application.action_packet import build_action_packet, refresh_action_packet_estimate


def test_projection_split_modules_and_context_handler_are_below_line_limit():
    root = Path(projection.__file__).resolve().parents[1]
    paths = [Path(module.__file__) for module in (projection, patch_core, docs_core)]
    paths.append(root / 'interfaces' / 'mcp' / 'context_tools.py')
    for path in paths:
        assert len(path.read_text().splitlines()) <= 1000


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


def test_split_patch_core_resolves_public_validator_at_call_time(monkeypatch):
    packet = build_action_packet(question='Read absent evidence', context_pack=[])
    visible, snapshot = projection.project_patch_context(packet=packet, evidence_items=[])
    calls = []
    def observed(*args, **kwargs):
        calls.append(kwargs)
        return ['observed strict validator']
    monkeypatch.setattr(projection, 'validate_action_packet', observed)
    assert projection.validate_model_visible_projection(visible, snapshot=snapshot) == ['observed strict validator']
    assert len(calls) == 1 and 'evidence_items' in calls[0]


def test_split_docs_core_resolves_public_digest_and_limitation_hooks(monkeypatch):
    monkeypatch.setattr(projection, '_source_digest', lambda _: 'a' * 64)
    source = projection._docs_source({'path': 'docs/a.md', 'content': 'Exact rule.'})
    assert source['content_sha256'] == 'a' * 64
    monkeypatch.setattr(projection, '_needs_actionable_limitation', lambda *_: False)
    answer, refs, limited = projection._answer_text('Rule?', {}, [source])
    assert answer == 'Exact rule.' and refs == [source['evidence_id']] and limited is False
    assert projection._docs_source({'path': 'docs/a.md', 'content': 'x' * 3001}) is None
