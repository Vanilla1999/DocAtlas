"""Current source/body witnesses must survive only real same-scope evidence."""
from copy import deepcopy
from pathlib import Path
import socket

import pytest

from docmancer.docs.application.docs_context_projection import _requalify_visible_source
from tests.docs._reference_binding_fixtures import capture_reference_case
from tests.docs.test_admission_guard_composition import QUESTION, FACT


@pytest.fixture
def indexed_source(tmp_path):
    cap = capture_reference_case(tmp_path, {'Guide.md': '# Settings\n\n' + FACT}, QUESTION)
    entry = next(iter(cap['projection_attempts'][-1]['snapshot'].values()))
    raw = deepcopy(entry['source'])
    return {
        **raw, 'path_or_url': entry['path_or_url'], 'snippet': entry['snippet'],
        '_qualification_candidate': raw,
        '_expected_project_identity': entry['project_identity'],
    }


def recheck(source):
    return _requalify_visible_source(source, query_text={
        'query-original': QUESTION, 'query-need-1': QUESTION,
        'query-anchor-1': 'RelayClient',
    })['retrieval_query_matches']['query-need-1']


def test_current_indexed_source_keeps_its_typed_witness(indexed_source):
    trace = recheck(indexed_source)
    assert trace['qualified'] and trace['admission_route'] == 'typed_local'
    assert trace['match_ratio'] < 0.4


@pytest.mark.parametrize('snippet', [
    'RelayClient default timeout', 'default timeout is 7 seconds.',
    'RelayClient',
])
def test_crop_cannot_keep_an_old_subject_predicate_or_value_witness(indexed_source, snippet):
    trace = recheck({**indexed_source, 'snippet': snippet})
    assert not trace['qualified']
    assert not trace.get('need_local_witness')
    assert not trace.get('matched_need_ids')


@pytest.mark.parametrize('field,value', [
    ('project_identity', 'foreign'), ('generation_id', 'other-snapshot'),
    ('resolved_version', '99.0'), ('path_or_url', 'Other.md'),
    ('freshness', 'stale'),
])
def test_identical_body_does_not_carry_approval_across_source_switch(indexed_source, field, value):
    trace = recheck({**indexed_source, field: value})
    assert not trace['qualified']
    assert not trace.get('need_local_witness')


def test_requalification_reads_no_new_files_or_network(indexed_source, monkeypatch):
    assert recheck(indexed_source)['qualified']  # prime ordinary imports first
    def forbidden(*args, **kwargs):
        raise AssertionError('admission/projector performed I/O')
    monkeypatch.setattr('builtins.open', forbidden)
    monkeypatch.setattr(Path, 'open', forbidden)
    monkeypatch.setattr(Path, 'read_text', forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    assert recheck(indexed_source)['qualified']
