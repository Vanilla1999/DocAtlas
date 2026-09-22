"""Native context-only routing must not manufacture full answer support."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import sqlite3

from tests.docs._reference_binding_fixtures import capture_reference_case, visible
from tests.docs.test_evidence_set_disposition import context_case
from docmancer.docs.application.need_context_disposition import classify_need_context

QUESTION = 'Which page title wins when the navigation configuration and Markdown content define different titles?'
FACT = 'The title in your nav setting overrides the Markdown heading.'


def test_safe_precedence_context_reaches_native_final_without_root_proof(tmp_path):
    cap = capture_reference_case(tmp_path, {'Guide.md': '# Page titles\n\n' + FACT + '\n'}, QUESTION)
    assert FACT in visible(cap), cap['public_payload']
    payload = cap['public_payload']
    assert payload['query_coverage'] != 'full'
    assert all(payload[k] is False for k in ('answer_supported', 'answer_available', 'edit_ready'))
    assert not any(k in json.dumps(payload) for k in
                   ('raw_document', '_evidence_sets', '_need_context', 'proposed_need_ids'))


def test_context_route_does_not_disclose_a_source_for_missing_explicit_class(tmp_path):
    docs = {'Guide.md': '# OtherClass\n\nOtherClass retry scheduling uses a bounded queue.\n'}
    q = 'Explain the detailed retry scheduling behavior of class MissingClass.'
    cap = capture_reference_case(tmp_path, docs, q)
    assert 'OtherClass retry scheduling' not in visible(cap)


def test_current_proof_is_not_reused_after_dependency_crop():
    contract, args = context_case('What is RelayClient default timeout?',
        '# RelayClient\n\nRelayClient default timeout is 7 seconds.\n')
    assert classify_need_context(contract, **args).state == 'supported'
    args['candidate']['snippet'] = 'RelayClient default timeout is 7 seconds.'
    assert classify_need_context(contract, **args).state != 'supported'
    args['candidate']['snippet'] = 'default timeout is 7 seconds.'
    assert classify_need_context(contract, **args).state == 'blocked'


def test_classifier_has_no_io_with_cold_or_warm_structural_cache(monkeypatch):
    from docmancer.docs.domain.source_dependency_graph import source_graph
    contract, args = context_case()
    source_graph.cache_clear()
    def forbidden(*a, **kw):
        raise AssertionError('classification performed I/O after source preparation')
    monkeypatch.setattr('builtins.open', forbidden)
    monkeypatch.setattr(Path, 'open', forbidden)
    monkeypatch.setattr(Path, 'read_text', forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    monkeypatch.setattr(sqlite3, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    assert classify_need_context(contract, **args).state == 'retrieval_only'
    assert classify_need_context(contract, **args).state == 'retrieval_only'


def test_existing_supported_partial_answer_never_enters_new_fallback(tmp_path, monkeypatch):
    import docmancer.docs.application.need_context_projection as target
    from tests.docs._evidence_set_fixtures import capture_case, old_assessment
    def forbidden(*a, **kw):
        raise AssertionError('topic fallback ran before an existing primary source')
    monkeypatch.setattr(target, 'project_need_context_fallback', forbidden)
    for case in ('pydantic-07', 'ruff-07'):
        cap = capture_case(tmp_path / case, case)
        assert old_assessment(case, cap)['claims']['required']['status'] == 'supported'
        assert cap['public_payload']['query_coverage'] != 'full'
