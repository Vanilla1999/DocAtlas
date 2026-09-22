"""Actual source-span relations; byte identity does not itself prove an answer."""
from dataclasses import asdict, replace
from hashlib import sha256
import json
import pytest
from docmancer.docs.domain.evidence_set_types import SourceKey, SpanRef, EvidenceSet
from docmancer.docs.domain.query_reference_binding import ScopeKey
from docmancer.docs.domain.evidence_set_validation import (
    span_matches_source, dependency_edges, build_dependency_sets, validate_evidence_set)


def source(raw, *, version='v1', snapshot='g1', path='Guide.md'):
    return SourceKey(ScopeKey('p',version,snapshot),'doc1',path,sha256(raw.encode()).hexdigest())


def span(key, raw, text):
    start=raw.index(text)
    return SpanRef(key,start,start+len(text),sha256(text.encode()).hexdigest())


def prepared(key, raw):
    return {key: {'raw_document': raw, 'source': {
        'scope': asdict(key.scope), 'document_id': key.document_id,
        'canonical_path': key.canonical_path, 'content_sha256': key.document_sha256}}}


def bundles(raw, needle, **kwargs):
    key=source(raw); start=raw.index(needle)
    return key, *build_dependency_sets(raw,key,start,start+len(needle),**kwargs)


def test_original_unicode_and_crlf_coordinates_are_characters_with_exact_utf8_hash():
    raw='# ΣWorker\r\n\r\nΣWorker returns ` /--disabled`.\r\n'; key=source(raw)
    ref=span(key,raw,'ΣWorker returns ` /--disabled`.')
    assert span_matches_source(ref,raw)
    assert not span_matches_source(replace(ref,start=ref.start+1),raw)
    assert not span_matches_source(replace(ref,text_sha256='0'*64),raw)
    assert not span_matches_source(ref,raw.replace(' /','/'))


@pytest.mark.parametrize('start,end', [(-1,3),(0,999),(3,2),(1,1),(True,3)])
def test_malformed_or_empty_spans_are_not_source_bytes(start,end):
    raw='Original text';key=source(raw)
    assert not span_matches_source(SpanRef(key,start,end,key.document_sha256),raw)


@pytest.mark.parametrize('raw,kind,parent,child', [
    ('# OrbitResolver\n\nOrbitResolver runs tasks.\n','heading','# OrbitResolver','OrbitResolver runs tasks.'),
    ('# Modes\n\nThere are two modes:\n\n- Bronze: waits.\n- Jade: runs.\n','list','There are two modes:','- Jade: runs.'),
    ('# Mapping\n\n| Key | Value |\n|---|---|\n| ALPHA | gamma |\n','table','| Key | Value |','| ALPHA | gamma |'),
    ('# Queue\n\nOrbitResolver is the request queue.\n\nOrbitResolver runs tasks after delivery.\n','definition','OrbitResolver is the request queue.','OrbitResolver runs tasks'),
    ('# Queue\n\nOrbitResolver processes requests.\n\nIt uses a bounded buffer.\n','anaphora','OrbitResolver processes requests.','It uses a bounded buffer.'),
    ('# Queue\n\nOrbitResolver selects the first index.\n\nThis rule prevents dependency confusion.\n','cause','OrbitResolver selects the first index.','This rule prevents dependency confusion.'),
])
def test_declared_relations_have_actual_source_endpoints(raw,kind,parent,child):
    key=source(raw);edges=dependency_edges(raw,key)
    matches=[e for e in edges if e.kind==kind and parent in raw[e.parent.start:e.parent.end]
             and child in raw[e.child.start:e.child.end]]
    assert matches, edges
    assert all(span_matches_source(e.parent,raw) and span_matches_source(e.child,raw) for e in edges)


@pytest.mark.parametrize('raw,forbidden', [
    ('# One\n\nOrbitResolver processes requests.\n\n# Two\n\nIt uses a bounded buffer.\n', {'anaphora'}),
    ('# One\n\nOrbitResolver and OtherResolver process requests.\n\nIt uses a bounded buffer.\n', {'anaphora'}),
    ('# One\n\nOrbitResolver processes requests. OtherResolver does too.\n\nThis rule prevents confusion.\n', {'cause','anaphora'}),
    ('# One\n\nOrbitResolver processes requests.\n\nOtherResolver uses a bounded buffer.\n', {'anaphora','definition','cause'}),
    ('# One\n\nOrbitResolver processes requests.\n\nThe server listens on a port.\n', {'cause','definition','anaphora'}),
    ('# One\n\n```md\nThere are two modes:\n- Bronze: waits.\n- Jade: runs.\n```\n', {'list'}),
    ('# One\n\n```md\n| Key | Value |\n|---|---|\n| A | B |\n```\n', {'table'}),
    ('# One\n\n| Key | Value |\n|---|---|\n', {'table'}),
    ('# One\n\n| Key | Value |\n|---|---|\n| A | |\n', {'table'}),
    ('# Header only\n', {'heading'}),
])
def test_unrelated_or_ambiguous_text_does_not_create_a_dependency(raw,forbidden):
    assert not forbidden.intersection(e.kind for e in dependency_edges(raw,source(raw)))


def test_complete_list_closure_retains_all_top_level_items_not_nested_examples():
    raw=('# Modes\n\nThere are four modes:\n\n- Bronze: waits.\n- Jade: runs.\n'
         '  - Example: background processing.\n- Amber: pauses.\n- Indigo: stops.\n')
    key, sets, reasons=bundles(raw,'Jade')
    assert sets and not reasons
    covered='\n'.join(raw[s.start:s.end] for s in sets[0].member_spans)
    assert all(word in covered for word in ('Bronze','Jade','Amber','Indigo'))
    assert sum(e.kind=='list' for e in sets[0].edges)==4
    assert len(sets[0].member_spans)<=8
    assert validate_evidence_set(sets[0],(),prepared(key,raw))==()


def test_oversized_list_is_rejected_not_truncated_into_a_complete_set():
    raw='# Modes\n\nThere are twelve modes:\n\n'+''.join(f'- Mode{i}: acts.\n' for i in range(12))
    key, sets, reasons=bundles(raw,'Mode3')
    assert not sets and 'dependency_budget_exceeded' in reasons


def test_dependency_hop_limit_is_applied_to_real_closure():
    raw='# Queue\n\nOrbitResolver processes requests.\n\nIt uses a bounded buffer.\n'
    key, sets, reasons=bundles(raw,'bounded buffer',max_hops=1)
    assert not sets and 'dependency_budget_exceeded' in reasons
    key, sets, reasons=bundles(raw,'bounded buffer')
    assert sets and not reasons
    assert validate_evidence_set(sets[0],(),prepared(key,raw))==()


def test_missing_list_member_invalidates_the_proposed_full_bundle():
    raw='# Modes\n\nThere are two modes:\n\n- Bronze: waits.\n- Jade: runs.\n'
    key, sets, _=bundles(raw,'Jade'); assert sets
    bundle=sets[0]
    removed=next(s for s in bundle.member_spans if 'Bronze' in raw[s.start:s.end])
    forged=replace(bundle,member_spans=tuple(s for s in bundle.member_spans if s!=removed),
                   edges=tuple(e for e in bundle.edges if e.parent!=removed and e.child!=removed))
    assert 'incomplete_list_dependency' in validate_evidence_set(forged,(),prepared(key,raw))


def test_forged_rule_id_cannot_validate_a_real_pair_of_spans():
    raw='# Queue\n\nOrbitResolver processes requests.\n\nIt uses a bounded buffer.\n'
    key, sets, _=bundles(raw,'bounded buffer'); assert sets
    bundle=sets[0];bad=replace(bundle,edges=(replace(bundle.edges[0],rule_id='trust_metadata'),*bundle.edges[1:]))
    assert 'unverified_dependency_edge' in validate_evidence_set(bad,(),prepared(key,raw))


@pytest.mark.parametrize('field,value', [('version','v2'),('snapshot_id','g2'),('project_id','foreign')])
def test_same_bytes_in_different_scope_do_not_inherit_prepared_permission(field,value):
    raw='# Queue\n\nOrbitResolver runs tasks.\n';key,sets,_=bundles(raw,'runs');assert sets
    other=replace(key,scope=replace(key.scope,**{field:value}))
    assert 'source_not_prepared' in validate_evidence_set(sets[0],(),prepared(other,raw))


def test_prepared_record_cannot_disagree_with_its_mapping_key():
    raw='# Queue\n\nOrbitResolver runs tasks.\n';key,sets,_=bundles(raw,'runs');assert sets
    data=prepared(key,raw);data[key]['source']['canonical_path']='Other.md'
    assert 'source_identity_mismatch' in validate_evidence_set(sets[0],(),data)


def test_unknown_need_id_is_not_an_approval():
    raw='# Queue\n\nOrbitResolver runs tasks.\n';key,sets,_=bundles(raw,'runs');assert sets
    bad=replace(sets[0],proposed_need_ids=('invented-approved-need',))
    assert 'unknown_proposed_need' in validate_evidence_set(bad,(),prepared(key,raw))


def test_cold_validation_cache_performs_no_new_source_io(monkeypatch):
    from pathlib import Path
    import socket
    raw='# AuditQueue\n\nFreshWorker is a local queue.\n\nIt has a bounded buffer.\n'
    key=source(raw)
    def forbidden(*args,**kwargs):raise AssertionError('validation performed I/O')
    monkeypatch.setattr('builtins.open',forbidden)
    monkeypatch.setattr(Path,'read_text',forbidden)
    monkeypatch.setattr(socket,'socket',forbidden)
    sets,reasons=build_dependency_sets(raw,key,raw.index('bounded'),len(raw))
    assert sets and not reasons
    assert validate_evidence_set(sets[0],(),prepared(key,raw))==()


def test_a_rehashed_arbitrary_crop_is_not_a_recognized_structural_unit():
    from docmancer.docs.domain.evidence_set_validation import _set_id
    raw='# Queue\n\nOrbitResolver does not perform retries.\n';key=source(raw)
    arbitrary=span(key,raw,'perform retries.')
    bad=EvidenceSet(_set_id((arbitrary,),()),(arbitrary,),(),())
    assert 'unrecognized_source_unit' in validate_evidence_set(bad,(),prepared(key,raw))


def test_declared_edge_limit_rejects_large_replayed_graph():
    raw='# Queue\n\nOrbitResolver runs tasks.\n';key,sets,_=bundles(raw,'runs');assert sets
    bad=replace(sets[0],edges=sets[0].edges*65)
    assert 'dependency_budget_exceeded' in validate_evidence_set(bad,(),prepared(key,raw))


def test_repeated_structural_window_does_not_repeat_dependency_closure(monkeypatch):
    from docmancer.docs.domain import evidence_set_validation as validation
    raw = '# CacheResolver\n\nCacheResolver handles requests.\n\nThis rule prevents confusion.\n'
    key_ = source(raw)
    original = validation._closure
    calls = []
    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(validation, '_closure', counted)
    first, _ = validation.build_dependency_sets(raw, key_, 0, len(raw))
    before = len(calls)
    second, _ = validation.build_dependency_sets(raw, key_, 0, len(raw))
    assert first and first == second
    assert len(calls) == before


def test_structural_cache_is_bounded_and_never_caches_prepared_permission():
    from docmancer.docs.domain import evidence_set_validation as validation
    worker = getattr(validation, '_build_source_sets', None)
    assert worker is not None and hasattr(worker, 'cache_info')
    worker.cache_clear()
    for i in range(140):
        raw = f'# CacheResolver\n\nCacheResolver handles stage {i}.\n'
        key_ = source(raw)
        bundles, _ = validation.build_dependency_sets(raw, key_, 0, len(raw))
        assert bundles
    info = worker.cache_info()
    assert info.maxsize == 128 and info.currsize <= 128
    record = prepared(key_, raw)
    assert validation.validate_evidence_set(bundles[0], (), record) == ()
    record[key_]['source']['scope']['snapshot_id'] = 'changed'
    assert 'source_identity_mismatch' in validation.validate_evidence_set(bundles[0], (), record)


def test_cached_structure_never_copies_need_routing_from_another_question():
    from docmancer.docs.domain import evidence_set_validation as validation
    raw = '# CacheResolver\n\nCacheResolver handles requests.\n'
    key_ = source(raw)
    first, _ = validation.build_dependency_sets(raw, key_, 0, len(raw), proposed_need_ids=('need-a',))
    second, _ = validation.build_dependency_sets(raw, key_, 0, len(raw), proposed_need_ids=('need-b',))
    assert first[0].proposed_need_ids == ('need-a',)
    assert second[0].proposed_need_ids == ('need-b',)
    assert first[0].member_spans == second[0].member_spans


def test_cache_cannot_turn_boolean_limits_or_offsets_into_valid_integers():
    from docmancer.docs.domain import evidence_set_validation as validation
    raw = '# Cached\n\nCached handles tasks.\n'
    key_ = source(raw)
    validation.build_dependency_sets(raw, key_, 1, len(raw), max_hops=1)
    with pytest.raises(ValueError):
        validation.build_dependency_sets(raw, key_, 1, len(raw), max_hops=True)
    bundles, errors = validation.build_dependency_sets(raw, key_, True, len(raw), max_hops=1)
    assert not bundles and 'source_window_mismatch' in errors
