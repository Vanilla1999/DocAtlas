from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import pytest
import yaml

from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.mcp import _docs_server_part01 as mcp


DOCUMENTS = {'docs/rules.md': (
    '# Fixture constraints\r\n\r\nConstraints apply to `BootstrapNeedle`: '
    'private fixture state must remain isolated.\r\n')}
QUESTION = 'What constraints apply to `BootstrapNeedle`?'


def fixture_root(tmp_path):
    root = tmp_path / 'corpus' / 'fixture'
    write_project(root, DOCUMENTS)
    return root


def test_cold_unconfirmed_prepare_never_initializes_storage(tmp_path):
    root = fixture_root(tmp_path)
    with isolated_service(tmp_path / 'state') as (service, config):
        cold = service._cold
        policy = cold.member_storage_policy
        assert cold._service is None
        assert config.index.db_path == str(policy.db_path)
        assert not policy.db_path.exists() and not policy.marker.exists()
        result = mcp.call_docs_tool_payload('prepare_docs', {
            'action': 'sync_project_docs', 'project_path': str(root),
        }, cold)
        assert result['status'] != 'success'
        assert not policy.db_path.exists() and not policy.marker.exists()
        assert cold._service is None


def test_confirmed_prepare_retrieval_and_diagnostics_share_actual_store(tmp_path, monkeypatch):
    root = fixture_root(tmp_path)
    # An extra file is not catalog membership or an acquisition route. Fixture
    # intent comes solely from the document mapping above.
    (root / 'unselected.md').write_text('# Unselected\n\nBootstrapNeedle unselected sentinel.\n')
    captured = []
    original = mcp.call_docs_tool_payload

    def capture(name, arguments, service, **kwargs):
        captured.append((name, deepcopy(arguments)))
        return original(name, arguments, service, **kwargs)

    monkeypatch.setattr(mcp, 'call_docs_tool_payload', capture)
    # The legacy observer imports this public dispatcher into its own module;
    # capture either import order without changing dispatch or its arguments.
    import scripts.run_project_docs_self_host_gate as gate
    monkeypatch.setattr(gate, 'call_docs_tool_payload', capture)
    with isolated_service(tmp_path / 'state') as (service, config):
        ingest = index_project(service, config, root)
        assert service._cold._service is None  # preparing does not eagerly materialize
        policy = service._cold.member_storage_policy
        assert ingest['storage_path'] == config.index.db_path == str(policy.db_path)
        assert ingest['expected_paths'] == ingest['indexed_paths'] == ['docs/rules.md']
        assert not ingest['unexpected_paths'] and not ingest['excluded_or_failed_paths']
        assert policy.generation() == ingest['generation_id']
        grant = captured[0][1]['mutation']
        entry = read_project_docs_catalog(root).entries[0]
        assert grant['confirm'] is True and grant['expected_generation_id'] is None
        assert grant['catalog_sha256'] == hashlib.sha256((root / 'docatlas.project-docs.yaml').read_bytes()).hexdigest()
        assert grant['documents'] == [{
            'path': 'docs/rules.md',
            'content_sha256': hashlib.sha256(DOCUMENTS['docs/rules.md'].encode()).hexdigest(),
            'catalog_entry_hash': catalog_entry_hash(entry),
        }]
        assert (root / 'docs/rules.md').read_bytes() == DOCUMENTS['docs/rules.md'].encode()
        # The unchanged evaluator's observer must see the materialized facade,
        # rather than a second index or a callback attached to the cold wrapper.
        from eval.evidence_quality_v2.observer import observe_call
        request = {'question': QUESTION, 'project_path': str(root), 'scope': 'all'}
        payload, trace = observe_call(service, request)
        # Bootstrap cannot restore removed natural-language answer authority.
        # Check real acquisition independently of that production delivery
        # decision; never add expected facts as public runtime requirements.
        assert payload['status'] == 'insufficient_evidence', payload
        assert payload['reason_code'] == 'required_evidence_missing'
        assert payload['answer_supported'] is False and payload['edit_ready'] is False
        assert len(trace['stages']['retrieved_candidates']) == 1
        assert len(trace['stages']['query_window']) == 1
        acquired = trace['stages']['query_window'][0]['sources']
        assert {row['path_or_url'] for row in acquired} == {'docs/rules.md'}
        assert all(row['snippet'] in DOCUMENTS['docs/rules.md'] for row in acquired)
        assert all(row['retrieval_query_matches']['query-original']['qualified'] for row in acquired)
        assert not trace['stages']['projector_inputs'] and not trace['snapshot']
        assert mcp._service_for_project_path(service, request) is service._cold.materialize()
        assert str(service.agent_gateway.agent_instance().store.db_path) == str(policy.db_path)
        assert not hasattr(service._cold._service, '_same_call_diagnostics_observer')
        assert captured[-1][1] == request and 'requirements' not in captured[-1][1]
        with sqlite3.connect(policy.db_path) as db:
            sources = db.execute('SELECT content, metadata_json FROM sources').fetchall()
        assert len(sources) == 1 and sources[0][0] == DOCUMENTS['docs/rules.md']
        assert 'unselected sentinel' not in json.dumps(json.loads(sources[0][1])).lower()
        assert not (tmp_path / 'state/index.db').exists()


def test_replay_reopens_same_host_target_and_idempotent_generation(tmp_path):
    root = fixture_root(tmp_path)
    state = tmp_path / 'state'
    with isolated_service(state) as (service, config):
        first = index_project(service, config, root)
    with isolated_service(state) as (service, config):
        assert service._cold._service is None
        second = index_project(service, config, root)
        assert first['storage_path'] == second['storage_path']
        assert first['generation_id'] == second['generation_id']
        assert first['rows'] == second['rows']
        assert second['transaction_metrics']['derived_writes'] == 0
        assert second['transaction_metrics']['unchanged_files'] == 1
        assert second['transaction_metrics']['sources_deleted'] == 0


def test_fixture_environment_ignores_inherited_storage_and_cwd_config(tmp_path, monkeypatch):
    root = fixture_root(tmp_path)
    foreign = tmp_path / 'foreign.db'
    foreign.write_bytes(b'foreign database must not be adopted')
    (tmp_path / 'docatlas.yaml').write_text('index:\n  provider: qdrant\n  db_path: foreign.db\n')
    monkeypatch.chdir(tmp_path)
    for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'DOCATLAS_HOME'):
        monkeypatch.setenv(key, str(tmp_path / ('inherited-' + key)))
    monkeypatch.setenv('DOCATLAS_INDEX_DB_PATH', str(foreign))
    monkeypatch.setenv('DOCATLAS_INDEX_PROVIDER', 'qdrant')
    monkeypatch.setenv('DOCATLAS_AUTO_VECTORS', '1')
    before = dict(os.environ)
    with isolated_service(tmp_path / 'state') as (service, config):
        assert 'DOCATLAS_INDEX_DB_PATH' not in os.environ
        assert config.index.provider == 'sqlite' and config.retrieval.default_mode == 'lexical'
        assert os.environ['DOCATLAS_OFFLINE'] == '1' and os.environ['DOCATLAS_AUTO_VECTORS'] == '0'
        policy = service._cold.member_storage_policy
        assert not policy.app_home.is_relative_to(tmp_path)
        assert policy.db_path.is_relative_to(policy.app_home)
        index_project(service, config, root)
    assert dict(os.environ) == before
    assert foreign.read_bytes() == b'foreign database must not be adopted'
    with pytest.raises(RuntimeError, match='fixture failure'):
        with isolated_service(tmp_path / 'other-state'):
            raise RuntimeError('fixture failure')
    assert dict(os.environ) == before


@pytest.mark.parametrize('field,value', [('roots', [{'path': 'docs'}]), ('code_files', ['example.py'])])
def test_nonfinite_or_code_catalog_does_not_initialize_store(tmp_path, field, value):
    root = fixture_root(tmp_path)
    catalog_path = root / 'docatlas.project-docs.yaml'
    catalog = yaml.safe_load(catalog_path.read_text())
    catalog[field] = value
    catalog_path.write_text(yaml.safe_dump(catalog))
    with isolated_service(tmp_path / 'state') as (service, config):
        with pytest.raises(ValueError, match='finite docs-only catalog'):
            index_project(service, config, root)
        assert not service._cold.member_storage_policy.db_path.exists()


def test_confirmed_hash_and_generation_preconditions_remain_enforced(tmp_path, monkeypatch):
    root = fixture_root(tmp_path)
    original = mcp.call_docs_tool_payload
    requests = []

    def capture(name, arguments, service, **kwargs):
        requests.append(deepcopy(arguments))
        return original(name, arguments, service, **kwargs)

    monkeypatch.setattr(mcp, 'call_docs_tool_payload', capture)
    with isolated_service(tmp_path / 'state') as (service, config):
        first = index_project(service, config, root)
        policy = service._cold.member_storage_policy
        for field in ('content_sha256', 'catalog_entry_hash'):
            bad = deepcopy(requests[0])
            bad['mutation']['expected_generation_id'] = first['generation_id']
            bad['mutation']['documents'][0][field] = ('sha256:' if field == 'catalog_entry_hash' else '') + '0' * 64
            result = original('prepare_docs', bad, service._cold)
            assert result['status'] != 'success'
            assert policy.generation() == first['generation_id']
        stale = deepcopy(requests[0])  # null no longer matches the committed G
        result = original('prepare_docs', stale, service._cold)
        assert result['status'] != 'success'
        assert policy.generation() == first['generation_id']


def test_fixture_project_config_cannot_select_storage(tmp_path):
    root = fixture_root(tmp_path)
    (root / 'docatlas.yaml').write_text('index:\n  db_path: foreign.db\n')
    with isolated_service(tmp_path / 'state') as (service, config):
        with pytest.raises(ValueError, match='must not inherit project configuration'):
            index_project(service, config, root)
        assert not service._cold.member_storage_policy.db_path.exists()


def test_parallel_fixture_contexts_have_distinct_stores_and_restore_environment(tmp_path):
    before = dict(os.environ)

    def run_one(number):
        root = tmp_path / str(number) / 'corpus'
        write_project(root, DOCUMENTS)
        with isolated_service(tmp_path / str(number) / 'state') as (service, config):
            ingest = index_project(service, config, root)
            assert os.environ['DOCATLAS_HOME'] == str(service._cold.member_storage_policy.app_home)
            return ingest['storage_path']

    with ThreadPoolExecutor(max_workers=2) as executor:
        stores = list(executor.map(run_one, (1, 2)))
    assert stores[0] != stores[1]
    assert dict(os.environ) == before
