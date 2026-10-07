"""Offline packing tests: prepared candidates, fixture files, no index/provider."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
from types import SimpleNamespace

import pytest

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.project_docs_service import ProjectDocsService
from docmancer.docs.application.project_context_service import ProjectContextService
from docmancer.docs.application.unified_context_service import UnifiedDocsContextService
from docmancer.docs.domain.project_doc_ranking import rerank_project_doc_chunks
from docmancer.docs.domain.retrieval_routing import validate_routing_record
from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from docmancer.docs.models import ProjectDocsCandidate, ProjectMetadata


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    root = tmp_path
    path = 'rules.md'
    texts = []
    for index in range(32):
        lines = ['```python', 'def validate_binding(record):']
        for field in range(36):
            lines.extend([f'    if record["binding_{index}_{field}"] != "contract-{index}-{field}":',
                          f'        raise ValueError("invalid contract {index} field {field}")'])
        texts.append('\n'.join([*lines, '    return record', '```']) + '\n')
    content = ''.join(texts)
    (root / path).write_text(content)
    (root / 'docatlas.project-docs.yaml').write_text(
        'schema_version: 1\ndocuments:\n  - path: rules.md\n'
        '    role: api_contract\n    description: Binding contracts\n'
        '    authority: source_of_truth\n')
    source_hash = 'sha256:' + hashlib.sha256(content.encode()).hexdigest()
    member = ProjectDocsCandidate(path=path, content_hash=source_hash,
        authority='source_of_truth', catalog_entry_hash='sha256:' + 'c' * 64)
    metadata = ProjectMetadata(project_path=str(root), docs_candidates=[member],
        docs_catalog_present=True, docs_catalog_valid=True)
    chunks = []
    offset, line = 0, 1
    for index, text in enumerate(texts):
        chunks.append(RetrievedChunk(source=str(root / path), chunk_index=index,
            text=text, score=1.0, metadata={
                'project_path': str(root), 'project_identity': 'fixture',
                'source_class': 'project_file', 'doc_scope': 'project',
                'project_doc_path': path, 'project_doc_content_hash': source_hash,
                'project_doc_catalog_entry_hash': member.catalog_entry_hash,
                'project_doc_authority': 'source_of_truth', 'authority': 'source_of_truth',
                'lifecycle_status': 'active', 'freshness': 'current', 'index_freshness': 'synchronized',
                'stable_chunk_id': f'child-{index}', 'parent_logical_id': 'parent',
                'char_span': [offset, offset + len(text)],
                'line_span': [line, line + len(text.splitlines()) - 1],
                'display_content_hash': hashlib.sha256(text.encode()).hexdigest(),
                'token_estimate': len(text) // 4, 'title': f'Binding contract {index}',
            }))
        offset += len(text)
        line += len(text.splitlines())
    acquisitions, controls = [], []

    class Dispatcher:
        def run(self, query, **kwargs):
            acquisitions.append((query, deepcopy(kwargs)))
            # Return the fixed prepared lane; never acquire more for patch mode.
            return SimpleNamespace(chunks=deepcopy(chunks))

    agent = SimpleNamespace(config=SimpleNamespace(query=SimpleNamespace(default_limit=4),
        retrieval=SimpleNamespace(default_mode='lexical')), store=SimpleNamespace())
    facade = SimpleNamespace(agent_gateway=SimpleNamespace(dispatcher_for=lambda *a, **k: Dispatcher()))
    service = ProjectDocsService(facade)
    monkeypatch.setattr(service, '_repository_identity', lambda root: 'fixture')
    monkeypatch.setattr(service, '_agent_instance', lambda: agent, raising=False)
    monkeypatch.setattr(service, 'read_project_metadata', lambda *a: deepcopy(metadata), raising=False)
    indexed = {'source': str(root / path), 'path': path, 'content_hash': source_hash,
               'source_class': 'project_file', 'doc_scope': 'project'}
    monkeypatch.setattr(service, '_indexed_project_doc_sources', lambda *a: [indexed])
    monkeypatch.setattr(service, '_partition_project_doc_state', lambda *a: ([indexed], [], []))
    monkeypatch.setattr(service, '_module_summaries', lambda *a: [])
    monkeypatch.setattr(service, '_resolve_module_filter', lambda *a, **k: (None, None))
    def inspect(*args):
        controls.append('inspect')
        return SimpleNamespace(reason_code='project_docs_ready', recommended_next_actions=[])
    facade.get_project_docs = service.get_project_docs
    facade.inspect_project_docs = inspect
    from docmancer.docs.project import ProjectMetadataReader
    metadata_reader = ProjectMetadataReader.read
    monkeypatch.setattr('docmancer.docs.project.ProjectMetadataReader.read', lambda *a, **k: deepcopy(metadata))
    context = ProjectContextService(facade)
    facade.get_project_context = context.get_project_context
    facade.read_project_metadata = lambda *a: deepcopy(metadata)
    unified = UnifiedDocsContextService(facade)
    return SimpleNamespace(root=root, chunks=chunks, service=service, context=context,
        unified=unified, acquisitions=acquisitions, controls=controls, agent=agent,
        metadata_reader=metadata_reader)


def test_final_merge_retains_qualified_windows_without_changing_acquisition(pipeline):
    p = pipeline
    bounded = p.service.query_project_docs(str(p.root), 'validate_binding',
        lookup_queries=('record binding',), limit=20)
    calls = deepcopy(p.acquisitions)
    p.acquisitions.clear()
    control = []
    retained = p.service.query_project_docs(str(p.root), 'validate_binding',
        lookup_queries=('record binding',), limit=20, retain_found_windows=True, _control_chunks=control)
    assert p.acquisitions == calls
    assert [row.model_dump() for row in control] == [row.model_dump() for row in bounded]
    assert len(retained) == 32 > len(bounded)
    assert sum(row.metadata['token_estimate'] for row in retained) > 4000
    assert sum(len(row.text.encode()) for row in retained) > 64 * 1024
    assert all(row.metadata['retrieval_query_matches']['query-original']['qualified'] is True for row in retained)


def test_project_control_view_and_routing_remain_bounded(pipeline):
    p = pipeline
    bounded = p.context.get_project_context(str(p.root), 'validate_binding', mode='project-only')
    calls, controls = deepcopy(p.acquisitions), list(p.controls)
    p.acquisitions.clear()
    p.controls.clear()
    retained = p.context.get_project_context(str(p.root), 'validate_binding', mode='project-only', retain_found_windows=True)
    assert p.acquisitions == calls and p.controls == controls
    assert retained.status == bounded.status
    assert retained.selection_decision == bounded.selection_decision
    assert retained.project_docs == bounded.project_docs
    assert retained.diagnostics['retrieval_routing'] == bounded.diagnostics['retrieval_routing']
    assert validate_routing_record(retained.diagnostics['retrieval_routing']) == []
    assert len(retained.context_pack) == 32
    assert sum(len(row['content'].encode()) for row in retained.context_pack) > 64 * 1024
    for row in retained.context_pack:
        assert row['char_end'] - row['char_start'] == len(row['content'])
        assert row['display_content_hash'] == hashlib.sha256(row['content'].encode()).hexdigest()


def test_explicit_public_patch_retains_windows_with_live_validation(pipeline, monkeypatch):
    import docmancer.docs.application._action_packet_part01 as authority
    p = pipeline
    reads = []
    original = authority.read_project_docs_catalog
    def read(root):
        reads.append(str(root))
        return original(root)
    monkeypatch.setattr(authority, 'read_project_docs_catalog', read)
    args = {'project_path': str(p.root), 'question': 'validate_binding', 'mode': 'project'}
    docs = handle_context_tool('get_docs_context', args, p.unified)
    assert docs['kind'] == 'docs_context'
    assert reads == []
    packet = handle_context_tool('get_docs_context', {**args, 'context_format': 'patch_context'}, p.unified)
    assert packet['kind'] == 'patch_context'
    assert len(packet['sources']) == 32
    assert sum(len(row['text'].encode()) for row in packet['sources']) > 64 * 1024
    assert packet['edit_ready'] is False
    assert len(reads) >= 4 * 32
    assert set(reads) == {str(p.root)}


def test_omitted_null_and_prose_do_not_enable_retention():
    calls = []
    class Facade:
        def get_docs_context(self, question, **kwargs):
            calls.append(kwargs)
            return {'status': 'success', 'context_pack': []}
    for args in ({}, {'context_format': None}):
        handle_context_tool('get_docs_context', {'question': 'patch edit code', **args}, Facade())
    assert calls[0] == calls[1]
    assert 'retain_found_windows' not in calls[0]
    handle_context_tool('get_docs_context', {'question': 'docs', 'context_format': 'patch_context'}, Facade())
    assert calls[-1]['retain_found_windows'] is True


def test_unsupported_facade_rejects_without_retry():
    class Facade:
        def get_docs_context(self, question):
            pytest.fail('unsupported facade must not be invoked')
    result = handle_context_tool('get_docs_context', {'question': 'binding', 'context_format': 'patch_context'}, Facade())
    assert result['error']['reason_code'] == 'unsupported_found_window_retention'


def test_ranking_retains_only_independently_qualified_eligible_windows(pipeline):
    p = pipeline
    sink = []
    p.service.get_project_docs(str(p.root), 'validate_binding', retain_found_windows=True, _retained_results=sink)
    good = sink[0]
    bad = [replace(good, stable_chunk_id='stale', stale=True),
           replace(good, stable_chunk_id='foreign', path='foreign.md'),
           replace(good, stable_chunk_id='unqualified', metadata={'retrieval_query_matches': {}})]
    rows = rerank_project_doc_chunks([*sink, *bad], question='validate_binding',
        intent=SimpleNamespace(broad=True), limit=1, finite_member_paths=frozenset({'rules.md'}),
        retain_found_windows=True)
    assert len(rows) == 32
    assert not {'stale', 'foreign', 'unqualified'} & {row.stable_chunk_id for row in rows}


def test_late_catalog_authority_change_is_rejected(pipeline, monkeypatch):
    import docmancer.docs.application._action_packet_part01 as authority
    p = pipeline
    original = authority.read_project_docs_catalog
    count = 0
    def read(root):
        nonlocal count
        count += 1
        if count == 33:
            path = p.root / 'docatlas.project-docs.yaml'
            path.write_text(path.read_text().replace('source_of_truth', 'supporting'))
        return original(root)
    monkeypatch.setattr(authority, 'read_project_docs_catalog', read)
    result = handle_context_tool('get_docs_context', {'project_path': str(p.root),
        'question': 'validate_binding', 'mode': 'project', 'context_format': 'patch_context'}, p.unified)
    assert result['error']['reason_code'] == 'invalid_action_packet'
    assert count >= 33


def test_partial_packet_preserves_explicit_constraints_and_window_bindings(pipeline):
    p = pipeline
    class Facade:
        def get_docs_context(self, question, **kwargs):
            raw = asdict(p.unified.get_docs_context(question, **kwargs))
            raw['required_target_paths'] = ['missing.py']
            return raw
    packet = handle_context_tool('get_docs_context', {'project_path': str(p.root),
        'question': 'validate_binding', 'mode': 'project', 'context_format': 'patch_context'}, Facade())
    assert packet['completeness'] == 'partial'
    assert packet['edit_ready'] is False
    assert len(packet['sources']) == 32
    assert any(row['kind'] == 'target_path' and row['value'] == 'missing.py' for row in packet['requirements'])
    original = {row.metadata['stable_chunk_id']: row for row in p.chunks}
    for row in packet['sources']:
        chunk = original[row['stable_id']]
        assert row['text'] == chunk.text
        assert row['content_sha256'] == hashlib.sha256(chunk.text.encode()).hexdigest()
        assert [row['char_start'], row['char_end']] == chunk.metadata['char_span']
        assert [row['line_start'], row['line_end']] == chunk.metadata['line_span']


def test_retention_does_not_expand_unqualified_or_foreign_lanes(pipeline):
    p = pipeline
    good = p.chunks[0]
    p.chunks.extend([
        good.model_copy(update={'chunk_index': 100, 'metadata': {**good.metadata,
            'stable_chunk_id': 'foreign', 'project_identity': 'another-project'}}),
        good.model_copy(update={'chunk_index': 101, 'text': 'Unrelated material without the requested identifier.',
            'metadata': {**good.metadata, 'stable_chunk_id': 'unqualified'}}),
        good.model_copy(update={'chunk_index': 102, 'metadata': {**good.metadata,
            'stable_chunk_id': 'stale', 'index_freshness': 'stale'}}),
    ])
    rows = p.service.query_project_docs(str(p.root), 'validate_binding', retain_found_windows=True)
    assert not {'foreign', 'unqualified', 'stale'} & {row.metadata['stable_chunk_id'] for row in rows}


def test_acquisition_source_content_reads_unchanged_validation_io_increases(pipeline, monkeypatch):
    from pathlib import Path
    p = pipeline
    reads, resolves, opens = [], [], []
    original_read, original_resolve = Path.read_text, Path.resolve
    original_open = Path.open
    def read(path, *args, **kwargs):
        reads.append(str(path))
        return original_read(path, *args, **kwargs)
    def resolve(path, *args, **kwargs):
        resolves.append(str(path))
        return original_resolve(path, *args, **kwargs)
    def open_path(path, *args, **kwargs):
        opens.append(str(path))
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(Path, 'resolve', resolve)
    monkeypatch.setattr(Path, 'open', open_path)
    args = {'project_path': str(p.root), 'question': 'validate_binding', 'mode': 'project'}
    handle_context_tool('get_docs_context', args, p.unified)
    baseline_reads, baseline_resolves = list(reads), len(resolves)
    reads.clear()
    resolves.clear()
    handle_context_tool('get_docs_context', {**args, 'context_format': 'patch_context'}, p.unified)
    assert str(p.root / 'rules.md') not in baseline_reads + reads
    assert str(p.root / 'rules.md') not in opens
    assert set(reads) == {str(p.root / 'docatlas.project-docs.yaml')}
    assert len(reads) > len(baseline_reads)
    assert len(resolves) > baseline_resolves


def test_exact_document_fallback_schedule_unchanged(pipeline, monkeypatch):
    import docmancer.docs.application._project_docs_service_part03 as implementation
    p = pipeline
    calls = []
    def fallback(*args, **kwargs):
        calls.append(deepcopy(kwargs))
        return []
    monkeypatch.setattr(implementation, '_exact_document_index_chunks', fallback)
    p.service.get_project_docs(str(p.root), 'validate_binding', evidence_path='rules.md')
    baseline = deepcopy(calls)
    calls.clear()
    p.service.get_project_docs(str(p.root), 'validate_binding', evidence_path='rules.md',
        retain_found_windows=True, _retained_results=[])
    assert calls == baseline and len(calls) == 1


@pytest.mark.parametrize('mode', ['project', 'mixed', 'dependency'])
def test_unified_project_branches_forward_explicit_flag(pipeline, mode):
    p = pipeline
    calls = []
    def project(*args, **kwargs):
        calls.append(kwargs)
        raise RuntimeError('delegation observed')
    p.unified.service.get_project_context = project
    p.unified._dependency_prefetch_needed = lambda *args: False
    with pytest.raises(RuntimeError, match='delegation observed'):
        p.unified.get_docs_context('validate_binding', project_path=str(p.root),
            mode=mode, prepare_project_docs=False, retain_found_windows=True)
    assert calls[0]['retain_found_windows'] is True


def test_unsupported_project_facade_never_retries_bounded(pipeline):
    p = pipeline
    calls = []
    def legacy(root, query, *, tokens=None, limit=None, expand=None, module=None,
               module_path=None, scope=None, requirements=None, documentation_query_plan=None):
        calls.append(query)
        pytest.fail('legacy body must not run or be retried without retention')
    p.context.facade.get_project_docs = legacy
    with pytest.raises(TypeError, match='retain_found_windows'):
        p.context.get_project_context(str(p.root), 'validate_binding', mode='project-only',
            retain_found_windows=True)
    assert calls == []


def test_generic_kwargs_is_not_retention_support(pipeline):
    p = pipeline
    class DroppingFacade:
        def get_docs_context(self, question, **kwargs):
            kwargs.pop('retain_found_windows')
            kwargs.pop('_retention_ack')
            return p.unified.get_docs_context(question, **kwargs)
    packet = handle_context_tool('get_docs_context', {'project_path': str(p.root),
        'question': 'validate_binding', 'mode': 'project', 'context_format': 'patch_context'}, DroppingFacade())
    assert packet['error']['reason_code'] == 'unsupported_found_window_retention'


@pytest.mark.parametrize('layer', ['get_project_context', 'get_project_docs', 'query_project_docs', 'project_docs_delegate'])
def test_nested_dropping_delegation_rejects_before_delivery(pipeline, layer):
    p = pipeline
    if layer == 'project_docs_delegate':
        bounded = p.service.get_project_docs(str(p.root), 'validate_binding')
        p.service.facade._project_get_project_docs_impl = lambda *args, **kwargs: bounded
    else:
        owner = p.unified.service if layer == 'get_project_context' else p.context.facade if layer == 'get_project_docs' else p.service
        original = getattr(owner, layer)
        def dropping(*args, **kwargs):
            kwargs.pop('retain_found_windows', None)
            return original(*args, **kwargs)
        setattr(owner, layer, dropping)
    packet = handle_context_tool('get_docs_context', {'project_path': str(p.root),
        'question': 'validate_binding', 'mode': 'project', 'context_format': 'patch_context'}, p.unified)
    assert packet['error']['reason_code'] == 'unsupported_found_window_retention'


@pytest.fixture
def stored_generation(pipeline, monkeypatch):
    """Real disposable SQLite generation; only candidate acquisition is stubbed."""
    from docmancer.core.models import Document
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
    from docmancer.docs.project import ProjectMetadataReader
    p = pipeline
    source = str(p.root / 'rules.md')
    content = (p.root / 'rules.md').read_text()
    # Unlike the packing-only fixture, use live production metadata/hash reads.
    monkeypatch.setattr(ProjectMetadataReader, 'read', p.metadata_reader)
    read_metadata = lambda root: ProjectMetadataReader().read(root)
    monkeypatch.setattr(p.service, 'read_project_metadata', read_metadata)
    p.unified.service.read_project_metadata = read_metadata
    project_metadata = read_metadata(p.root)
    assert len(project_metadata.docs_candidates) == 1
    metadata = {key: value for key, value in p.chunks[0].metadata.items()
                if key not in {'stable_chunk_id', 'parent_logical_id', 'char_span', 'line_span',
                               'display_content_hash', 'token_estimate'}}
    metadata['project_doc_catalog_entry_hash'] = project_metadata.docs_candidates[0].catalog_entry_hash
    identity = ProjectDocsService._repository_identity(p.root)
    metadata['project_identity'] = identity
    monkeypatch.setattr(p.service, '_repository_identity', lambda root: identity)
    store = SQLiteStore(p.root / 'fixture-index.db', extracted_dir=p.root / 'fixture-extracted')
    indexed = store.add_documents([Document(source=source, content=content, metadata=metadata)])
    generation = indexed.generation_id
    assert generation == store.active_generation_id()
    with store._connect() as conn:
        ids = [row[0] for row in conn.execute(
            'SELECT hydration_id FROM retrieval_children WHERE generation_id=? ORDER BY chunk_index', (generation,))]
    assert ids
    p.chunks[:] = store.fetch_sections_by_id(ids, budget=1_000_000)
    p.agent.store = store
    statements, content_reads, loads, fallback_rows, file_reads, fallbacks = [], [], [], [], [], []
    from pathlib import Path
    path_open = Path.open
    class SourceFile:
        def __init__(self, handle):
            self.handle = handle
        def read(self, size=-1):
            value = self.handle.read(size)
            file_reads.append((source, size, len(value)))
            return value
        def __enter__(self):
            self.handle.__enter__()
            return self
        def __exit__(self, *args):
            return self.handle.__exit__(*args)
        def __getattr__(self, name):
            return getattr(self.handle, name)
    def open_path(path, *args, **kwargs):
        handle = path_open(path, *args, **kwargs)
        return SourceFile(handle) if str(path) == source else handle
    monkeypatch.setattr(Path, 'open', open_path)
    connect = store._connect

    class Cursor:
        def __init__(self, cursor, sql, params):
            self.cursor, self.sql, self.params = cursor, sql, params
        def fetchone(self):
            row = self.cursor.fetchone()
            if row is not None and self.sql.startswith('SELECT content FROM generation_sources'):
                content_reads.append((tuple(self.params), len(row['content'].encode())))
            return row
        def __iter__(self):
            return iter(self.cursor)
        def __getattr__(self, name):
            return getattr(self.cursor, name)

    class Connection:
        def __init__(self):
            self.connection = connect()
        def execute(self, sql, params=()):
            normalized = ' '.join(sql.split())
            statements.append((normalized, tuple(params)))
            return Cursor(self.connection.execute(sql, params), normalized, params)
        def __enter__(self):
            self.connection.__enter__()
            return self
        def __exit__(self, *args):
            try:
                return self.connection.__exit__(*args)
            finally:
                self.connection.close()

    monkeypatch.setattr(store, '_connect', Connection)
    document = SourceReferenceContext._document
    def load(context, source):
        if source not in context.documents:
            loads.append((context.scope.snapshot_id, source))
        return document(context, source)
    monkeypatch.setattr(SourceReferenceContext, '_document', load)
    sections = store.list_sections_for_source
    def list_sections(*args, **kwargs):
        rows = sections(*args, **kwargs)
        fallback_rows.append(len(rows))
        return rows
    monkeypatch.setattr(store, 'list_sections_for_source', list_sections)
    import docmancer.docs.application._project_docs_service_part03 as implementation
    exact = implementation._exact_document_index_chunks
    def exact_fallback(*args, **kwargs):
        rows = exact(*args, **kwargs)
        fallbacks.append(tuple(row.metadata['stable_chunk_id'] for row in rows))
        return rows
    monkeypatch.setattr(implementation, '_exact_document_index_chunks', exact_fallback)
    return SimpleNamespace(p=p, store=store, generation=generation, source=source,
        statements=statements, content_reads=content_reads, loads=loads, fallback_rows=fallback_rows,
        file_reads=file_reads, fallbacks=fallbacks)


def test_real_generation_preparation_and_nonempty_fallback_traces_match(stored_generation):
    f, p = stored_generation, stored_generation.p
    bounded_sink = []
    bounded = p.service.get_project_docs(str(p.root), 'validate_binding', evidence_path='rules.md',
        lookup_queries=('validate_binding record',))
    assert bounded.results
    assert f.fallback_rows and all(f.fallback_rows)
    assert len(f.fallbacks) == 1 and f.fallbacks[0]
    baseline = (deepcopy(f.statements), list(f.content_reads), list(f.loads),
                deepcopy(p.acquisitions), list(f.fallback_rows), list(f.file_reads), list(f.fallbacks))
    f.statements.clear()
    f.content_reads.clear()
    f.loads.clear()
    p.acquisitions.clear()
    f.fallback_rows.clear()
    f.file_reads.clear()
    f.fallbacks.clear()
    retained = p.service.get_project_docs(str(p.root), 'validate_binding', evidence_path='rules.md',
        lookup_queries=('validate_binding record',), retain_found_windows=True, _retained_results=bounded_sink)
    assert retained == bounded
    assert (f.statements, f.content_reads, f.loads, p.acquisitions, f.fallback_rows, f.file_reads, f.fallbacks) == baseline
    assert len(f.loads) == len(f.content_reads) == 2
    assert f.content_reads and all(params == (f.generation, f.source) for params, _ in f.content_reads)
    assert all(size == (p.root / 'rules.md').stat().st_size for _, size in f.content_reads)
    assert f.file_reads and {path for path, _, _ in f.file_reads} == {f.source}
    assert sum(size for _, _, size in f.file_reads) == (p.root / 'rules.md').stat().st_size
    assert bounded_sink
    for chunk in bounded_sink:
        evidence = chunk.metadata['_reference_evidence']
        assert chunk.metadata['generation_id'] == f.generation
        assert evidence['source']['scope']['snapshot_id'] == f.generation
        assert evidence['source']['scope']['project_id'] == p.service._repository_identity(p.root)
        assert evidence['text'] == chunk.content
        assert evidence['raw_document'][chunk.char_start:chunk.char_end] == chunk.content


def test_real_generation_duplicate_lookup_bindings_survive(stored_generation):
    f, p = stored_generation, stored_generation.p
    control = []
    rows = p.service.query_project_docs(str(p.root), 'validate_binding',
        lookup_queries=('validate_binding record',), retain_found_windows=True, _control_chunks=control)
    assert len({(row.source, row.chunk_index) for row in rows}) == len(rows)
    independent = [row for row in rows if row.metadata['retrieval_query_matches']['query-original']['qualified']]
    assert independent
    for row in independent:
        matches = row.metadata['retrieval_query_matches']
        assert any(key.startswith('query-lookup-') and trace['qualified'] for key, trace in matches.items())
        assert set(row.metadata['retrieval_query_ids']) == {key for key, trace in matches.items() if trace['qualified']}
        assert row.metadata['_reference_evidence']['source']['scope']['snapshot_id'] == f.generation


def test_real_generation_context_retention_preserves_control_and_read_traces(stored_generation):
    f, p = stored_generation, stored_generation.p
    bounded = p.context.get_project_context(str(p.root), 'validate_binding', mode='project-only')
    baseline = (deepcopy(f.statements), list(f.content_reads), list(f.loads),
                deepcopy(p.acquisitions), list(f.file_reads), list(p.controls))
    f.statements.clear()
    f.content_reads.clear()
    f.loads.clear()
    p.acquisitions.clear()
    f.file_reads.clear()
    p.controls.clear()
    retained = p.context.get_project_context(str(p.root), 'validate_binding', mode='project-only',
        retain_found_windows=True)
    assert (f.statements, f.content_reads, f.loads, p.acquisitions, f.file_reads, p.controls) == baseline
    assert retained.selection_decision == bounded.selection_decision
    assert retained.project_docs == bounded.project_docs
    assert retained.diagnostics['retrieval_routing'] == bounded.diagnostics['retrieval_routing']
    assert len(retained.context_pack) > len(bounded.context_pack)
    assert all(row['_reference_evidence']['source']['scope']['snapshot_id'] == f.generation
               for row in retained.context_pack)


def test_real_generation_unresolved_admission_is_not_uncapped(stored_generation):
    p = stored_generation.p
    control = []
    rows = p.service.query_project_docs(str(p.root), 'unmatched_identifier',
        retain_found_windows=True, _control_chunks=control)
    assert [row.model_dump() for row in rows] == [row.model_dump() for row in control]
    assert all(not trace['qualified'] for row in rows
               for trace in row.metadata['retrieval_query_matches'].values())
    results = []
    p.service.get_project_docs(str(p.root), 'unmatched_identifier',
        retain_found_windows=True, _retained_results=results)
    ranked = rerank_project_doc_chunks(results, question='unmatched_identifier',
        intent=SimpleNamespace(broad=True), finite_member_paths=frozenset({'rules.md'}), retain_found_windows=True)
    assert ranked == []
