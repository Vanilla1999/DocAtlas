"""Whole-owner materialization contracts; N10 is deliberately not part of this run."""
from copy import deepcopy
import hashlib

import pytest

from v2plan import next07_grounded_candidate as candidate
from v2plan.next07_owner_delivery import delivery_spans, materialize_hit, owner_envelope


def hit(raw, start=0, end=None, identity='doc-A'):
    end = len(raw) if end is None else end
    return dict(raw=raw, identity=identity, start=start, end=end,
                content=raw[start:end], source_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                path='guide.md', bm25_order_score=-1.0, retrieval_order=0)


@pytest.mark.parametrize('ending', ['\n', '\r\n'])
@pytest.mark.parametrize('position', ['start', 'middle', 'tail'])
def test_long_owner_includes_original_late_restriction(ending, position):
    raw = ending.join(['# Client', '', 'Client raises `Expired`.', '',
        *['Documentation of behavior.' for _ in range(200)], '',
        'Only when an operation expires.', ''])
    positions = {'start': (0, 15), 'middle': (100, 200), 'tail': (len(raw)-40, len(raw))}
    start, end = positions[position]
    row = hit(raw, start, end)
    before = deepcopy(row)
    result = materialize_hit(row)
    assert result['content'] == raw
    assert (result['start'], result['end']) == (0, len(raw))
    assert result['retrieval_span'] == [start, end]
    assert result['retrieval_content'] == raw[start:end]
    assert result['bm25_order_score'] == row['bm25_order_score']
    assert result['retrieval_order'] == row['retrieval_order']
    assert row == before


def test_half_open_boundary_does_not_include_next_sibling():
    raw = '# A\n\nFirst.\n\n# B\n\nSecond.\n'
    boundary = raw.index('# B')
    assert owner_envelope(raw, 'd', 5, boundary) == (0, boundary)
    assert owner_envelope(raw, 'd', boundary, len(raw)) == (boundary, len(raw))


def test_cross_section_hit_is_contiguous_and_never_stitched():
    raw = '# A\n\nFirst.\n\n# B\n\nSecond.\n\n# C\n\nThird.\n'
    end = raw.index('# C')
    row = materialize_hit(hit(raw, raw.index('First'), raw.index('Second')+3))
    assert row['content'] == raw[:end]
    assert row['owner_spans'] == [[0, raw.index('# B')], [raw.index('# B'), end]]
    assert '# C' not in row['content']


def test_duplicate_headings_bind_by_offsets_not_title():
    raw = '# Same\n\nShared.\n\n# Same\n\nShared.\n'
    second = raw.index('# Same', 1)
    row = materialize_hit(hit(raw, second+8, len(raw)))
    assert (row['start'], row['end']) == (second, len(raw))
    assert row['content'] == raw[second:]


def test_nested_heading_does_not_promote_to_document_root():
    raw = '# Root\n\nIntro.\n\n## Child\n\nValue.\n\n## Sibling\n\nOther.\n'
    start, end = raw.index('## Child'), raw.index('## Sibling')
    row = materialize_hit(hit(raw, start+5, end-2))
    assert (row['start'], row['end']) == (start, end)


def test_fenced_heading_is_not_a_section_boundary():
    raw = '# A\n\n```python\n# a code comment\nx = 1\n```\n\nOnly when enabled.\n'
    assert materialize_hit(hit(raw, raw.index('x ='), raw.index('x =')+5))['content'] == raw


def test_unicode_byte_spans_and_final_newline_are_exact():
    raw = '# Α\n\nα😀.\n\n# Β\r\n\r\nβ😀.\r\n'
    start = raw.index('# Β')
    row = materialize_hit(hit(raw, start+3, len(raw)))
    assert row['content'] == raw[start:]
    assert raw.encode()[row['byte_start']:row['byte_end']] == row['content'].encode()


@pytest.mark.parametrize('start,end', [(-1, 3), (0, 1000), (3, 3), (4, 2), (True, 3), (0, 2.5)])
def test_invalid_hit_coordinates_are_rejected(start, end):
    with pytest.raises(ValueError):
        owner_envelope('# A\ntext', 'd', start, end)


@pytest.mark.parametrize('field,value', [('source_sha256', '0'*64), ('content', 'invented')])
def test_snapshot_or_hit_text_mismatch_does_not_mint_a_unit(field, value):
    row = hit('# A\n\nOriginal.\n')
    row[field] = value
    with pytest.raises(ValueError, match='snapshot'):
        materialize_hit(row)


def test_consumer_recomputes_canonical_units_and_rejects_clipped_tail():
    raw = '# Client\n\nRaises E.\n\nOnly when X.\n'
    spans = delivery_spans(raw, 'd', [(0, 20), (20, len(raw))])
    assert spans == {(0, len(raw))}
    assert (0, 20) not in spans
    changed = raw + 'Additional restriction.\n'
    assert (0, len(raw)) not in delivery_spans(changed, 'd', [(0, 20)])


def test_proposals_rank_search_text_before_materialization(monkeypatch):
    raw = '# Owner\n\n' + ('Body sentence.\n\n' * 400) + 'Only when X.\n'
    indexed, _ = candidate.structural_spans(raw, 'd')
    assert len(indexed) > 1
    observed = {}
    def rank(rows, question):
        observed['spans'] = [(r['start'], r['end']) for r in rows]
        observed['text'] = [r['content'] for r in rows]
        return [{**row, 'bm25_order_score': -float(i+1), 'retrieval_order': i}
                for i, row in enumerate(reversed(rows))]
    monkeypatch.setattr(candidate, 'rank_rows', rank)
    rows, _ = candidate.proposals([dict(raw=raw, identity='d', title='', url='', path='d.md')], 'question')
    assert observed['spans'] == indexed
    assert observed['text'] == [raw[a:b] for a, b in indexed]
    assert [r['retrieval_span'] for r in rows] == [list(x) for x in reversed(indexed)]
    assert [r['retrieval_order'] for r in rows] == list(range(len(indexed)))
    assert [r['bm25_order_score'] for r in rows] == [-float(i+1) for i in range(len(indexed))]
    assert all(r['content'] == raw for r in rows)


def long_document():
    return ('# RelayClient\n\nRelayClient raises `OperationExpired`.\n\n'
        + ('Documentation of the operation lifecycle.\n\n' * 160)
        + 'Only when an operation expires.\n')


def test_real_preparation_and_guards_for_materialized_owner(tmp_path):
    from v2plan.test_next07_grounded_first import prepared_units, decision
    question = 'Which exception does RelayClient raise when an operation expires?'
    raw = long_document()
    rows, _ = prepared_units(tmp_path, {'guide.md': raw}, question)
    accepted = [row for row in rows if decision(row, question).allowed]
    assert accepted
    for row in accepted:
        assert row['snippet'] == raw
        assert row['char_span'] == [0, len(raw)]
        assert row['_reference_evidence']['text'] == raw
    row = accepted[0]
    for mutation in ({'project_identity':'foreign'}, {'freshness':'stale'},
            {'risk_flags':['unsafe']}, {'instruction_risk_flags':['injection']},
            {'generation_id':'wrong'}, {'resolved_version':'wrong'},
            {'path':'another.md'}, {'char_span':[0, 30]}):
        bad = deepcopy(row)
        bad.update(mutation)
        assert not decision(bad, question, row['project_identity']).allowed, mutation
    bad = deepcopy(row)
    bad['_reference_evidence']['raw_document'] += 'changed'
    assert not decision(bad, question).allowed


def test_real_public_owner_packet_preserves_tail_and_validator(tmp_path):
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from eval.project_context_quality.capture_public_context import capture_public_call
    from eval.evidence_quality_v2.audit import audit_payload
    from docmancer.docs.domain.read_delivery_limits import COMPACT_READ_LIMITS
    from v2plan.next07_grounded_public import installed
    raw = long_document()
    root = (tmp_path / 'corpus').resolve()
    write_project(root, {'guide.md': raw})
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, root)
        trace = {}
        with installed(service, trace, delivery_limits=COMPACT_READ_LIMITS):
            capture = capture_public_call(service, dict(project_path=str(root), scope='project',
                question='Which exception does RelayClient raise when an operation expires?'))
    payload = capture['public_payload']
    assert trace['restored'] and not trace.get('exceptions')
    assert trace.get('handler_validation') and all(not e['errors'] for e in trace['handler_validation'])
    assert len(payload['sources']) == 1
    assert payload['sources'][0]['snippet'] == raw
    assert not audit_payload(payload, trace['final_snapshot'], root, delivery_limits=COMPACT_READ_LIMITS)
    assert all(payload[k] is False for k in ('answer_supported', 'answer_available', 'edit_ready'))
