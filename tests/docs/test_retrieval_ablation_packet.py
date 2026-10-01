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


def test_legacy_ordering_calls_production_ranker_with_real_traces(tmp_path, monkeypatch):
    from docmancer.docs.application import context_candidate_ranking
    store, sources, filters = project_store(tmp_path, {
        'docs/one.md': '# Retry\n\nThe retry budget is three attempts.\n',
        'docs/two.md': '# Retry\n\nUse the retry budget only for transient failures.\n'})
    called = []
    ranker = context_candidate_ranking._facet_aware_candidates

    def observe(candidates, **kwargs):
        called.append(deepcopy(candidates))
        assert all(c['retrieval_query_matches']['query-original']['qualified'] for c in candidates)
        return ranker(candidates, **kwargs)

    monkeypatch.setattr(context_candidate_ranking, '_facet_aware_candidates', observe)
    def forbidden(*args, **kwargs):
        raise AssertionError('another product retrieval was called')
    monkeypatch.setattr(SQLiteStore, 'query', forbidden)
    from experiments.retrieval_ablation.adapters import reproject_structural_fts
    reproject_structural_fts(store)
    result = native_diagnostic(store, ['retry budget'], filters=filters, sources=sources,
                              assembly='owner_neighbors_v1', soft_gate='legacy', legacy_ordering=True)
    assert len(called) == 1 and len(called[0]) == 2
    assert result['paired_E_G_control']['model_visible_packet']['sources']
    assert result['ordering_qualification_traces'] == [
        c['retrieval_query_matches']['query-original'] for c in called[0]]
    assert result['packet_audit_errors'] == []
    assert result['model_visible_packet']['covered_query_ids'] == []
    from experiments.retrieval_ablation.review import summarize
    result.update(arm='E_GR_L', freeze_sha256='same')
    summary = summarize([result], planned_arms=('B', 'D_L', 'E_G_L', 'E_GR_L'))
    assert summary['planned_runs'] == 4
    assert summary['missing_arms'] == ['B', 'D_L', 'E_G_L']
    assert summary['execution_counts'] == {'EXECUTED': 1}


def test_ratio_hook_removes_only_threshold_and_retains_rejections():
    from docmancer.docs.domain import evidence_qualification as gate
    from experiments.retrieval_ablation.ratio_hook import without_ratio_threshold
    probe = {'query_terms': ['storage', 'xenolith', 'marigold', 'zephyr']}
    kwargs = {'query_id': 'q', 'visible_text': 'Storage persists records.'}
    assert gate.qualify_evidence(probe, **kwargs).reason == 'insufficient_visible_match'
    with without_ratio_threshold() as stats:
        assert gate.qualify_evidence(probe, **kwargs).qualified
        policies = [({'project_identity': 'foreign'}, 'wrong_project_identity'),
                    ({'freshness': 'stale'}, 'stale_evidence'),
                    ({'index_freshness': 'stale'}, 'unsynchronized_index'),
                    ({'risk_flags': ['unsafe']}, 'unsafe_evidence'),
                    ({'lifecycle_status': 'historical'}, 'lifecycle_not_allowed')]
        for facts, reason in policies:
            result = gate.qualify_evidence(probe, **kwargs,
                candidate={'project_identity': 'repo', **facts}, expected_project_identity='repo')
            assert not result.qualified and result.reason == reason
        for other_probe, text in [
            ({**probe, 'exact_terms': ['Client.beta']}, 'Storage persists records.'),
            ({**probe, 'parent_exact_terms': ['Client.beta']}, 'Storage persists records.'),
            ({**probe, 'bound_subjects': ['Client.beta']}, 'Storage persists records.'),
            (probe, 'Unrelated prose.'),
            (probe, '# Storage'),
            ({**probe, 'forbidden_evidence_terms': ['storage']}, 'Storage persists records.')]:
            result = gate.qualify_evidence(other_probe, query_id='q', visible_text=text)
            assert not result.qualified, (other_probe, result)
        assert stats['below_threshold_checks'] > 0
        assert stats['parent_exact_preserved_checks'] > 0
    assert not gate.qualify_evidence(probe, **kwargs).qualified


def test_ratio_hook_restores_lazily_imported_alias_after_exception(monkeypatch):
    import sys
    from types import ModuleType
    from docmancer.docs.domain import evidence_qualification as gate
    from experiments.retrieval_ablation.ratio_hook import without_ratio_threshold
    original = gate.qualify_evidence
    name = 'docmancer._ablation_late_alias_test'
    late = ModuleType(name)
    with pytest.raises(RuntimeError, match='controlled failure'):
        with without_ratio_threshold():
            late.qualify = gate.qualify_evidence
            monkeypatch.setitem(sys.modules, name, late)
            assert late.qualify is not original
            raise RuntimeError('controlled failure')
    assert late.qualify is original
    assert gate.qualify_evidence is original


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


def test_structural_assembly_expands_only_within_same_owner_without_new_search(tmp_path):
    from experiments.retrieval_ablation.adapters import SQLTrace, ReadPort, _eligible_rows
    from experiments.retrieval_ablation.packet import ProjectPacketPort
    text = '# API\n\n' + ('intro words ' * 45) + '\n\n' + ('target contract ' * 45) + '\n\n' + ('condition detail ' * 45) + '\n\n## Foreign\n\nforeign target contract\n'
    store, sources, filters = project_store(tmp_path, {'docs/api.md': text})
    trace = SQLTrace()
    with store._connect() as conn:
        _, allowed, _, _, _, _ = _eligible_rows(store, conn, trace, filters, sources)
        port = ProjectPacketPort(ReadPort(store, conn, trace), filters=filters, queries=('target contract',))
        ids = port.allowed_ids(allowed, 'target contract')
        rows = store._search_rows('target contract', 20, filters=filters)
        candidates = []
        for rank, row in enumerate(rows, 1):
            if row['id'] not in ids:
                continue
            candidates.append({'lane': 0, 'rank_in_lane': rank,
                               'stable_chunk_id': row['stable_chunk_id'],
                               'bm25_cost': row['rank'], 'row': row})
        assert candidates
        lanes = [{'query': 'target contract'}]
        result = port.pack_structural(candidates, lanes)
    assert result['assembly_reads'] > 0
    assert result['assembly_decisions']
    assert any(d['expanded'] for d in result['assembly_decisions'])
    assert all(d['parent_logical_id'] == d['assembled_parent_logical_id']
               for d in result['assembly_decisions'])
    assert result['packet_audit_errors'] == []


def test_structural_assembly_never_crosses_heading_owner(tmp_path):
    from experiments.retrieval_ablation.adapters import native_diagnostic
    text = '# One\n\n' + ('alpha target ' * 55) + '\n\n' + ('alpha condition ' * 45) + '\n\n## Two\n\n' + ('target foreign ' * 40) + '\n'
    store, sources, filters = project_store(tmp_path, {'docs/api.md': text})
    result = native_diagnostic(store, ['alpha target'], filters=filters, sources=sources,
                               assembly='owner_neighbors_v1')
    for decision in result['assembly_decisions']:
        assert decision['parent_logical_id'] == decision['assembled_parent_logical_id']
        assert decision['assembled_char_start'] >= decision['parent_char_start']
        assert decision['assembled_char_end'] <= decision['parent_char_end']
    assert result['packet_audit_errors'] == []
