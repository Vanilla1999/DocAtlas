"""Real SQLiteStore fixtures, not a synthetic search implementation."""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from experiments.retrieval_ablation.adapters import native_diagnostic, observe_native_sql


def make_store(tmp_path, count=10):
    sources = {f'docs/{i:02}.md': f'# Widget {i}\n\nwidget alpha contract {i}\n' for i in range(count)}
    store = SQLiteStore(tmp_path / 'index.db')
    store.add_documents([Document(source=path, content=text, metadata={
        'format': 'markdown', 'project_identity': 'repo',
        'source_class': 'project_doc', 'authority': 'source_of_truth',
        'resolved_version': '1',
    }) for path, text in sources.items()], recreate=True)
    return store, sources


def test_raw_budget_counts_and_or_and_all_probes(tmp_path):
    store, sources = make_store(tmp_path)
    result = native_diagnostic(store, ['widget alpha', 'widget contract'],
        filters={'project_identity': 'repo'}, sources=sources, raw_limit=4)
    assert sum(len(lane['rows']) for lane in result['lanes']) <= 4


def test_sql_lanes_are_native_ordered_and_replayable(tmp_path):
    store, sources = make_store(tmp_path)
    result = native_diagnostic(store, ['widget alpha'], filters={'project_identity': 'repo'}, sources=sources)
    assert result['raw_hits'] > 0
    for lane in result['lanes']:
        costs = [row['rank'] for row in lane['rows']]
        assert costs == sorted(costs)
        with store._connect() as conn:
            actual = [dict(row) for row in conn.execute(lane['sql'], lane['parameters'])]
        assert actual == lane['rows']
    assert [c['bm25_cost'] for c in result['candidates']] == [row['rank'] for row in result['lanes'][0]['rows']]


def test_native_arm_never_calls_custom_ranking_or_expansion(tmp_path, monkeypatch):
    store, sources = make_store(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('custom ranking/packing was called')
    for method in ('query', '_ranking_candidate', '_expand_row'):
        monkeypatch.setattr(SQLiteStore, method, forbidden)
    result = native_diagnostic(store, ['widget'], filters={'project_identity': 'repo'}, sources=sources)
    assert result['candidates']
    assert result['model_visible_packet'] is None
    assert result['packet_status'] == 'BLOCKED_SAFE_PACKET_ADAPTER'
    assert result['quality_status'] == 'UNJUDGED'
    assert 'answer_supported' not in result
    assert 'edit_ready' not in result


@pytest.mark.parametrize('change', [
    {'project_identity': 'foreign'}, {'resolved_version': '2'},
    {'stale': True}, {'risk_flags': ['unsafe']},
    {'index_freshness': 'stale'}, {'lifecycle_status': 'superseded'},
])
def test_real_strong_forbidden_hit_is_filtered_before_exposure(tmp_path, change):
    store, sources = make_store(tmp_path, 1)
    sources['docs/foreign.md'] = '# Widget alpha\n\n' + 'widget alpha ' * 30
    store.add_documents([Document(source='docs/foreign.md', content=sources['docs/foreign.md'], metadata={
        'format': 'markdown', 'project_identity': 'repo', 'resolved_version': '1',
        'source_class': 'project_doc', 'authority': 'source_of_truth', **change})])
    # The forbidden source really exists and is a native lexical hit.
    assert any(row['source'] == 'docs/foreign.md' for row in store._search_rows('widget', 40))
    result = native_diagnostic(store, ['widget'], sources=sources, raw_limit=1,
                               filters={'project_identity': 'repo', 'resolved_version': '1'})
    assert result['raw_hits'] == 1
    assert all(row['source'] == 'docs/00.md' for lane in result['lanes'] for row in lane['rows'])
    assert result['policy_rejections']


@pytest.mark.parametrize('field,value', [
    ('display_text', 'modified quote'), ('char_end', 1000000),
    ('line_end', 100), ('display_content_hash', 'bad'),
    ('retrieval_content_hash', 'bad'), ('source_identity', 'foreign'),
])
def test_tampered_canonical_rows_never_enter_exposure(tmp_path, field, value):
    store, sources = make_store(tmp_path, 1)
    with store._connect() as conn:
        conn.execute(f'UPDATE retrieval_children SET {field} = ?', (value,))
    result = native_diagnostic(store, ['widget'], filters={'project_identity': 'repo'}, sources=sources)
    assert result['candidates'] == []
    assert result['raw_hits'] == 0
    assert result['policy_rejections']


def test_current_source_snapshot_is_not_replaced_by_self_consistent_old_index(tmp_path):
    store, sources = make_store(tmp_path, 1)
    sources['docs/00.md'] = sources['docs/00.md'].replace('alpha', 'omega')
    result = native_diagnostic(store, ['widget'], filters={'project_identity': 'repo'}, sources=sources)
    assert result['raw_hits'] == 0
    assert result['policy_rejections'][0]['reason'] == 'source_snapshot_mismatch'


def test_active_generation_only_and_read_only(tmp_path):
    store, sources = make_store(tmp_path, 1)
    old = dict(sources)
    sources = {'docs/new.md': '# Widget\n\nwidget current contract\n'}
    store.add_documents([Document(source=path, content=text, metadata={
        'format': 'markdown', 'project_identity': 'repo'}) for path, text in sources.items()], recreate=True)
    before = store.db_path.read_bytes()
    result = native_diagnostic(store, ['widget'], filters={'project_identity': 'repo'}, sources={**old, **sources})
    assert result['raw_hits'] > 0
    assert {c['row']['source'] for c in result['candidates']} == {'docs/new.md'}
    assert store.db_path.read_bytes() == before


def test_duplicate_hits_consume_budget_but_do_not_vote_twice(tmp_path):
    store, sources = make_store(tmp_path, 1)
    result = native_diagnostic(store, ['widget alpha', 'widget contract'],
        filters={'project_identity': 'repo'}, sources=sources, raw_limit=4)
    assert result['raw_hits'] == 4
    assert len(result['candidates']) == 1
    assert result['query_schedule'] == [2, 2]


def test_no_hits_is_executed_not_a_quality_failure(tmp_path):
    store, sources = make_store(tmp_path, 1)
    result = native_diagnostic(store, ['zzzzzzzzz'], filters={'project_identity': 'repo'}, sources=sources)
    assert result['execution_status'] == 'EXECUTED'
    assert result['raw_hits'] == 0
    assert result['quality_status'] == 'UNJUDGED'


@pytest.mark.parametrize('budget', [0, -1, True, 0.5])
def test_invalid_budgets_fail_closed(tmp_path, budget):
    store, sources = make_store(tmp_path, 1)
    with pytest.raises(ValueError, match='budgets'):
        native_diagnostic(store, ['widget'], filters={'project_identity': 'repo'}, sources=sources, raw_limit=budget)


def test_observer_is_transparent_and_restored_after_exception(tmp_path):
    store, _ = make_store(tmp_path)
    original = SQLiteStore._connect
    statements = []
    def counted_connect(self):
        connection = original(self)
        connection.set_trace_callback(statements.append)
        return connection
    with patch.object(SQLiteStore, '_connect', counted_connect):
        before = store.query('widget alpha', limit=2, budget=800, filters={'project_identity': 'repo'})
        plain_sql = list(statements)
        statements.clear()
        with observe_native_sql() as trace:
            after = store.query('widget alpha', limit=2, budget=800, filters={'project_identity': 'repo'})
        assert before == after
        assert statements == plain_sql
        assert len(trace.lanes) == 2
        assert any(not lane['uncapped_complete'] for lane in trace.lanes)
        with pytest.raises(RuntimeError, match='deliberate'):
            with observe_native_sql():
                raise RuntimeError('deliberate')
        assert SQLiteStore._connect is counted_connect
    assert SQLiteStore._connect is original


def test_public_handler_observer_preserves_dto_searches_and_index(tmp_path):
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from eval.evidence_quality_v2.observer import observe_call
    from docmancer.mcp.docs_server import call_docs_tool_payload
    project = tmp_path / 'project'
    write_project(project, {'docs/retry.md': '# Retry\n\nThe retry budget is three attempts. Do not retry cancellation.\n'})
    with isolated_service(tmp_path / 'state') as (service, config):
        config.retrieval.default_mode = 'lexical'
        config.retrieval.max_sections_per_source = 2
        index_project(service, config, project)
        request = {'question': 'What is the retry budget?', 'project_path': str(project), 'scope': 'all'}
        before = Path(config.index.db_path).read_bytes()
        uninstrumented = call_docs_tool_payload('get_docs_context', request, service)
        with observe_native_sql() as first:
            plain = call_docs_tool_payload('get_docs_context', request, service)
        with observe_native_sql() as second:
            observed, trace = observe_call(service, request)
        assert uninstrumented == plain == observed
        assert len(first.lanes) == len(second.lanes)
        assert [(x['sql'], x['parameters']) for x in first.lanes] == [(x['sql'], x['parameters']) for x in second.lanes]
        assert Path(config.index.db_path).read_bytes() == before
        assert trace['snapshot']


def test_public_handler_product_probe_is_real_and_audited(tmp_path):
    from experiments.retrieval_ablation.adapters import product_probe
    corpus = tmp_path / 'corpus'
    corpus.mkdir()
    raw = b'# Retry\n\nThe retry budget is three attempts. Do not retry cancellation.\n'
    (corpus / 'retry.md').write_bytes(raw)
    spec = {'schema_version': 1, 'sources': [{'path': 'retry.md', 'sha256': hashlib.sha256(raw).hexdigest()}]}
    result = product_probe(corpus, spec, {'question': 'What is the retry budget?'})
    assert result['arm'] == 'P'
    assert result['status'] == 'EXECUTED'
    assert result['audit_errors'] == []
    assert result['budget_tokens'] <= 800
    assert result['raw_fts_lanes']
