"""Source, budget and lineage controls for complete-block context delivery."""
from copy import deepcopy
from unittest.mock import patch

import pytest

from eval.evidence_quality_v2.run import load_protocol, documents_for, audit_payload
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.application.structural_context_expansion import expand_structural_context
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens


@pytest.fixture
def seed(tmp_path):
    _, _, manifest = load_protocol()
    project = tmp_path / 'project'
    write_project(project, documents_for('httpx', manifest))
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, project)
        with patch('docmancer.docs.application.structural_context_expansion.expand_structural_context',
                   side_effect=lambda payload, snapshot, **kwargs: (payload, snapshot)):
            payload, trace = observe_call(service, {
                'question': 'Назови четыре типа timeout в HTTPX и объясни, что ограничивает каждый.',
                'project_path': str(project), 'scope': 'all',
            })
    return payload, trace['snapshot'], project


def test_expansion_keeps_seed_text_input_objects_and_attribution(seed):
    payload, snapshot, project = seed
    before = deepcopy((payload, snapshot))
    out, bindings = expand_structural_context(payload, snapshot, max_tokens=800, project_root=str(project))
    assert (payload, snapshot) == before
    for source in payload['sources']:
        grown = next(s for s in out['sources'] if s['evidence_id'] == source['evidence_id'])
        assert source['snippet'] in grown['snippet']
        assert source['path_or_url'] == grown['path_or_url']
        assert source['version_binding'] == grown['version_binding']
        assert bool(source.get('source_uri')) == bool(grown.get('source_uri'))
    for field in ('covered_query_ids', 'missing_query_ids', 'facets', 'facet_coverage', 'read_next',
                  'answer_supported', 'answer_available', 'edit_ready'):
        assert out[field] == payload[field]
    assert audit_payload(out, bindings, project) == []
    assert docs_context_budget_tokens(out) <= 800


@pytest.mark.parametrize('field,value', [
    ('project_identity', 'another-project'), ('generation_id', 'old-generation'),
    ('resolved_version', 'wrong-version'), ('_source_snapshot_sha256', 'sha256:' + '0' * 64),
    ('path', 'docs/another.md'), ('stale', True), ('index_freshness', 'stale'),
    ('risk_flags', ['untrusted_instruction']), ('lifecycle_status', 'deprecated'),
])
def test_rejected_source_never_grows(field, value, seed):
    payload, snapshot, project = seed
    snapshot = deepcopy(snapshot)
    for source in payload['sources']:
        snapshot[source['evidence_id']]['source'][field] = value
    out, _ = expand_structural_context(payload, snapshot, max_tokens=800, project_root=str(project))
    assert out == payload


@pytest.mark.parametrize('mutation', ['raw', 'digest', 'scope', 'window', 'oversize', 'missing_reference'])
def test_invalid_or_unbounded_snapshot_never_grows(mutation, seed):
    payload, snapshot, project = seed
    snapshot = deepcopy(snapshot)
    for source in payload['sources']:
        original = snapshot[source['evidence_id']]['source']
        ref = original['_reference_evidence']
        if mutation == 'raw': ref['raw_document'] += '\nInjected.'
        elif mutation == 'digest': ref['source']['content_sha256'] = '0' * 64
        elif mutation == 'scope': ref['source']['scope']['snapshot_id'] = 'other'
        elif mutation == 'window': ref['char_end'] += 1
        elif mutation == 'oversize': ref['raw_document'] = 'x' * 262145
        else: original.pop('_reference_evidence')
    out, _ = expand_structural_context(payload, snapshot, max_tokens=800, project_root=str(project))
    assert out == payload


def test_expansion_does_not_cross_forbidden_text_boundary(seed):
    payload, snapshot, project = seed
    snapshot = deepcopy(snapshot)
    for source in payload['sources']:
        probes = snapshot[source['evidence_id']]['source']['retrieval_query_matches']
        for probe in probes.values():
            probe['forbidden_evidence_terms'] = ['socket connection']
    out, bindings = expand_structural_context(payload, snapshot, max_tokens=800, project_root=str(project))
    assert all('socket connection' not in s['snippet'] for s in out['sources'])
    assert audit_payload(out, bindings, project) == []


def test_no_spare_budget_preserves_existing_quotes(seed):
    payload, snapshot, project = seed
    out, _ = expand_structural_context(payload, snapshot,
        max_tokens=docs_context_budget_tokens(payload), project_root=str(project))
    assert out == payload


@pytest.mark.parametrize('field,value', [
    ('kind', 'docs_answer'), ('support_status', 'insufficient_evidence'),
    ('edit_ready', True), ('answer_supported', True), ('sources', []),
    ('context_quality', {'status': 'checked'}),
])
def test_non_retrieval_or_already_checked_packets_are_unchanged(field, value, seed):
    payload, snapshot, project = seed
    payload = deepcopy(payload)
    payload[field] = value
    assert expand_structural_context(payload, snapshot,
        max_tokens=800, project_root=str(project)) == (payload, snapshot)
