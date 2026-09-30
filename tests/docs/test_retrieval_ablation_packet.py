"""Native whole-unit delivery through real source/reference/DTO boundaries."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.retrieval_ablation.run import _native_fixture, PROTOCOL
from docmancer.docs.application.model_visible_projection import (
    docs_context_budget_tokens, validate_model_visible_projection,
)


def input_fixture(tmp_path, documents=None):
    corpus = tmp_path / 'corpus'
    corpus.mkdir()
    documents = documents or {'retry.md': '# Retry\n\nThe retry budget is three attempts. Do not retry cancellation.\n'}
    for name, text in documents.items():
        path = corpus / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    spec = {'schema_version': 1, 'sources': [
        {'path': name, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
        for name, text in documents.items()]}
    return corpus, spec, json.loads(PROTOCOL.read_bytes())


def test_native_fixture_delivers_audited_whole_units_without_answer_authority(tmp_path):
    corpus, spec, protocol = input_fixture(tmp_path)
    result = _native_fixture(corpus, spec, {'question': 'What is the retry budget?'}, protocol)
    packet = result['model_visible_packet']
    assert isinstance(packet, dict), result['packet_status']
    assert packet['kind'] == 'docs_context'
    assert packet['answer_supported'] is False and packet['answer_available'] is False
    assert packet['edit_ready'] is False
    assert packet['sources']
    assert packet['sources'][0]['snippet'] == (corpus / 'retry.md').read_text().strip()
    assert docs_context_budget_tokens(packet) <= 800
    assert validate_model_visible_projection(packet, snapshot=result['packet_snapshot'], max_tokens=800) == []
    assert result['audit_errors'] == []
    assert result['quality_status'] == 'UNJUDGED'


def test_whole_unit_packet_never_calls_custom_ordering_or_product_projector(tmp_path):
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.docs.application import context_candidate_ranking, docs_context_projection
    corpus, spec, protocol = input_fixture(tmp_path)
    with patch.object(SQLiteStore, 'query', side_effect=AssertionError('custom query')), \
         patch.object(SQLiteStore, '_ranking_candidate', side_effect=AssertionError('custom ranking')), \
         patch.object(context_candidate_ranking, '_facet_aware_candidates', side_effect=AssertionError('custom preference')), \
         patch.object(docs_context_projection, 'project_docs_context', side_effect=AssertionError('full projector')):
        result = _native_fixture(corpus, spec, {'question': 'retry budget'}, protocol)
    assert result['model_visible_packet'] is not None


def test_empty_native_packet_is_insufficient_not_ready(tmp_path):
    corpus, spec, protocol = input_fixture(tmp_path)
    result = _native_fixture(corpus, spec, {'question': 'zzzzzzzzz'}, protocol)
    packet = result['model_visible_packet']
    assert isinstance(packet, dict)
    assert packet['status'] == 'insufficient_evidence'
    assert not packet.get('sources')
    assert packet['answer_supported'] is False
    assert packet['edit_ready'] is False
    assert validate_model_visible_projection(packet, snapshot=result['packet_snapshot'], max_tokens=800) == []


from contextlib import contextmanager


@contextmanager
def indexed_case(tmp_path, documents=None):
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from docmancer.core.sqlite_store import SQLiteStore
    from experiments.retrieval_ablation.adapters import native_diagnostic
    documents = documents or {'retry.md': '# Retry\n\nThe retry budget is three attempts. Do not retry cancellation.\n'}
    project = tmp_path / 'project'
    write_project(project, documents)
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, project)
        store = SQLiteStore(config.index.db_path)
        with store._connect() as conn:
            identity = conn.execute('SELECT project_identity FROM retrieval_children LIMIT 1').fetchone()[0]
        filters = {'project_identity': identity, 'project_path': str(project),
                   'source_class': 'project_file', 'project_docs': True, 'doc_scope': 'project', 'resolved_version': ''}
        yield store, documents, filters, project


def _native(store, documents, filters, question='retry budget'):
    from experiments.retrieval_ablation.adapters import native_diagnostic
    return native_diagnostic(store, [question], filters=filters, sources=documents)


@pytest.mark.parametrize('change', [
    {'project_identity': 'foreign'}, {'resolved_version': '2'}, {'stale': True},
    {'index_freshness': 'stale'}, {'risk_flags': ['unsafe']},
    {'lifecycle_status': 'superseded'}, {'doc_scope': 'module'},
    {'source_class': 'library_doc'}, {'project_docs': False},
])
def test_strong_forbidden_source_never_reaches_native_packet(tmp_path, change):
    from docmancer.core.models import Document
    from experiments.retrieval_ablation.packet import pack_native
    with indexed_case(tmp_path) as (store, docs, filters, project):
        docs['foreign.md'] = '# Retry budget\n\n' + ('retry budget ' * 25)
        (project / 'foreign.md').write_text(docs['foreign.md'])
        metadata = {**filters, 'format': 'markdown', 'source_path': 'foreign.md',
            'authority': 'source_of_truth', 'resolved_version': '', **change}
        store.add_documents([Document(source=str(project/'foreign.md'), content=docs['foreign.md'], metadata=metadata)])
        filters = {**filters, 'resolved_version': ''}
        assert any(row['source'].endswith('foreign.md') for row in store._search_rows('retry budget', 40))
        native = _native(store, docs, filters)
        before = deepcopy(native)
        result = pack_native(store, native, sources=docs, question='retry budget')
        assert native == before
        assert native['policy_rejections']
        assert {s['path_or_url'] for s in result['model_visible_packet']['sources']} == {'retry.md'}


@pytest.mark.parametrize('field,value', [('display_text', 'fabricated quote'),
    ('char_end', 999999), ('display_content_hash', 'wrong'), ('source_identity', 'foreign')])
def test_packet_refuses_native_rows_changed_after_retrieval(tmp_path, field, value):
    from experiments.retrieval_ablation.packet import pack_native
    with indexed_case(tmp_path) as (store, docs, filters, _):
        native = _native(store, docs, filters)
        native['candidates'][0]['row'][field] = value
        with pytest.raises(ValueError, match='candidate changed|canonical'):
            pack_native(store, native, sources=docs, question='retry budget')


def test_packet_revalidates_source_policy_after_rendering(tmp_path, monkeypatch):
    from experiments.retrieval_ablation import packet
    with indexed_case(tmp_path) as (store, docs, filters, _):
        native = _native(store, docs, filters)
        render = packet._render
        def revoke(*args, **kwargs):
            result = render(*args, **kwargs)
            with store._connect() as conn:
                conn.execute("UPDATE retrieval_children SET metadata_json=json_set(metadata_json, '$.risk_flags', json('[\"unsafe\"]'))")
            return result
        monkeypatch.setattr(packet, '_render', revoke)
        with pytest.raises(ValueError, match='candidate changed|eligibility'):
            packet.pack_native(store, native, sources=docs, question='retry budget')


def test_packet_does_not_accept_a_self_consistent_old_snapshot(tmp_path):
    from experiments.retrieval_ablation.packet import pack_native
    with indexed_case(tmp_path) as (store, docs, filters, _):
        native = _native(store, docs, filters)
        docs['retry.md'] = docs['retry.md'].replace('three', 'five')
        with pytest.raises(ValueError, match='candidate changed|canonical'):
            pack_native(store, native, sources=docs, question='retry budget')


def test_soft_overlap_bypass_does_not_forge_qualification(tmp_path):
    from experiments.retrieval_ablation.packet import pack_native
    question = 'retry budget coconut nebula galaxy'
    with indexed_case(tmp_path) as (store, docs, filters, _):
        native = _native(store, docs, filters, question)
        simple = pack_native(store, native, sources=docs, question=question)
        gated = pack_native(store, native, sources=docs, question=question, soft_gate=True)
        assert simple['model_visible_packet']['sources']
        trace = simple['prepared_candidates'][0]['retrieval_query_matches']['query-original']
        assert trace['qualified'] is False
        assert trace['qualification_reason'] == 'insufficient_visible_match'
        assert simple['prepared_candidates'] == gated['prepared_candidates']
        assert gated['model_visible_packet']['status'] == 'insufficient_evidence'
        assert gated['packet_omissions'][0]['reason'] == 'legacy_soft_gate'


def test_soft_overlap_bypass_does_not_bypass_exact_identity(tmp_path):
    from experiments.retrieval_ablation.packet import pack_native
    question = 'method Widget.retry budget coconut nebula galaxy'
    docs = {'retry.md': '# Other.retry\n\nThe retry budget is three attempts.\n'}
    with indexed_case(tmp_path, docs) as (store, docs, filters, _):
        native = _native(store, docs, filters, question)
        assert native['candidates']
        result = pack_native(store, native, sources=docs, question=question)
        assert result['model_visible_packet']['status'] == 'insufficient_evidence'
        assert result['packet_rejections']


def test_packet_source_locator_is_bound_to_actual_catalog(tmp_path):
    from experiments.retrieval_ablation.packet import pack_native
    docs = {'wanted.md': '# Overview\n\nUnrelated instructions.\n',
            'wrong.md': '# Retry\n\nThe retry budget is three attempts.\n'}
    question = 'In file wanted.md, what is the retry budget?'
    with indexed_case(tmp_path, docs) as (store, docs, filters, _):
        native = _native(store, docs, filters, question)
        result = pack_native(store, native, sources=docs, question=question)
        assert all(row['path_or_url'] != 'wrong.md' for row in result['model_visible_packet'].get('sources', []))
        assert any(any(t['qualification_reason'] == 'source_locator_mismatch' for t in row['qualification'].values())
                   for row in result['packet_rejections'])


def test_packet_skips_oversized_unit_and_preserves_later_whole_unit(tmp_path):
    from experiments.retrieval_ablation.packet import pack_native
    docs = {'large.md': '# Retry\n\n' + ('Retry budget is a documented constraint. ' * 27),
            'small.md': '# Retry\n\nThe retry budget is three attempts.\n'}
    with indexed_case(tmp_path, docs) as (store, docs, filters, _):
        native = _native(store, docs, filters)
        # A deliberate saved-order packing fixture, not a retrieval ranking claim.
        native['candidates'].sort(key=lambda c: (not c['row']['source'].endswith('large.md'), c['rank_in_lane']))
        result = pack_native(store, native, sources=docs, question='retry budget', max_tokens=400)
        assert any(row['path_or_url'] == 'small.md' for row in result['model_visible_packet']['sources'])
        assert any(row['reason'] == 'whole_unit_token_budget' for row in result['packet_omissions'])
        assert docs_context_budget_tokens(result['model_visible_packet']) <= 400


def test_real_packet_audit_checks_final_disk_spans(tmp_path):
    from eval.evidence_quality_v2.run import audit_payload
    from experiments.retrieval_ablation.packet import pack_native
    with indexed_case(tmp_path) as (store, docs, filters, project):
        result = pack_native(store, _native(store, docs, filters), sources=docs, question='retry budget')
        assert audit_payload(result['model_visible_packet'], result['packet_snapshot'], project) == []
        tampered = deepcopy(result['model_visible_packet'])
        tampered['sources'][0]['snippet'] += ' Fabricated.'
        assert audit_payload(tampered, result['packet_snapshot'], project)


def test_native_fixture_runs_real_final_disk_audit(tmp_path):
    from eval.evidence_quality_v2 import run as evaluator
    corpus, spec, protocol = input_fixture(tmp_path)
    with patch.object(evaluator, 'audit_payload', wraps=evaluator.audit_payload) as audit:
        result = _native_fixture(corpus, spec, {'question': 'retry budget'}, protocol)
    assert audit.call_count == 1
    assert result['audit_errors'] == []


def test_root_source_locator_filters_before_native_exposure(tmp_path):
    docs = {'wanted.md': '# Retry\n\nA bounded retry budget.\n',
            'wrong.md': '# Retry budget\n\n' + ('retry budget ' * 40)}
    corpus, spec, protocol = input_fixture(tmp_path, docs)
    protocol['raw_hits'] = 1
    result = _native_fixture(corpus, spec, {'question': 'In file wanted.md, what is the retry budget?'}, protocol)
    assert result['candidates']
    assert all(row['row']['source'].endswith('wanted.md') for row in result['candidates'])
    assert result['root_reference_plan']['references'][0]['state'] == 'resolved'
    assert result['audit_errors'] == []
