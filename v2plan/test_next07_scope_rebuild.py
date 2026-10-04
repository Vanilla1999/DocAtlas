"""Contract tests for scope transport and complete diagnostic accounting.

FakeCatalog is a test double for service boundaries, NOT guard acceptance.
Run test_next07_scope_native.py in the real project for public scope checks.
"""
from dataclasses import dataclass
from copy import deepcopy
from types import SimpleNamespace
import importlib.util
from pathlib import Path
import sys

import pytest

from v2plan import next07_grounded_public as wiring



@dataclass
class Chunk:
    source: str
    text: str
    metadata: dict

    def model_copy(self, *, update):
        return Chunk(update.get('source', self.source), update.get('text', self.text),
                     update.get('metadata', self.metadata))


@dataclass
class CatalogResult:
    results: list
    status: str = 'success'


class PreparedReference:
    def prepare(self, chunks):
        return list(chunks)


class FakeCatalog:
    """Models the documented all->None and module-path normalization boundary."""
    def __init__(self):
        self.project_docs = self
        self.calls = []
        self.query_calls = []
        self.context = PreparedReference()

    def query_project_docs(self, root, question, *, scope=None, module_path=None):
        self.query_calls.append((scope, module_path))
        assert scope != 'all', 'low-level query must not receive literal all'
        identity = dict(document_id='guide', canonical_path='guide.md', scope={'snapshot_id': 's'})
        row = Chunk('guide', '# Owner\n\nText.\n', {
            '_reference_evidence': {'raw_document': '# Owner\n\nText.\n', 'source': identity},
            'document_title': 'Owner', 'char_span': [0, 15]})
        return self.context.prepare([row])

    def get_project_docs(self, root, question, *, scope=None, module_path=None):
        self.calls.append((scope, module_path))
        internal_scope = 'module' if module_path else (None if scope == 'all' else scope)
        return CatalogResult(self.query_project_docs(root, question, scope=internal_scope, module_path=module_path))


@pytest.mark.parametrize('scope,module_path,internal_scope', [
    ('project', None, 'project'), ('all', None, None), (None, None, None),
    ('module', 'packages/one', 'module'), ('project', 'packages/one', 'module'),
    ('all', 'packages/one', 'module'), (None, 'packages/one', 'module'),
])
def test_preparation_uses_native_catalog_scope_boundary(monkeypatch, scope, module_path, internal_scope):
    service = FakeCatalog()
    monkeypatch.setattr(wiring, 'SourceReferenceContext', PreparedReference)
    monkeypatch.setattr(wiring, 'proposals', lambda docs, query: ([{
        'identity': docs[0]['identity'], 'content': docs[0]['raw'], 'start': 0, 'end': len(docs[0]['raw'])}], []))
    monkeypatch.setattr(wiring, 'project_context_pack', lambda **kw: [{
        'display_text': chunk.text, 'char_start': 0, 'char_end': len(chunk.text),
        'source_class': 'project_doc'} for chunk in kw['project_docs'].results])
    original = service.query_project_docs
    trace = {}
    rows = wiring.prepared(service, '/repo', 'question', trace, scope=scope, module_path=module_path)
    assert service.calls == [(scope, module_path)] * 2
    assert service.query_calls == [(internal_scope, module_path)]
    assert service.query_project_docs == original
    assert rows[0]['snippet'] == '# Owner\n\nText.\n'
    assert trace['source_request'] == {'scope': scope, 'module_path': module_path}


@pytest.mark.parametrize('arguments', [
    {'scope': 'project'}, {'scope': 'all'}, {'scope': None},
    {'scope': 'module', 'module_path': 'packages/one'},
    {'scope': 'project', 'module_path': 'packages/one'},
    {'module_path': 'packages/one'},
])
def test_rebuilt_scope_envelope(arguments):
    wiring._check_supported_request(arguments)


@pytest.mark.parametrize('arguments', [
    {'scope': 'foreign'}, {'module': 'guessed-name'}, {'lookup_queries': ['new topic']},
    {'lifecycle_intent': 'historical'}, {'request_intent': 'change'},
    {'mode': 'deps-only'}, {'libraries': ['external']},
])
def test_other_lanes_remain_explicitly_unsupported(arguments):
    with pytest.raises(NotImplementedError):
        wiring._check_supported_request(arguments)


def test_failed_preparation_restores_native_query(monkeypatch):
    service = FakeCatalog()
    monkeypatch.setattr(wiring, 'SourceReferenceContext', PreparedReference)
    monkeypatch.setattr(wiring, 'proposals', lambda docs, q: ([{
        'identity': 'guide', 'content': docs[0]['raw'], 'start': 0, 'end': len(docs[0]['raw'])}], []))
    def crash(**kwargs):
        raise TypeError('packing boundary')
    monkeypatch.setattr(wiring, 'project_context_pack', crash)
    before = service.query_project_docs
    with pytest.raises(TypeError, match='packing boundary'):
        wiring.prepared(service, '/repo', 'q', {}, scope='all')
    assert service.query_project_docs == before

