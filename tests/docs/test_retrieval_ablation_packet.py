"""Real project snapshots, reference preparation and public packet renderer."""
from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from experiments.retrieval_ablation.adapters import native_diagnostic


def project_store(tmp_path, documents=None):
    sources = documents or {'docs/retry.md': '# Retry\n\nThe retry budget is three attempts. Do not retry cancellation.\n'}
    root = tmp_path / 'project'
    root.mkdir()
    store = SQLiteStore(tmp_path / 'index.db')
    filters = {'project_identity': 'test-project', 'project_path': str(root),
               'source_class': 'project_doc', 'doc_scope': 'project'}
    store.add_documents([Document(source=name, content=text, metadata={
        **filters, 'source_path': name, 'project_doc_path': name,
        'project_doc_content_hash': hashlib.sha256(text.encode()).hexdigest(),
        'format': 'markdown', 'authority': 'source_of_truth',
    }) for name, text in sources.items()], recreate=True)
    return store, sources, filters


def test_native_project_packet_uses_real_renderer_and_validator(tmp_path):
    from docmancer.docs.application.model_visible_projection import (
        validate_model_visible_projection, docs_context_budget_tokens)
    store, sources, filters = project_store(tmp_path)
    before = store.db_path.read_bytes()
    result = native_diagnostic(store, ['What is the retry budget?'], filters=filters, sources=sources)
    packet = result['model_visible_packet']
    assert packet is not None
    assert result['packet_status'] == 'VALIDATED_PROJECT_PACKET'
    assert packet['sources']
    assert packet['answer_supported'] is False and packet['edit_ready'] is False
    assert packet['query_coverage'] == 'partial'
    assert packet['covered_query_ids'] == []
    assert validate_model_visible_projection(packet, snapshot=result['packet_snapshot'], max_tokens=800) == []
    assert docs_context_budget_tokens(packet) <= 800
    assert store.db_path.read_bytes() == before


def test_root_source_locator_is_enforced_before_exposure(tmp_path):
    docs = {'docs/target.md': '# Retry\n\nThe retry budget is three attempts.\n',
            'docs/foreign.md': '# Retry budget\n\n' + 'retry budget ' * 30}
    store, sources, filters = project_store(tmp_path, docs)
    result = native_diagnostic(store, ['According to file `docs/target.md`, what is the retry budget?'],
                              filters=filters, sources=sources, raw_limit=1)
    assert result['candidates']
    assert {c['row']['source'] for c in result['candidates']} == {'docs/target.md'}
    assert result['model_visible_packet'] is not None


def test_foreign_owner_and_exact_identity_are_not_soft_bypasses(tmp_path):
    store, sources, filters = project_store(tmp_path, {'docs/api.md':
        '# Client.beta\n\nThis method raises CancelledError. See Client.alpha.\n'})
    result = native_diagnostic(store, ['Does method Client.gamma raise CancelledError?'],
                              filters=filters, sources=sources)
    assert result['model_visible_packet'] is not None
    assert result['model_visible_packet']['status'] == 'insufficient_evidence'
    assert result['raw_hits'] == 0


def test_whole_units_skip_oversized_without_truncating_conditions(tmp_path):
    docs = {'docs/api.md': '# Retry\n\n' + ('retry budget depends on the configured condition. ' * 90) + '\n'}
    store, sources, filters = project_store(tmp_path, docs)
    result = native_diagnostic(store, ['retry budget'], filters=filters, sources=sources)
    packet = result['model_visible_packet']
    assert packet is not None
    for entry in packet.get('sources', []):
        assert any(entry['snippet'] == c['row']['text'].strip() for c in result['candidates'])
    assert result['packet_audit_errors'] == []


def test_native_project_packet_never_calls_custom_ordering(tmp_path, monkeypatch):
    store, sources, filters = project_store(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('custom ordering/packing called')
    for method in ('query', '_ranking_candidate', '_expand_row'):
        monkeypatch.setattr(SQLiteStore, method, forbidden)
    from docmancer.docs.application import context_candidate_ranking
    monkeypatch.setattr(context_candidate_ranking, '_facet_aware_candidates', forbidden)
    result = native_diagnostic(store, ['retry budget'], filters=filters, sources=sources)
    assert result['model_visible_packet']['sources']


def test_packet_source_entries_and_sections_are_distinct_limits(tmp_path):
    docs = {f'docs/{i}.md': f'# Retry {i}\n\nretry budget {i} attempts.\n' for i in range(5)}
    store, sources, filters = project_store(tmp_path, docs)
    result = native_diagnostic(store, ['retry budget'], filters=filters, sources=sources)
    packet = result['model_visible_packet']
    assert packet is not None
    assert 1 <= len(packet['sources']) <= 3
    assert result['packet_audit_errors'] == []


def test_versioned_or_incomplete_scope_is_not_silently_promoted(tmp_path):
    store, sources, filters = project_store(tmp_path)
    filters['resolved_version'] = '2'
    result = native_diagnostic(store, ['retry'], filters=filters, sources=sources)
    assert result['model_visible_packet'] is None
    assert result['packet_status'] == 'BLOCKED_SAFE_PACKET_ADAPTER'


def test_forged_heading_metadata_cannot_relabel_the_public_owner(tmp_path):
    import json
    store, sources, filters = project_store(tmp_path)
    with store._connect() as conn:
        row = conn.execute('SELECT id, metadata_json FROM retrieval_children').fetchone()
        metadata = json.loads(row['metadata_json'])
        metadata['heading_path'] = ['Forged unrelated API']
        conn.execute('UPDATE retrieval_children SET metadata_json=? WHERE id=?',
                     (json.dumps(metadata), row['id']))
    result = native_diagnostic(store, ['retry budget'], filters=filters, sources=sources)
    assert result['raw_hits'] == 0
    assert result['model_visible_packet']['status'] == 'insufficient_evidence'


def test_real_soft_ratio_bypass_does_not_forge_qualification(tmp_path):
    store, sources, filters = project_store(tmp_path)
    result = native_diagnostic(store, ['retry xenolith marigold zephyr cobalt verdigris'],
                              filters=filters, sources=sources)
    assert result['model_visible_packet']['sources']
    traces = result['qualification_traces']
    assert traces and all(t['qualified'] is False for t in traces)
    assert all(t['qualification_reason'] == 'insufficient_visible_match' for t in traces)
    assert result['model_visible_packet']['covered_query_ids'] == []


def test_mutated_final_quote_and_authority_flags_fail_actual_validation(tmp_path):
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection, _refresh_estimate
    store, sources, filters = project_store(tmp_path)
    result = native_diagnostic(store, ['retry budget'], filters=filters, sources=sources)
    packet = deepcopy(result['model_visible_packet'])
    packet['sources'][0]['snippet'] = 'The retry budget is infinite.'
    packet['answer_supported'] = True
    packet['edit_ready'] = True
    _refresh_estimate(packet)
    errors = validate_model_visible_projection(packet, snapshot=result['packet_snapshot'], max_tokens=800)
    assert any('snippet' in e for e in errors)
    assert any('supported answer' in e for e in errors)
    assert any('authorize edits' in e for e in errors)


def test_reviewer_revalidates_native_packet_and_keeps_quality_unmeasured(tmp_path):
    from experiments.retrieval_ablation.review import summarize
    store, sources, filters = project_store(tmp_path)
    result = native_diagnostic(store, ['retry budget'], filters=filters, sources=sources)
    result['freeze_sha256'] = 'same'
    summary = summarize([result])
    assert summary['semantic_evaluable'] == 0
    result['packet_budget_tokens'] += 1
    with pytest.raises(ValueError, match='invalid native'):
        summarize([result])
