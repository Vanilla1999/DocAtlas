"""Source-local dependency integrity; passing these checks is NOT answer proof."""
from __future__ import annotations

from dataclasses import asdict, replace
from functools import lru_cache
import json
from typing import Mapping
from .evidence_set_types import SourceKey, SpanRef, EvidenceSet
from .source_dependency_graph import digest, source_graph


def span_matches_source(ref: SpanRef, raw: str) -> bool:
    """Check exact bytes only. Caller separately checks current source access."""
    return bool(isinstance(raw,str) and isinstance(ref,SpanRef)
        and type(ref.start) is int and type(ref.end) is int
        and 0 <= ref.start < ref.end <= len(raw)
        and digest(raw)==ref.source.document_sha256
        and digest(raw[ref.start:ref.end])==ref.text_sha256)


def dependency_edges(raw: str, source: SourceKey):
    return source_graph(raw,source).edges


@lru_cache(maxsize=256)
def _set_id(members,edges):
    value={'members':[asdict(x) for x in members],'edges':[asdict(x) for x in edges]}
    return 'evidence-set:'+digest(json.dumps(value,sort_keys=True,separators=(',',':')))


def _ordered(spans):
    return tuple(sorted(set(spans),key=lambda s:(s.start,s.end,s.text_sha256)))


def _closure(seed,graph,max_spans):
    members={seed}
    while True:
        old=set(members)
        members.update(e.parent for e in graph.edges if e.child in old)
        for intro,children in graph.lists:
            if members.intersection(children):
                members.add(intro);members.update(children)
        if len(members)>max_spans:
            return None
        if members==old:
            return members


def _depth_error(members,edges,max_hops):
    incoming={ref:set() for ref in members}
    for edge in edges:
        if edge.child in incoming: incoming[edge.child].add(edge.parent)
    def depth(ref,seen):
        if ref in seen: return max_hops+1
        parents=incoming.get(ref,())
        return 1+max((depth(p,seen|{ref}) for p in parents),default=-1)
    return any(depth(ref,set())>max_hops for ref in members)


def build_dependency_sets(raw: str, source: SourceKey, start: int, end: int, *,
                          proposed_need_ids=(), max_hops=2, max_spans=8):
    """Reuse immutable structural proposals, not access or question approvals.

    Scope/path/document/window/limits are the cache key. Routing is attached for
    the current question only; validate_evidence_set still checks current access.
    """
    # bool and int compare equal inside compound LRU keys; validate the public
    # contract before any cache lookup, including previously warmed windows.
    if (type(max_hops) is not int or not 0 <= max_hops <= 2 or
            type(max_spans) is not int or not 1 <= max_spans <= 8):
        raise ValueError('dependency limits must satisfy hops<=2 and spans<=8')
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw):
        return (), ('source_window_mismatch',)
    sets, reasons = _build_source_sets(raw, source, start, end, max_hops, max_spans)
    ids = tuple(proposed_need_ids)
    return tuple(replace(item, proposed_need_ids=ids) for item in sets), reasons


@lru_cache(maxsize=128)
def _build_source_sets(raw: str, source: SourceKey, start: int, end: int,
                       max_hops: int, max_spans: int):
    """Complete structural alternatives overlapping a real retrieved window.

    All list siblings are required together; no partial prefix is mislabeled as
    a complete structural set. Exact requested-item support is checked later.
    """
    if (type(max_hops) is not int or not 0<=max_hops<=2 or
            type(max_spans) is not int or not 1<=max_spans<=8):
        raise ValueError('dependency limits must satisfy hops<=2 and spans<=8')
    if (type(start) is not int or type(end) is not int or not 0<=start<end<=len(raw)
            or digest(raw)!=source.document_sha256):
        return (),('source_window_mismatch',)
    graph=source_graph(raw,source);sets={};reasons=[]
    for kind,ref in graph.nodes:
        if kind in {'heading','list_intro','table_intro'} or not (ref.start<end and start<ref.end):
            continue
        members=_closure(ref,graph,max_spans)
        if members is None:
            reasons.append('dependency_budget_exceeded');continue
        edges=tuple(e for e in graph.edges if e.parent in members and e.child in members)
        if _depth_error(members,edges,max_hops):
            reasons.append('dependency_budget_exceeded');continue
        ordered=_ordered(members);identity=_set_id(ordered,edges)
        sets[identity]=EvidenceSet(identity,ordered,edges,())
    if not sets and not reasons: reasons.append('dependency_unavailable')
    return tuple(sets.values()),tuple(dict.fromkeys(reasons))


def validate_evidence_set(bundle: EvidenceSet, contracts, prepared_sources: Mapping):
    """Recompute every dependency from current prepared bytes, not cached flags.

    This function certifies source/structure integrity only. proposed_need_ids
    are routing hints and never a claim that those needs are supported.
    """
    reasons=[];members=bundle.member_spans
    if not members or len(members)>8 or len(bundle.edges)>64:
        return ('dependency_budget_exceeded',)
    keys={ref.source for ref in members}
    if len(keys)!=1:return ('mixed_source_scope',)
    key=next(iter(keys));record=prepared_sources.get(key)
    if not isinstance(record,Mapping):return ('source_not_prepared',)
    identity=record.get('source') or {}
    expected={'scope':asdict(key.scope),'document_id':key.document_id,
        'canonical_path':key.canonical_path,'content_sha256':key.document_sha256}
    if any(identity.get(k)!=v for k,v in expected.items()):
        return ('source_identity_mismatch',)
    raw=record.get('raw_document')
    if not isinstance(raw,str) or any(not span_matches_source(ref,raw) for ref in members):
        return ('source_span_mismatch',)
    graph=source_graph(raw,key);current=set(graph.edges);visible=set(members)
    if not visible<={ref for _,ref in graph.nodes}:reasons.append('unrecognized_source_unit')
    for edge in bundle.edges:
        if edge.parent not in visible or edge.child not in visible:
            reasons.append('missing_dependency_endpoint')
        if edge not in current:reasons.append('unverified_dependency_edge')
    for edge in current:
        if edge.child in visible and edge.parent not in visible:
            reasons.append('missing_dependency_endpoint')
        elif edge.child in visible and edge.parent in visible and edge not in bundle.edges:
            reasons.append('missing_dependency_edge')
    for intro,children in graph.lists:
        if visible.intersection(children) and not set((intro,*children))<=visible:
            reasons.append('incomplete_list_dependency')
    if _depth_error(visible,bundle.edges,2):reasons.append('dependency_budget_exceeded')
    known={c.need.need_id for c in contracts}
    if not set(bundle.proposed_need_ids)<=known:reasons.append('unknown_proposed_need')
    if bundle.set_id!=_set_id(_ordered(members),bundle.edges):reasons.append('set_identity_mismatch')
    return tuple(dict.fromkeys(reasons))
