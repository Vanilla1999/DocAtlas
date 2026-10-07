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
    monkeypatch.setattr('docmancer.docs.project.ProjectMetadataReader.read', lambda *a, **k: deepcopy(metadata))
    context = ProjectContextService(facade)
    facade.get_project_context = context.get_project_context
    facade.read_project_metadata = lambda *a: deepcopy(metadata)
    unified = UnifiedDocsContextService(facade)
    return SimpleNamespace(root=root, chunks=chunks, service=service, context=context,
        unified=unified, acquisitions=acquisitions, controls=controls)


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
