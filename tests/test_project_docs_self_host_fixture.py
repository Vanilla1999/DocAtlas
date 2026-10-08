"""Real fixture setup guards; evaluator inputs and retrieval rules stay untouched."""
from copy import deepcopy
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

import pytest
import yaml

from scripts import _project_docs_self_host_fixture as fixture_module
from docmancer.docs.application.project_docs_member_transaction import local_project_identity
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.mcp._docs_server_part01 import call_docs_tool_payload


RULES = b'# Fixture rules\r\n\r\n`MirrorNeedle` requires explicit preparation before a member write.\r\n'


def _git(root, *arguments):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS='0')
    return subprocess.run(
        ['git', '-c', 'core.hooksPath=' + os.devnull, '-c', 'core.fsmonitor=false',
         '-c', 'commit.gpgsign=false', '-c', 'user.name=Fixture',
         '-c', 'user.email=fixture@example.invalid', '-C', str(root), *arguments],
        env=env, stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=10,
    ).stdout


def _checkout(tmp_path):
    root = tmp_path / 'origin'
    root.mkdir()
    documents = {
        'README.md': b'# Fixture overview\n\nThis repository documents a finite member store.\n',
        'docs/rules.md': RULES,
        'docs/unselected.md': b'# Unselected\n\nForbiddenGoldenNeedle is a physical distractor.\n',
        'eval/answers.json': b'{"answer": "ForbiddenGoldenNeedle"}\n',
        'src/unselected.py': b'NEVER_IMPORT_THIS_MIRROR = True\n',
        'pyproject.toml': b'[project]\nname="fixture"\ndependencies=["foreign-library==9"]\n',
        '.gitignore': b'untracked/\n__pycache__/\n',
    }
    config = {
        'index': {'provider': 'sqlite', 'db_path': '.docatlas/docatlas.db',
                  'extracted_dir': '.docatlas/extracted'},
        'query': {'default_budget': 2400, 'default_limit': 8},
        'project': {'source_roots': ['src'], 'documentation_roots': ['docs'],
                    'exclude_paths': ['blocked/**'], 'generated_paths': ['generated/**'],
                    'include_extensions': ['.py'], 'max_scanned_files': 5000,
                    'max_scanned_bytes': 33554432, 'max_file_bytes': 256000,
                    'scan_deadline_seconds': 5, 'max_directory_depth': 20},
    }
    entries = [
        {'path': 'README.md', 'role': 'overview', 'scope': 'project',
         'description': 'Fixture overview', 'authority': 'supporting', 'status': 'active', 'impact': 'track'},
        {'path': 'docs/rules.md', 'role': 'development', 'scope': 'project',
         'description': 'Literal fixture rules', 'authority': 'source_of_truth', 'status': 'active', 'impact': 'track'},
    ]
    documents['docatlas.yaml'] = yaml.safe_dump(config, sort_keys=False).encode()
    documents['docatlas.project-docs.yaml'] = yaml.safe_dump(
        {'schema_version': 1, 'code_files': [], 'documents': entries}, sort_keys=False,
    ).encode()
    for relative, data in documents.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    _git(root, 'init', '--initial-branch=main')
    _git(root, 'add', '--all')
    _git(root, 'commit', '-m', 'fixture-only source snapshot')
    (root / 'untracked').mkdir()
    (root / 'untracked/not-copied.md').write_bytes(b'Untracked build output')
    return root, documents


def _cold_read(fixture):
    return call_docs_tool_payload('get_docs_context', {
        'question': 'What does `MirrorNeedle` require?', 'project_path': str(fixture.root), 'scope': 'all',
    }, fixture.service)


def test_self_host_snapshot_preserves_all_catalog_bytes_and_source_boundaries(tmp_path):
    origin, documents = _checkout(tmp_path)
    source_metadata = ProjectMetadataReader().read(origin)
    with fixture_module.self_host_fixture(origin) as fixture:
        provenance = fixture.provenance
        assert provenance['file_count'] == len(documents)
        assert provenance['total_source_bytes'] == sum(map(len, documents.values()))
        assert {row['path'] for row in provenance['files']} == set(documents)
        assert provenance['origin']['head_sha'] == _git(origin, 'rev-parse', 'HEAD').decode().strip()
        assert provenance['origin']['tree_sha'] == _git(origin, 'rev-parse', 'HEAD^{tree}').decode().strip()
        source_manifest = [{key: row[key] for key in (
            'path', 'git_mode', 'git_blob', 'bytes', 'original_sha256',
        )} for row in provenance['files']]
        assert provenance['source_manifest_sha256'] == hashlib.sha256(json.dumps(
            source_manifest, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
        ).encode()).hexdigest()
        for row in provenance['files']:
            assert row['original_sha256'] == row['copied_sha256'] == hashlib.sha256(documents[row['path']]).hexdigest()
            assert row['mirror_sha256'] == hashlib.sha256((fixture.root / row['path']).read_bytes()).hexdigest()
            if row['path'] != 'docatlas.yaml':
                assert (fixture.root / row['path']).read_bytes() == documents[row['path']]
            assert not (stat.S_IMODE((fixture.root / row['path']).stat().st_mode) & 0o222)
        copied_config = yaml.safe_load((fixture.root / 'docatlas.yaml').read_text())
        original_config = yaml.safe_load(documents['docatlas.yaml'])
        assert copied_config['index']['db_path'] == fixture.config.index.db_path
        copied_config['index']['db_path'] = original_config['index']['db_path']
        assert copied_config == original_config
        assert provenance['config_delta']['field'] == 'index.db_path'
        assert (fixture.root / 'docatlas.project-docs.yaml').read_bytes() == documents['docatlas.project-docs.yaml']
        copied_metadata = ProjectMetadataReader().read(fixture.root)
        fields = ('path', 'content_hash', 'catalog_entry_hash', 'doc_scope', 'module_path',
                  'authority', 'lifecycle_status', 'impact_policy', 'description')
        assert [[getattr(item, name) for name in fields] for item in copied_metadata.docs_candidates] == [
            [getattr(item, name) for name in fields] for item in source_metadata.docs_candidates
        ]
        assert copied_metadata.dependencies == source_metadata.dependencies == []
        assert copied_metadata.detected_ecosystems == source_metadata.detected_ecosystems == []
        assert copied_metadata.code_files == source_metadata.code_files == ()
        assert provenance['mirror_identity'] == local_project_identity(fixture.root)
        assert provenance['mirror_identity'] != local_project_identity(origin)
        for module in provenance['import_origins']['modules'].values():
            assert Path(module['path']).is_relative_to(Path(fixture_module.__file__).resolve().parents[1])
            assert not Path(module['path']).is_relative_to(fixture.root)
            assert module['sha256'] == hashlib.sha256(Path(module['path']).read_bytes()).hexdigest()
    assert provenance['origin_unchanged_after_calls'] is True
    assert {relative: (origin / relative).read_bytes() for relative in documents} == documents
    # These bounds reject the entire mirror; they never filter selected members.
    for name, value in [('MAX_FILES', 1), ('MAX_INVENTORY_BYTES', 8),
                        ('MAX_FILE_BYTES', 1), ('MAX_TOTAL_BYTES', 1), ('COPY_SECONDS', 0)]:
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(fixture_module, name, value)
            with pytest.raises(ValueError):
                with fixture_module.self_host_fixture(origin):
                    pytest.fail('over-bound mirror was exposed')


def test_self_host_snapshot_does_not_select_members_from_questions_or_unselected_files(tmp_path):
    origin, documents = _checkout(tmp_path)
    with fixture_module.self_host_fixture(origin) as fixture:
        assert (fixture.root / 'docs/unselected.md').read_bytes() == documents['docs/unselected.md']
        assert (fixture.root / 'eval/answers.json').read_bytes() == documents['eval/answers.json']
        assert (fixture.root / 'src/unselected.py').read_bytes() == documents['src/unselected.py']
        assert not (fixture.root / 'untracked').exists()
        assert not (fixture.root / '.git').exists()
        assert {row['path'] for row in fixture.mutation['documents']} == {'README.md', 'docs/rules.md'}
        assert fixture.verify_cold_read(_cold_read(fixture))
        fixture.prepare()
        assert fixture.provenance['preparation']['indexed_paths'] == ['README.md', 'docs/rules.md']
        policy = fixture.service._cold.member_storage_policy
        with closing(policy.connect()) as db:
            stored = [dict(row) for row in db.execute('SELECT content, metadata_json FROM sources')]
        assert len(stored) == 2
        assert all('ForbiddenGoldenNeedle' not in row['content'] for row in stored)
        assert {json.loads(row['metadata_json'])['project_doc_path'] for row in stored} == {'README.md', 'docs/rules.md'}
    # A tracked symlink is not silently dropped while making a smaller mirror.
    outside = tmp_path / 'foreign-hardlink'
    os.link(origin / 'README.md', outside)
    with pytest.raises(ValueError, match='non-hardlinked regular file'):
        with fixture_module.self_host_fixture(origin):
            pytest.fail('hardlinked source was accepted')
    outside.unlink()
    (origin / 'outside-link').symlink_to(tmp_path / 'outside')
    _git(origin, 'add', 'outside-link')
    _git(origin, 'commit', '-m', 'fixture unsafe tracked path')
    with pytest.raises(ValueError, match='unsafe, nonregular or unmerged'):
        with fixture_module.self_host_fixture(origin):
            pytest.fail('tracked symlink was followed or omitted')


def test_self_host_cold_read_does_not_create_or_authorize_storage(tmp_path):
    origin, _ = _checkout(tmp_path)
    with fixture_module.self_host_fixture(origin) as fixture:
        cold = fixture.service._cold
        policy = cold.member_storage_policy
        payload = _cold_read(fixture)
        assert payload['status'] == 'failed'
        assert payload['error']['reason_code'] == 'permission_denied'
        assert cold._service is None and not policy.db_path.exists() and not policy.marker.exists()
        for invalid in (None, [], 'unexpected', {'status': 'ok'},
                        {'recommended_next_action': {'arguments_patch': {'action': 'sync_project_docs'}}}):
            assert fixture.verify_cold_read(invalid) is False
            with pytest.raises(ValueError, match='pre-sync cold read guard'):
                fixture.prepare()
        for flag in ('answer_supported', 'answer_available', 'edit_ready', 'mutation_ready', 'context_available'):
            for value in (True, 1, 0, []):
                contradictory = deepcopy(payload)
                contradictory[flag] = value
                assert fixture.verify_cold_read(contradictory) is False
                with pytest.raises(ValueError, match='pre-sync cold read guard'):
                    fixture.prepare()
        assert fixture.verify_cold_read({**payload, 'kind': 'docs_answer'}) is False
        assert fixture.verify_cold_read(payload)
        denied = call_docs_tool_payload('prepare_docs', {
            'action': 'sync_project_docs', 'project_path': str(fixture.root),
        }, cold)
        assert denied['status'] == 'failed' and denied['error']['reason_code'] == 'permission_denied'
        assert cold._service is None and not policy.db_path.exists() and not policy.marker.exists()


def test_self_host_confirmed_prepare_binds_one_host_store_and_copied_project(tmp_path):
    origin, _ = _checkout(tmp_path)
    with fixture_module.self_host_fixture(origin) as fixture:
        policy = fixture.service._cold.member_storage_policy
        assert policy.db_path.is_relative_to(policy.app_home)
        assert not policy.db_path.is_relative_to(origin)
        assert not policy.db_path.is_relative_to(fixture.root)
        assert fixture.mutation['confirm'] is True and fixture.mutation['expected_generation_id'] is None
        assert fixture.verify_cold_read(_cold_read(fixture))
        fixture.prepare()
        prepared = fixture.provenance['preparation']
        assert policy.generation() == prepared['generation_id']
        assert prepared['storage_path'] == fixture.config.index.db_path
        assert fixture.service._cold._service is None
        assert not (fixture.root / '.docatlas').exists()
        from scripts.run_project_docs_self_host_gate import _call_with_snapshot
        payload, snapshot = _call_with_snapshot({
            'question': 'What does `MirrorNeedle` require?', 'project_path': str(fixture.root), 'scope': 'all',
            'lookup_queries': ['`MirrorNeedle` explicit preparation'],
        }, fixture.service)
        diagnostic = json.dumps({'payload': payload, 'snapshot_keys': sorted(snapshot)},
                                ensure_ascii=False, sort_keys=True)
        assert payload['status'] == 'ok' and payload['kind'] == 'docs_context', diagnostic
        assert payload['context_available'] is True and snapshot, diagnostic
        assert payload['answer_available'] is False and payload['support_status'] == 'retrieval_only', diagnostic
        assert 'query-lookup-1' in payload['covered_query_ids'], diagnostic
        assert 'query-original' not in payload['covered_query_ids'], diagnostic
        assert 'query-original' in payload['missing_query_ids'], diagnostic
        assert payload['answer_supported'] is False and payload['edit_ready'] is False
        sources = [row for row in payload['sources'] if row['path_or_url'] == 'docs/rules.md']
        assert sources and sources[0]['snippet'] in RULES.decode()
        assert sources[0]['project_identity'] == local_project_identity(fixture.root)
        source = snapshot[sources[0]['evidence_id']]['source']
        assert source['content'] == RULES.decode()
        assert source['generation_id'] == prepared['generation_id']
        assert source['display_content_hash'] == hashlib.sha256(RULES).hexdigest()
        catalog = read_project_docs_catalog(fixture.root)
        member = next(row for row in prepared['mutation']['documents'] if row['path'] == 'docs/rules.md')
        assert source['_source_catalog_hash'] == member['catalog_entry_hash']
        assert {row.path for row in catalog.entries} == {'README.md', 'docs/rules.md'}
        assert str(fixture.service.agent_gateway.agent_instance().store.db_path) == str(policy.db_path)
        inspection = fixture.service.inspect_project_docs(str(fixture.root))
        assert inspection.reason_code == 'project_docs_ready'
        assert not inspection.requires_confirmation
        assert inspection.project_docs['preflight']['git']['status'] == 'not_git'
        assert inspection.project_docs['preflight']['auto_sync_eligible'] is False
        assert not inspection.stale_sources and not inspection.ignored_sources
        with pytest.raises(ValueError, match='original cold store'):
            fixture.prepare()


def test_self_host_conflicting_config_and_changed_hashes_fail_before_initialization(tmp_path):
    origin, documents = _checkout(tmp_path)
    with fixture_module.self_host_fixture(origin) as fixture:
        cold = fixture.service._cold
        policy = cold.member_storage_policy
        assert fixture.verify_cold_read(_cold_read(fixture))
        path = fixture.root / 'docatlas.yaml'
        relocated = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(documents['docatlas.yaml'])
        with pytest.raises(RuntimeError, match='explicit member preparation failed'):
            fixture.prepare()
        assert not policy.db_path.exists() and not policy.marker.exists() and cold._service is None
        path.write_bytes(relocated)
        path.chmod(0o444)
        for field in ('content_sha256', 'catalog_entry_hash', 'catalog_sha256', 'expected_generation_id'):
            mutation = deepcopy(fixture.mutation)
            if field in {'content_sha256', 'catalog_entry_hash'}:
                mutation['documents'][0][field] = ('sha256:' if field == 'catalog_entry_hash' else '') + '0' * 64
            else:
                mutation[field] = '0' * 64
            denied = call_docs_tool_payload('prepare_docs', {
                'action': 'sync_project_docs', 'project_path': str(fixture.root), 'mutation': mutation,
            }, cold)
            assert denied['status'] == 'failed', field
            assert not policy.db_path.exists() and not policy.marker.exists() and cold._service is None
        fixture.prepare()
        assert policy.generation() == fixture.provenance['preparation']['generation_id']


def test_self_host_fixture_restores_environment_and_preserves_original_repository(tmp_path, monkeypatch):
    origin, documents = _checkout(tmp_path)
    foreign = tmp_path / 'foreign.db'
    foreign.write_bytes(b'foreign user database must not be adopted')
    monkeypatch.setenv('DOCATLAS_INDEX_DB_PATH', str(foreign))
    monkeypatch.setenv('DOCATLAS_HOME', str(tmp_path / 'foreign-home'))
    monkeypatch.setenv('GIT_DIR', str(tmp_path / 'foreign-git'))
    monkeypatch.setenv('GIT_INDEX_FILE', str(tmp_path / 'foreign-index'))
    before, cwd = dict(os.environ), Path.cwd()
    with pytest.raises(RuntimeError, match='fixture caller failure'):
        with fixture_module.self_host_fixture(origin) as fixture:
            mirror = fixture.root
            assert 'GIT_DIR' not in os.environ and 'GIT_INDEX_FILE' not in os.environ
            assert 'DOCATLAS_INDEX_DB_PATH' not in os.environ
            assert os.environ['DOCATLAS_OFFLINE'] == '1' and os.environ['DOCATLAS_AUTO_VECTORS'] == '0'
            assert Path.cwd() == cwd
            assert fixture.config.index.db_path != str(foreign)
            raise RuntimeError('fixture caller failure')
    assert not mirror.exists()
    assert dict(os.environ) == before and Path.cwd() == cwd
    assert foreign.read_bytes() == b'foreign user database must not be adopted'
    assert {relative: (origin / relative).read_bytes() for relative in documents} == documents
    assert _git(origin, 'status', '--porcelain', '--untracked-files=no') == b''
