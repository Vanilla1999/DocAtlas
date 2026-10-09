"""Current source/body witnesses must survive only real same-scope evidence."""
from copy import deepcopy
from pathlib import Path
import socket

import pytest

from docmancer.docs.application.docs_context_projection import _requalify_visible_source
from tests.docs._current_source_guard_fixtures import (
    capture_source_case, source_binding, assert_visible_fact, source_contains_fact,
)
from tests.docs.test_admission_guard_composition import QUESTION, FACT


@pytest.fixture
def indexed_source(tmp_path):
    cap = capture_source_case(tmp_path, {'Guide.md': '# Settings\n\n' + FACT}, QUESTION, lookups=(FACT,))
    public, original, _ = source_binding(cap, 'Guide.md', FACT)
    raw = deepcopy(original)
    return {
        **raw, 'path_or_url': public['path_or_url'], 'snippet': public['snippet'],
        '_qualification_candidate': raw,
        '_expected_project_identity': public['project_identity'],
    }


def requalify(source):
    return _requalify_visible_source(source, query_text={
        'query-original': QUESTION, 'query-lookup-1': FACT,
    })


def recheck(source):
    return requalify(source)['retrieval_query_matches']['query-lookup-1']


def test_current_indexed_source_keeps_explicit_lookup_without_original_credit(indexed_source):
    trace = recheck(indexed_source)
    assert trace['qualified']
    assert trace['query_origin'] == 'host_lookup'
    assert trace.get('public_parent_query_id') is None
    assert not trace.get('need_local_witness')
    assert not trace.get('matched_need_ids')
    assert FACT in indexed_source['snippet']


@pytest.mark.parametrize('snippet', [
    'RelayClient default timeout', 'default timeout is 7 seconds.',
    'RelayClient',
])
def test_crop_cannot_keep_old_semantic_credit_or_pass_the_original_fact_oracle(indexed_source, snippet):
    assert source_contains_fact(requalify(indexed_source), 'Guide.md', FACT)
    returned = requalify({**indexed_source, 'snippet': snippet})
    trace = returned['retrieval_query_matches']['query-lookup-1']
    # A partial literal match is retrieval context, never proof of the full fact.
    # Do not recreate the retired subject/predicate inference in the qualifier.
    assert not trace.get('need_local_witness')
    assert not trace.get('matched_need_ids')
    assert trace.get('admission_route') != 'typed_local'
    assert trace.get('public_parent_query_id') is None
    assert not source_contains_fact(returned, 'Guide.md', FACT)
    assert all(returned.get(key) is not True for key in ('answer_supported', 'answer_available', 'edit_ready'))


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


def test_original_question_still_delivers_the_authored_fact(tmp_path):
    # Kept separate from the seeded boundary controls: an original-only product
    # regression remains red if the unmodified question still loses its source.
    cap = capture_source_case(tmp_path, {'Guide.md': '# Settings\n\n' + FACT}, QUESTION)
    assert_visible_fact(cap, 'Guide.md', FACT)
