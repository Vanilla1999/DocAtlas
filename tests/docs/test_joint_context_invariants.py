"""Joint generation must respect structure, source boundaries and draft recovery."""
from copy import deepcopy
import pytest

from docmancer.docs.application.joint_context_candidates import structural_spans
from docmancer.docs.application.joint_context_selection import unread_lines, packet_alternatives, select_joint_context
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens
from eval.evidence_quality_v2.run import load_protocol, documents_for, audit_payload
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.observer import observe_call


def test_lazy_list_is_one_unit_not_four_word_based_votes():
    raw = '# Guide\n\n* Alpha means\none operation.\n\n* Beta means\ntwo operations.\n\nUnrelated paragraph.\n'
    spans = structural_spans(raw, 0, len(raw))
    lists = [raw[a:b].rstrip() for a, b, kind in spans if kind == 'list']
    assert lists == ['* Alpha means\none operation.\n\n* Beta means\ntwo operations.']


def test_list_does_not_swallow_separate_prose_or_code():
    raw = '* One\n\nSeparate prose.\n\n* Two\n\n```text\n* Not a list\n```\n'
    kinds = [kind for _, _, kind in structural_spans(raw, 0, len(raw))]
    assert kinds == ['list', 'prose', 'list', 'code']


def test_unread_lines_preserves_holes():
    assert unread_lines(1, 100, [(1, 20), (61, 80)]) == [(21, 60), (81, 100)]
    assert unread_lines(1, 10, [(1, 5), (4, 10)]) == []


@pytest.mark.parametrize('span', [(0, 3), (2, 1), (True, 5)])
def test_unread_rejects_invalid_boundaries(span):
    with pytest.raises(ValueError):
        unread_lines(*span, [])


@pytest.fixture
def seed(tmp_path):
    from unittest.mock import patch
    from docmancer.docs.application import joint_context_selection as joint
    _, _, manifest = load_protocol()
    project = tmp_path / 'project'
    docs = documents_for('httpx', manifest)
    write_project(project, docs)
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, project)
        with patch.object(joint, 'select_joint_context', side_effect=lambda p, s, r, **kw: (p, s)):
            payload, trace = observe_call(service, {'question':
                'What do connect, read, write, and pool timeouts each limit in HTTPX?',
                'project_path': str(project), 'scope': 'all'})
    return payload, trace['snapshot'], trace['stages']['projector_inputs'][0], project, docs


def test_full_list_beats_incomplete_alternatives_without_answer_labels(seed):
    payload, snapshot, retrieval, project, docs = seed
    out, bindings = select_joint_context(payload, snapshot, deepcopy(retrieval), max_tokens=800)
    raw = docs['docs/advanced/timeouts.md']
    expected = raw[raw.index('* The **connect**'):raw.index('\n\nYou can configure')]
    assert any(expected in s['snippet'] for s in out['sources'])
    assert audit_payload(out, bindings, project) == []
    assert docs_context_budget_tokens(out) <= 800


def test_draft_range_is_preserved_unless_its_bytes_are_delivered(seed):
    payload, snapshot, retrieval, project, docs = seed
    target = payload['read_next'][0]
    for out, bound, _, _, _ in packet_alternatives(payload, snapshot, retrieval, max_tokens=800):
        visible = [(s['line_start'], s['line_end']) for s in out['sources'] if s['path_or_url'] == target['path']]
        remaining = unread_lines(target['line_start'], target['line_end'], visible)
        assert not remaining or out['read_next'], {'remaining': remaining, 'out': out}


@pytest.mark.parametrize('field,value', [
    ('project_identity', 'other-project'), ('generation_id', 'old-generation'),
    ('resolved_version', 'wrong-version'), ('path', 'other.md'),
    ('_source_snapshot_sha256', 'sha256:' + '0' * 64),
    ('stale', True), ('risk_flags', ['untrusted_instruction']),
    ('lifecycle_status', 'deprecated'),
])
def test_invalid_identity_or_policy_never_expands(seed, field, value):
    payload, snapshot, retrieval, _, _ = seed
    altered = deepcopy(snapshot)
    for row in payload['sources']:
        altered[row['evidence_id']]['source'][field] = value
    out, _ = select_joint_context(payload, altered, deepcopy(retrieval), max_tokens=800)
    assert out == payload


@pytest.mark.parametrize('field', ['raw_document', 'digest', 'char_end', 'missing'])
def test_invalid_snapshot_never_expands(seed, field):
    payload, snapshot, retrieval, _, _ = seed
    altered = deepcopy(snapshot)
    for row in payload['sources']:
        original = altered[row['evidence_id']]['source']
        ref = original['_reference_evidence']
        if field == 'raw_document': ref['raw_document'] += '\nNot indexed.\n'
        elif field == 'digest': ref['source']['content_sha256'] = '0' * 64
        elif field == 'char_end': ref['char_end'] += 1
        else: original.pop('_reference_evidence')
    assert select_joint_context(payload, altered, deepcopy(retrieval), max_tokens=800)[0] == payload


def test_added_text_gets_policy_check_not_only_seed(seed):
    payload, snapshot, retrieval, _, _ = seed
    assert all('acquiring' not in s['snippet'] for s in payload['sources'])
    altered = deepcopy(snapshot)
    for row in payload['sources']:
        source = altered[row['evidence_id']]['source']
        for probe in source.get('retrieval_query_matches', {}).values():
            probe['forbidden_evidence_terms'] = ['acquiring']
    for p, _, _, _, _ in packet_alternatives(payload, altered, retrieval, max_tokens=800):
        assert all('acquiring' not in row['snippet'] for row in p['sources'])


def test_no_trial_reads_or_registers_resources_and_inputs_are_not_mutated(seed, monkeypatch):
    from pathlib import Path
    from docmancer.docs.application.source_continuation import SourceContinuationReader
    payload, snapshot, retrieval, _, _ = seed
    before = deepcopy((payload, snapshot))
    def forbidden(*a, **kw):
        raise AssertionError('candidate evaluation performed I/O or resource registration')
    monkeypatch.setattr(SourceContinuationReader, 'issue', forbidden)
    monkeypatch.setattr(SourceContinuationReader, 'issue_range', forbidden)
    monkeypatch.setattr(Path, 'read_text', forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    assert list(packet_alternatives(payload, snapshot, retrieval, max_tokens=800))
    assert (payload, snapshot) == before


def test_explicit_host_queries_remain_byte_equivalent(seed):
    payload, snapshot, retrieval, _, _ = seed
    changed = deepcopy(retrieval)
    changed['documentation_query_plan']['queries'].append({'origin': 'host_lookup'})
    assert select_joint_context(payload, snapshot, changed, max_tokens=800) == (payload, snapshot)


def test_already_issued_uri_keeps_range_after_new_packet(tmp_path):
    import json
    from unittest.mock import patch
    from docmancer.docs.application import joint_context_selection as joint
    from docmancer.mcp.docs_server import call_docs_tool_payload, read_docs_resource
    _, _, manifest = load_protocol()
    project = tmp_path / 'project'
    write_project(project, documents_for('httpx', manifest))
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, project)
        args = {'question': 'What is the difference between connect, read, write, and pool timeout limits?',
            'project_path': str(project), 'scope': 'all'}
        with patch.object(joint, 'select_joint_context', side_effect=lambda p,s,r,**kw:(p,s)):
            baseline = call_docs_tool_payload('get_docs_context', args, service)
        old = next(s for s in baseline['sources'] if s.get('source_uri'))
        candidate = call_docs_tool_payload('get_docs_context', args, service)
        old_read = json.loads(read_docs_resource(old['source_uri'], service)['text'])
        assert old_read['line_start'] == old['line_end'] + 1
        assert old_read['path'] == old['path_or_url']
        new = next(s for s in candidate['sources'] if s.get('source_uri'))
        new_read = json.loads(read_docs_resource(new['source_uri'], service)['text'])
        assert new_read['line_start'] == new['line_end'] + 1
        assert new_read['status'] in {'complete', 'truncated'}
        assert docs_context_budget_tokens(new_read) <= 600


def test_contiguous_parent_retains_two_seed_occurrences_not_just_their_words(seed):
    from docmancer.docs.application.joint_context_candidates import source_options
    from docmancer.docs.application.joint_context_lineage import retained_seed_mapping
    from docmancer.docs.application.model_visible_projection import _snapshot_entry
    payload, snapshot, _, _, _ = seed
    owner = payload['sources'][1]
    options, _ = source_options(owner, snapshot[owner['evidence_id']]['source'])
    full, original, _ = next(v for v in options if v[2] == 'containing_section')
    trial = {**payload, 'sources': [full]}
    bound = {full['evidence_id']: _snapshot_entry(original, full)}
    mapping = retained_seed_mapping(payload, snapshot, trial, bound)
    assert mapping == {s['evidence_id']: full['evidence_id'] for s in payload['sources']}
    # Same words under a different immutable source are not lineage.
    damaged = deepcopy(bound)
    damaged[full['evidence_id']]['source']['_reference_evidence']['source']['content_sha256'] = '0' * 64
    assert retained_seed_mapping(payload, snapshot, trial, damaged) == {}


@pytest.mark.parametrize('reverse', [False, True])
def test_more_citations_cannot_outvote_completion_of_a_seed(seed, monkeypatch, reverse):
    from docmancer.docs.application import joint_context_selection as joint
    payload, snapshot, retrieval, project, docs = seed
    raw = docs['docs/advanced/timeouts.md']
    block = raw[raw.index('* The **connect**'):raw.index('\n\nYou can configure')]
    candidates = list(packet_alternatives(payload, snapshot, retrieval, max_tokens=800))
    complete = next(c for c in candidates if len(c[0]['sources']) == 1
                    and block in c[0]['sources'][0]['snippet'])
    incomplete = next(c for c in candidates if len(c[0]['sources']) > 1
                      and not any(block in row['snippet'] for row in c[0]['sources']))
    # These are real, independently validated packet alternatives. The chooser
    # receives neither the expected block nor an arbitrary "complete units" label.
    order = [incomplete, complete] if reverse else [complete, incomplete]
    monkeypatch.setattr(joint, 'packet_alternatives', lambda *a, **k: iter(order))
    out, bindings = joint.select_joint_context(payload, snapshot, deepcopy(retrieval), max_tokens=800)
    assert any(block in row['snippet'] for row in out['sources'])
    assert audit_payload(out, bindings, project) == []


def test_coalescing_rechecks_policy_of_every_retained_seed(seed):
    payload, snapshot, retrieval, _, _ = seed
    altered = deepcopy(snapshot)
    code = payload['sources'][0]
    assert 'acquiring' not in code['snippet']
    for probe in altered[code['evidence_id']]['source']['retrieval_query_matches'].values():
        probe['forbidden_evidence_terms'] = ['acquiring']
    for candidate, _, _, _, _ in packet_alternatives(payload, altered, retrieval, max_tokens=800):
        if len(candidate['sources']) == 1:
            assert 'acquiring' not in candidate['sources'][0]['snippet']
