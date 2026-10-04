"""Contract checks for optional read limits and exact source serialization.

Packing tests stub only read_decision: they exercise serialization, not source
eligibility or retrieval quality. The public integration smoke is a separate run.
"""
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from docmancer.docs.domain.read_delivery_limits import (
    COMPACT_READ_LIMITS, ReadDeliveryLimits, current_read_delivery_limits,
    use_read_delivery_limits,
)
from docmancer.docs.domain.source_coordinates import source_line_range, source_line_text
from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application.model_visible_projection import (
    _docs_source, _snapshot_entry, _refresh_estimate, validate_model_visible_projection,
)
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
from eval.evidence_quality_v2.audit import audit_payload
from v2plan import next07_grounded_public as wiring


@pytest.mark.parametrize('ending', ['\n', '\r\n', '\r'])
@pytest.mark.parametrize('final_newline', [True, False])
def test_exact_line_endings(ending, final_newline):
    raw = ending.join(['# Owner', '', 'Fact 😀.']) + (ending if final_newline else '')
    assert source_line_range(raw, 0, len(raw)) == (1, 3)
    assert source_line_text(raw, 1, 3) == raw
    start = raw.index('Fact')
    assert source_line_range(raw, start, len(raw)) == (3, 3)
    assert raw[start:len(raw)] in source_line_text(raw, 3, 3)


@pytest.mark.parametrize('start,end', [(0, 0), (-1, 2), (3, 2), (0, 100), (False, 2)])
def test_invalid_character_coordinates(start, end):
    with pytest.raises(ValueError):
        source_line_range('text\n', start, end)


@pytest.mark.parametrize('start,end', [(0, 1), (1, 3), (2, 1), (True, 1)])
def test_invalid_line_coordinates(start, end):
    with pytest.raises(ValueError):
        source_line_text('a\nb\n', start, end)


@pytest.mark.parametrize('field', ['max_tokens', 'max_sources', 'max_snippet_chars', 'max_transport_bytes'])
@pytest.mark.parametrize('bad', [0, -1, True, 1.5])
def test_limits_are_positive_or_absent(field, bad):
    with pytest.raises(ValueError):
        ReadDeliveryLimits(**{field: bad})


def test_limits_are_scoped_and_restore_on_exception():
    assert current_read_delivery_limits() is None
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        assert asdict(current_read_delivery_limits()) == dict(
            max_tokens=None, max_sources=None, max_snippet_chars=None, max_transport_bytes=None)
        with pytest.raises(RuntimeError):
            with use_read_delivery_limits(ReadDeliveryLimits(max_tokens=100)):
                raise RuntimeError('scope canary')
        assert current_read_delivery_limits() is COMPACT_READ_LIMITS
    assert current_read_delivery_limits() is None


def test_payload_cannot_select_limits():
    assert current_read_delivery_limits() is None
    with pytest.raises(TypeError):
        with use_read_delivery_limits({'max_tokens': None}):
            pass


def row_for(text, path='guide.md'):
    return dict(path=path, title='Owner', heading_path='Owner', content=text,
        display_text=text, snippet=text, source_class='project_doc', authority='source_of_truth',
        project_identity='project-A', doc_scope='project', line_start=1,
        line_end=len(text.splitlines()), char_span=[0, len(text)],
        _reference_evidence=dict(raw_document=text, char_start=0, char_end=len(text),
            source=dict(document_id='source:'+path, scope=dict(snapshot_id='s1',
                project_id='project-A', version=''), canonical_path=path)))


def projected(row, *, unlimited=False):
    kwargs = {'max_snippet_chars': None} if unlimited else {}
    source = _docs_source(row, display_snippet=row['snippet'], **kwargs)
    assert source is not None
    source.update(snippet=row['snippet'], project_identity=row['project_identity'],
        authority=row['authority'], scope=row['doc_scope'],
        line_start=row['line_start'], line_end=row['line_end'])
    return source, _snapshot_entry(row, source)


@pytest.mark.parametrize('use_compact', [False, True])
def test_empty_selection_is_valid_insufficient(use_compact):
    def check():
        payload = _payload([])
        assert payload['status'] == 'insufficient_evidence'
        assert payload['sources'] == []
        assert payload['context_available'] is False
        assert all(payload[k] is False for k in ('answer_supported', 'answer_available', 'edit_ready'))
        assert not validate_model_visible_projection(payload, snapshot={}, max_tokens=800)
    if use_compact:
        with use_read_delivery_limits(COMPACT_READ_LIMITS):
            check()
    else:
        check()


@pytest.mark.parametrize('ending', ['\n', '\r\n', '\r'])
@pytest.mark.parametrize('final_newline', [True, False])
def test_audit_does_not_destroy_source_line_endings(tmp_path, ending, final_newline):
    raw = ending.join(['# Owner', '', 'A fact.']) + (ending if final_newline else '')
    (tmp_path/'guide.md').write_bytes(raw.encode())
    row = row_for(raw)
    src, snap = projected(row)
    assert audit_payload(_payload([src]), {src['evidence_id']: snap}, tmp_path) == []


@pytest.mark.parametrize('mutation', ['shifted_lines', 'beyond_eof', 'foreign_path', 'altered_text', 'wrong_hash'])
def test_audit_still_rejects_damage(tmp_path, mutation):
    raw = '# Owner\n\nA fact.\n'
    (tmp_path/'guide.md').write_bytes(raw.encode())
    row = row_for(raw)
    src, snap = projected(row)
    payload = _payload([src]); source = payload['sources'][0]
    if mutation == 'shifted_lines': source.update(line_start=2)
    elif mutation == 'beyond_eof': source.update(line_end=20)
    elif mutation == 'foreign_path': source.update(path_or_url='../other.md')
    elif mutation == 'altered_text': source.update(snippet='invented')
    else: source.update(content_sha256='0'*64)
    _refresh_estimate(payload)
    assert audit_payload(payload, {src['evidence_id']: snap}, tmp_path)


def many_packet():
    pairs = [projected(row_for('# Owner\n\n' + 'Relevant original material. '*90 + '\n', f'{i}.md'))
             for i in range(4)]
    payload = _payload([s for s,_ in pairs])
    snapshot = {s['evidence_id']: snap for s,snap in pairs}
    return payload, snapshot


def test_compact_removes_only_read_size_limits():
    payload, snapshot = many_packet()
    assert docs_context_budget_tokens(payload) > 800
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800)
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800) == []
    assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800)


@pytest.mark.parametrize('damage', ['estimate', 'hash', 'snapshot', 'credit', 'edit', 'forbidden'])
def test_compact_never_filters_nonbudget_validation_errors(damage):
    payload, snapshot = many_packet()
    if damage == 'estimate': payload['estimated_tokens'] += 1
    elif damage == 'hash': payload['sources'][0]['content_sha256'] = '0'*64
    elif damage == 'snapshot': snapshot.clear()
    elif damage == 'credit': payload['answer_supported'] = True
    elif damage == 'edit': payload['edit_ready'] = True
    else: payload['context_pack'] = []
    if damage != 'estimate': _refresh_estimate(payload)
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        assert validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800)


def test_compact_does_not_change_answer_or_patch_limits():
    payload, snapshot = many_packet()
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        for kind in ('docs_answer', 'patch_context'):
            other = deepcopy(payload); other['kind'] = kind; _refresh_estimate(other)
            errors = validate_model_visible_projection(other, snapshot=snapshot, max_tokens=800)
            assert 'projection estimate mismatch or budget exceeded' in errors


def test_large_source_limit_is_explicit_not_globally_disabled():
    row = row_for('# Owner\n\n' + 'A'*3100 + '\n')
    assert _docs_source(row, display_snippet=row['snippet']) is None
    assert _docs_source(row, display_snippet=row['snippet'], max_snippet_chars=None) is not None


@pytest.fixture
def permit_read_for_packing_only(monkeypatch):
    # This spy deliberately does not test source eligibility or read semantics.
    monkeypatch.setattr(wiring, 'read_decision', lambda *a, **k: SimpleNamespace(
        allowed=True, reason='serialization-test-only'))


def test_packer_delivers_four_whole_sources_over_800(permit_read_for_packing_only):
    rows = [row_for('# Owner\n\n' + 'A'*3100 + '\n', f'{i}.md') for i in range(4)]
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        trace = {}
        payload, snapshot = wiring.first_fit(rows, 'question', 'project-A', trace)
        assert len(payload['sources']) == 4
        assert docs_context_budget_tokens(payload) > 800
        assert [s['snippet'] for s in payload['sources']] == [r['snippet'] for r in rows]
        assert trace['validator'] == []
        assert not validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800)
        assert all(e['stage'] == 'selected' for e in trace['decisions'])


def test_empty_packer_keeps_semantic_unknown_separate(permit_read_for_packing_only):
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        payload, snapshot = wiring.first_fit([], 'question', 'project-A', {})
        assert payload['status'] == 'insufficient_evidence'
        assert snapshot == {}


def test_no_source_guard_bypass_when_all_rows_rejected(monkeypatch):
    monkeypatch.setattr(wiring, 'read_decision', lambda *a, **k: SimpleNamespace(
        allowed=False, reason='unsafe_evidence'))
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        trace = {}
        payload, _ = wiring.first_fit([row_for('# Owner\n\nFact.\n')], 'question', 'project-A', trace)
        assert payload['status'] == 'insufficient_evidence'
        assert trace['decisions'][0]['reason'] == 'unsafe_evidence'


def test_packer_rejects_wrong_coordinates_not_repairs_them(permit_read_for_packing_only):
    row = row_for('# Owner\n\nFact.\n'); row['line_start'] = 2
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        trace = {}
        payload, _ = wiring.first_fit([row], 'question', 'project-A', trace)
        assert payload['status'] == 'insufficient_evidence'
        assert trace['decisions'][0]['reason'] == 'source_coordinate_mismatch'


def test_exact_duplicate_is_not_returned_twice(permit_read_for_packing_only):
    row = row_for('# Owner\n\nFact.\n')
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        trace = {}
        payload, _ = wiring.first_fit([row, deepcopy(row)], 'question', 'project-A', trace)
        assert len(payload['sources']) == 1
        assert trace['decisions'][1]['stage'] == 'duplicate_contained'


def test_same_text_at_distinct_offsets_has_distinct_citation_ids(permit_read_for_packing_only):
    text = '# Owner\n\nFact.\n'
    raw = text + text
    first = row_for(text)
    first['_reference_evidence']['raw_document'] = raw
    second = deepcopy(first)
    second['char_span'] = [len(text), len(raw)]
    second['line_start'], second['line_end'] = source_line_range(raw, *second['char_span'])
    with use_read_delivery_limits(COMPACT_READ_LIMITS):
        payload, snapshot = wiring.first_fit([first, second], 'question', 'project-A', {})
        assert len(payload['sources']) == 2
        assert len(snapshot) == 2
        assert payload['sources'][0]['evidence_id'] != payload['sources'][1]['evidence_id']


def test_offline_audit_accepts_only_explicit_caller_policy(tmp_path):
    payload, snapshot = many_packet()
    for src in payload['sources']:
        (tmp_path/src['path_or_url']).write_bytes(src['snippet'].encode())
    assert audit_payload(payload, snapshot, tmp_path)
    assert audit_payload(payload, snapshot, tmp_path, delivery_limits=COMPACT_READ_LIMITS) == []
    assert current_read_delivery_limits() is None


def test_installed_restores_policy_after_exception():
    service = SimpleNamespace(get_project_context=lambda *a, **k: None,
        unified_context=SimpleNamespace(get_docs_context=lambda *a, **k: None))
    trace = {}
    with pytest.raises(RuntimeError, match='canary'):
        with wiring.installed(service, trace, delivery_limits=COMPACT_READ_LIMITS):
            assert current_read_delivery_limits() is COMPACT_READ_LIMITS
            raise RuntimeError('canary')
    assert trace['restored'] is True
    assert current_read_delivery_limits() is None


def test_named_compact_runner_policy_does_not_weaken_fact_checks(monkeypatch):
    from v2plan import next07_grounded_final_run as runner
    docs = {'default.md': '# LeaseClient\n\nThe default timeout is 17 seconds.\n',
            'error.md': '# LeaseClient\n\nAn expired operation raises `LeaseExpired`.\n'}
    payload = dict(kind='docs_context', sources=[dict(path_or_url=k, snippet=v) for k,v in docs.items()],
        answer_supported=False, answer_available=False, edit_ready=False, support_status='retrieval_only')
    trace = dict(projection_calls=1, handler_validation=[{'errors': []}], validator=[], restored=True)
    monkeypatch.setattr(runner, 'docs_context_budget_tokens', lambda p: 1600)
    assert not runner._assess_capture({'public_payload': payload}, trace, docs, 17, 'LeaseExpired')['passed']
    assert runner._assess_capture({'public_payload': payload}, trace, docs, 17, 'LeaseExpired',
        delivery_limits=COMPACT_READ_LIMITS)['passed']
    payload['sources'][1]['snippet'] = 'LeaseExpired'
    assert not runner._assess_capture({'public_payload': payload}, trace, docs, 17, 'LeaseExpired',
        delivery_limits=COMPACT_READ_LIMITS)['passed']
