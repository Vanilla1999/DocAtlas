"""Eval-only host inputs, never an autonomous-model success claim."""
from copy import deepcopy
import pytest

from eval.evidence_quality_v2.host_control import (
    build_oracle, evidence_envelope, permute, verify_spans, assemble_input,
)


def test_oracle_is_contiguous_and_bound_to_frozen_bytes():
    docs = {'guide.md': 'Before.\nDeploy only after approval.\nAfter.\n'}
    case = {'required_claims': [{'witness_sets': [{'parts': [
        {'path': 'guide.md', 'text': 'Deploy only after approval.', 'line_start': 2, 'line_end': 2}
    ]}]}]}
    sources = build_oracle(case, docs)
    assert len(sources) == 1
    assert sources[0]['snippet'] == 'Deploy only after approval.'
    assert sources[0]['line_start'] == sources[0]['line_end'] == 2
    verify_spans(sources, docs)
    wrong = deepcopy(sources)
    wrong[0]['snippet'] = 'Deploy without approval.'
    with pytest.raises(ValueError, match='span'):
        verify_spans(wrong, docs)


def test_oracle_never_glues_distant_parts_or_silently_drops_one():
    docs = {'a.md': 'first\n' + 'unrelated\n' * 20 + 'last\n'}
    parts = [{'path': 'a.md', 'text': 'first', 'line_start': 1, 'line_end': 1},
             {'path': 'a.md', 'text': 'last', 'line_start': 22, 'line_end': 22}]
    case = {'required_claims': [{'witness_sets': [{'parts': parts}]}]}
    sources = build_oracle(case, docs)
    assert [s['snippet'] for s in sources] == ['first', 'last']
    assert len({s['evidence_id'] for s in sources}) == 2
    case['required_claims'] *= 2
    assert len(build_oracle(case, docs)) == 2  # identical approved spans deduplicate


def test_over_budget_and_unanswerable_oracle_fail_not_truncate():
    with pytest.raises(ValueError, match='unestablished'):
        build_oracle({'required_claims': [{'witness_sets': []}]}, {})
    docs = {'a.md': ' '.join(['important'] * 800)}
    case = {'required_claims': [{'witness_sets': [{'parts': [
        {'path': 'a.md', 'text': docs['a.md'], 'line_start': 1, 'line_end': 1}
    ]}]}]}
    with pytest.raises(ValueError, match='budget'):
        evidence_envelope(build_oracle(case, docs))


def test_order_control_changes_only_order_not_text_or_identity():
    blocks = [{'evidence_id': str(i), 'snippet': str(i)} for i in range(3)]
    old = deepcopy(blocks)
    assert permute(blocks, 'reverse') == old[::-1]
    assert permute(blocks, 'rotate_one') == old[1:] + old[:1]
    assert permute(blocks, 'original') == old
    assert blocks == old
    with pytest.raises(ValueError):
        permute(blocks, 'best-first')


def test_host_input_uses_only_question_and_visible_blocks_not_gold_or_labels():
    blocks = [{'evidence_id': 's', 'snippet': 'Only after approval.'}]
    request = assemble_input('When is deployment allowed?', blocks)
    assert set(request) == {'instructions', 'question', 'context'}
    assert request['question'] == 'When is deployment allowed?'
    assert request['context'] == {'sources': blocks}
    assert not any(key in request for key in ('lane', 'required_claims', 'expected', 'case_id'))
