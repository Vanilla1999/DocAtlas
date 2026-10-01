"""Derive bounded structures from source windows already prepared by the index.

No new source/path lookup, model, translation, or evidence approval occurs here.
The current allowed catalog and original bytes are required, not metadata flags.
"""
from __future__ import annotations
from dataclasses import asdict
from typing import Any

from docmancer.docs.domain.evidence_set_types import SourceKey, EvidenceSet
from docmancer.docs.domain.evidence_set_validation import build_dependency_sets, validate_evidence_set


def prepare_dependency_sets(source_context: Any, retrieved, contracts, *, max_hops=2, max_spans=8) -> tuple[EvidenceSet,...]:
    result={}
    need_ids=tuple(c.need.need_id for c in contracts)[:12]
    for chunk in retrieved:
        label=str(chunk.source)
        catalog=source_context.sources.get(label)
        evidence=(chunk.metadata or {}).get('_reference_evidence') or {}
        window=(label,evidence.get('char_start'),evidence.get('char_end'))
        source_context.dependency_windows.pop(window,None)
        if catalog is None:
            source_context.dependency_rejections[label]=('source_not_prepared',)
            continue
        current=asdict(catalog)
        if evidence.get('source')!=current:
            source_context.dependency_rejections[label]=('source_identity_mismatch',)
            continue
        raw=evidence.get('raw_document');start=evidence.get('char_start');end=evidence.get('char_end')
        if (not isinstance(raw,str) or type(start) is not int or type(end) is not int
                or not 0<=start<end<=len(raw) or raw[start:end]!=chunk.text):
            source_context.dependency_rejections[label]=('source_window_mismatch',)
            continue
        key=SourceKey(catalog.scope,catalog.document_id,catalog.canonical_path,catalog.content_sha256)
        record={'source':current,'raw_document':raw}
        bundles,reasons=build_dependency_sets(raw,key,start,end,
            proposed_need_ids=need_ids,max_hops=max_hops,max_spans=max_spans)
        valid=[];rejected=list(reasons)
        for bundle in bundles:
            errors=validate_evidence_set(bundle,contracts,{key:record})
            if errors:
                rejected.extend(errors)
            elif len(result)<24:
                valid.append(bundle.set_id);result[bundle.set_id]=bundle
                source_context.dependency_sets[bundle.set_id]=bundle
            else:
                rejected.append('dependency_candidate_limit')
        source_context.dependency_sources[key]=record
        source_context.dependency_windows[(label,start,end)]=tuple(valid)
        source_context.dependency_rejections[label]=tuple(dict.fromkeys(rejected))
    return tuple(result.values())


def compact_dependency_record(bundle: EvidenceSet) -> dict:
    """Only proposals: source identity/raw bytes remain in _reference_evidence."""
    members=bundle.member_spans
    indices={span:i for i,span in enumerate(members)}
    return {'schema_version':'source-dependency-proposal-v1','set_id':bundle.set_id,
        'member_spans':[[s.start,s.end,s.text_sha256] for s in members],
        'edges':[[e.kind,indices[e.parent],indices[e.child],e.rule_id] for e in bundle.edges],
        'proposed_need_ids':list(bundle.proposed_need_ids)}
