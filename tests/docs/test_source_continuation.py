from dataclasses import asdict
import hashlib
import json

import pytest

from docmancer.docs.application.source_continuation import SourceContinuationReader, SourceReference
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
from docmancer.docs.infrastructure.project_source_read_gateway import ProjectSourceReadGateway
from docmancer.docs.project_docs_catalog import read_project_docs_catalog


class Gateway:
    def __init__(self, raw):
        self.raw = raw
        self.failure = None
        self.reads = 0

    def authorize(self, reference):
        return self.failure

    def read_snapshot(self, reference):
        self.reads += 1
        return self.raw


def reference(raw):
    return SourceReference('/repo', 'project:test', 'docs/jobs.md',
                           'sha256:' + hashlib.sha256(raw).hexdigest(), 'catalog:1',
                           'source_of_truth', 'project', None, 2)


def test_next_range_contains_missing_scope_table_without_repeating_intro():
    raw = b'# Scope\nIntroduction\nproject: repository rules only\nall: repository and modules\n'
    gateway = Gateway(raw)
    reader = SourceContinuationReader(gateway)
    uri = reader.issue(reference(raw))
    assert gateway.reads == 0
    result = reader.read(uri)
    assert result['snippet'] == 'project: repository rules only\nall: repository and modules'
    assert result['line_start'] == 3
    assert result['status'] == 'complete'
    assert reader.read(uri)['status'] == 'source_unavailable'
    assert gateway.reads == 1


def test_policy_revocation_and_forged_cursor_reject_before_hydration():
    gateway = Gateway(b'intro\nintro\npoll until terminal\n')
    reader = SourceContinuationReader(gateway)
    uri = reader.issue(reference(gateway.raw))
    assert reader.read(uri + '?start=1&budget=99999')['status'] == 'source_unavailable'
    gateway.failure = 'source_unavailable'
    assert reader.read(uri)['status'] == 'source_unavailable'
    assert gateway.reads == 0


def test_changed_snapshot_never_returns_latest_text():
    gateway = Gateway(b'intro\nintro\nold polling\n')
    reader = SourceContinuationReader(gateway)
    uri = reader.issue(reference(gateway.raw))
    gateway.raw = b'intro\nintro\nnew polling\n'
    result = reader.read(uri)
    assert result['status'] == 'source_changed'
    assert 'snippet' not in result


def test_total_json_budget_two_reads_and_monotonic_ranges():
    raw = ('intro\nintro\n' + '\n'.join(f'Poll job {i} until terminal status.' for i in range(300))).encode()
    gateway = Gateway(raw)
    reader = SourceContinuationReader(gateway)
    first = reader.read(reader.issue(reference(raw)))
    second = reader.read(first['continuation'])
    assert second['line_start'] == first['line_end'] + 1
    assert second['continuation'] is None
    assert second['reason_code'] == 'read_limit_reached'
    assert all(docs_context_budget_tokens(result) <= 600 for result in (first, second))


def test_giant_line_and_expiry_do_not_create_a_loop():
    gateway = Gateway(b'intro\nintro\n' + b'identifier_1234 ' * 1000)
    now = [0]
    reader = SourceContinuationReader(gateway, clock=lambda: now[0])
    uri = reader.issue(reference(gateway.raw))
    assert reader.read(uri)['reason_code'] == 'line_exceeds_read_budget'
    uri = reader.issue(reference(gateway.raw))
    now[0] = 601
    assert reader.read(uri)['status'] == 'source_unavailable'
    assert gateway.reads == 1


@pytest.fixture
def filesystem_reader(tmp_path):
    (tmp_path / 'docs').mkdir()
    source = tmp_path / 'docs/jobs.md'
    source.write_text('# Jobs\nIntroduction\nPoll until terminal.\nRetry only after completion.\n')
    (tmp_path / 'docatlas.project-docs.yaml').write_text('''schema_version: 1
documents:
  - path: docs/jobs.md
    role: runbook
    scope: project
    authority: source_of_truth
    status: active
    description: Job lifecycle
''')
    entry = read_project_docs_catalog(tmp_path).entries[0]
    catalog_hash = 'sha256:' + hashlib.sha256(json.dumps(
        asdict(entry), ensure_ascii=False, sort_keys=True, separators=(',', ':'),
    ).encode()).hexdigest()
    ref = SourceReference(str(tmp_path), 'project:test', 'docs/jobs.md',
                          'sha256:' + hashlib.sha256(source.read_bytes()).hexdigest(),
                          catalog_hash, 'source_of_truth', 'project', None, 2)
    metadata = {
        'project_path': str(tmp_path), 'project_identity': ref.project_identity,
        'project_doc_path': ref.path, 'project_doc_content_hash': ref.content_sha256,
        'project_doc_catalog_entry_hash': catalog_hash, 'source_class': 'project_file',
        'doc_scope': 'project', 'authority': 'source_of_truth', 'lifecycle_status': 'active',
    }

    class Store:
        active = True

        def source_metadata(self, path):
            assert path == str(source)
            return metadata

        def section_ids_for_source(self, path):
            return [1] if self.active else []

        def section_filter_metadata_for(self, ids):
            return {1: dict(metadata)}

    store = Store()
    gateway = ProjectSourceReadGateway(lambda: store, identity_for_root=lambda root: ref.project_identity)
    return SourceContinuationReader(gateway), ref, source, store, metadata


def test_real_filesystem_preserves_job_polling_and_retry_order(filesystem_reader):
    reader, ref, source, _, _ = filesystem_reader
    result = reader.read(reader.issue(ref))
    assert result['snippet'] == 'Poll until terminal.\nRetry only after completion.'
    assert result['content_sha256'] == ref.content_sha256


@pytest.mark.parametrize('change', ['catalog', 'inactive_index', 'cross_project', 'symlink', 'delete'])
def test_real_boundary_revocations_prevent_source_hydration(filesystem_reader, monkeypatch, change):
    reader, ref, source, store, metadata = filesystem_reader
    uri = reader.issue(ref)
    assert uri
    if change == 'catalog':
        catalog = source.parent.parent / 'docatlas.project-docs.yaml'
        catalog.write_text(catalog.read_text().replace('source_of_truth', 'historical'))
    elif change == 'inactive_index':
        store.active = False
    elif change == 'cross_project':
        metadata['project_identity'] = 'project:other'
    elif change == 'symlink':
        source.unlink()
        source.symlink_to('/etc/passwd')
    else:
        source.unlink()
    def forbidden(ref):
        pytest.fail('rejected source hydrated')
    monkeypatch.setattr(reader.gateway, 'read_snapshot', forbidden)
    assert reader.read(uri)['status'] == 'source_unavailable'


def test_symlink_replacement_after_authorization_cannot_escape(filesystem_reader):
    reader, ref, source, _, _ = filesystem_reader
    assert reader.gateway.authorize(ref) is None
    source.unlink()
    source.symlink_to('/etc/passwd')
    with pytest.raises(OSError):
        reader.gateway.read_snapshot(ref)


def test_public_handler_binds_reader_to_real_active_sqlite_snapshot(tmp_path):
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService
    from docmancer.mcp.docs_server import call_docs_tool_payload, read_docs_resource
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'pyproject.toml').write_text('[project]\nname="reader-smoke"\nversion="0.1"\n')
    path = tmp_path / 'docs/jobs.md'
    path.write_text('# Job polling\n\nJob polling uses docs_status to inspect progress.\n\n'
        + '\n'.join('Poll jobs with docs_status until terminal status.' for _ in range(30)) + '\n')
    (tmp_path / 'docatlas.project-docs.yaml').write_text(
        'schema_version: 1\ndocuments:\n  - path: docs/jobs.md\n    role: runbook\n'
        '    scope: project\n    authority: source_of_truth\n    status: active\n'
        '    description: Job polling lifecycle\n')
    config = DocmancerConfig()
    config.index.provider = 'sqlite'
    config.index.db_path = str(tmp_path / 'state/index.db')
    config.index.extracted_dir = str(tmp_path / 'state/extracted')
    service = LibraryDocsService(config=config, config_source='explicit')
    assert service.sync_project_docs(str(tmp_path), with_vectors=False).status == 'success'
    args = dict(question='Explain job polling.', lookup_queries=['job polling progress'],
                project_path=str(tmp_path), scope='all')
    payload = call_docs_tool_payload('get_docs_context', args, service)
    from scripts.run_project_docs_self_host_gate import _call_with_snapshot, _coverage_attribution
    observed, snapshot = _call_with_snapshot({**args, 'question': 'Job polling uses docs_status to inspect progress.'}, service)
    assert 'query-original' in observed['covered_query_ids']
    assert _coverage_attribution(snapshot, observed)
    from copy import deepcopy
    tampered = deepcopy(observed)
    for row in tampered['sources']:
        row['snippet'] += ' unsupported claim'
    assert not _coverage_attribution(snapshot, tampered)
    tampered = deepcopy(observed)
    for row in tampered['sources']:
        row['source_uri'] = 'docatlas://source/' + '0' * 24
    assert not _coverage_attribution(snapshot, tampered)
    source = next(row for row in payload['sources'] if row.get('source_uri'))
    read = json.loads(read_docs_resource(source['source_uri'], service)['text'])
    assert read['line_start'] == source['line_end'] + 1
    assert 'docs_status' in read['snippet']
    assert docs_context_budget_tokens(read) <= 600
    # A new query may issue a fresh session reference; changing the file must
    # never turn that reference into an implicit latest-version read.
    payload = call_docs_tool_payload('get_docs_context', args, service)
    source = next(row for row in payload['sources'] if row.get('source_uri'))
    path.write_text(path.read_text() + 'Unexpected replacement.\n')
    read = json.loads(read_docs_resource(source['source_uri'], service)['text'])
    assert read['status'] == 'source_changed'
    assert 'snippet' not in read
