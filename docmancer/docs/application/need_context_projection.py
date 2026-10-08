"""Checked context alternatives and empty fallback, never root answer proof.

Consume prepared candidates/original windows without extra search, source reads
or full-parent rescue. Relation/list preferences are ordering, not entailment.
"""
from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any, Mapping

from docmancer.docs.domain.context_blocks import source_block_alternatives
from docmancer.docs.domain.context_windows import (
    _focused_line_range, _focused_snippet, _projection_limits, _is_complete_source_span,
)
from docmancer.docs.domain.evidence_set_types import SourceKey, SpanRef, DependencyEdge, EvidenceSet
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.source_dependency_graph import source_graph
from docmancer.docs.domain.query_terms import documentation_query_terms
from docmancer.docs.domain.evidence_qualification import _visible_term_present, evidence_policy_rejection_reason
from docmancer.docs.domain.query_reference_binding import (
    QueryMention, ReferencePlan, ResolvedReference, ScopeKey,
)
from .need_context_disposition import classify_need_context
from .context_selection import context_selection_decision
from ._docs_context_payload import _payload
from .model_visible_projection import _docs_source, _snapshot_entry, docs_context_budget_tokens


def _current_plan(root: Mapping[str, Any], question: str) -> ReferencePlan | None:
    if root.get('question') != question:
        return None
    try:
        scope = ScopeKey(**root['scope'])
        references = tuple(ResolvedReference(QueryMention(**row['mention']),
            row['role'], row['state'], tuple(row['source_ids']), row['reason'])
            for row in root['references'])
        return ReferencePlan(question, references, scope, root['catalog_complete'])
    except (KeyError, TypeError, ValueError):
        return None


def _current_bundles(records, key: SourceKey) -> tuple[EvidenceSet, ...] | None:
    """Decode proposals, then the classifier re-derives every edge and digest."""
    if not isinstance(records, (list, tuple)) or len(records) > 24:
        return None
    bundles = []
    try:
        for row in records:
            if row.get('schema_version') != 'source-dependency-proposal-v1':
                return None
            members = row['member_spans']
            edges = row['edges']
            if not 0 < len(members) <= 8 or len(edges) > 64:
                return None
            if any(len(s) != 3 or type(s[0]) is not int or type(s[1]) is not int for s in members):
                return None
            spans = tuple(SpanRef(key, a, b, digest) for a, b, digest in members)
            decoded = []
            for kind, a, b, rule in edges:
                if type(a) is not int or type(b) is not int or not 0 <= a < len(spans) or not 0 <= b < len(spans):
                    return None
                decoded.append(DependencyEdge(kind, spans[a], spans[b], rule))
            bundles.append(EvidenceSet(row['set_id'], spans, tuple(decoded), tuple(row['proposed_need_ids'])))
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return tuple(bundles)


def iter_need_context_variants(
    candidates, *, query_plan: dict[str, Any], expected_project_identity: str | None,
    max_tokens: int | None, diagnostics: dict[str, Any],
):
    """Yield freshly checked original-byte alternatives, without selecting one."""
    question = str(query_plan.get('original_question') or '')
    if not question or not expected_project_identity:
        return None
    public_ids = tuple(query_plan.get('public_query_ids') or query_plan.get('query_ids') or ())
    outcomes = diagnostics.setdefault('need_context_fallback', [])
    for original in candidates[:24]:
        if not isinstance(original, Mapping) or original.get('source_class') != 'project_doc':
            continue
        if evidence_policy_rejection_reason({}, visible_text='', candidate=original,
                expected_project_identity=expected_project_identity,
                lifecycle_intent=original.get('_lifecycle_intent', 'current')) is not None:
            continue
        root = original.get('_reference_root_plan')
        evidence = original.get('_reference_evidence')
        if not isinstance(root, Mapping) or not isinstance(evidence, Mapping):
            continue
        plan = _current_plan(root, question)
        if plan is None or plan.scope.project_id != expected_project_identity:
            continue
        identity = evidence.get('source') or {}
        raw_document = evidence.get('raw_document')
        raw = evidence.get('text')
        start, end = evidence.get('char_start'), evidence.get('char_end')
        if (not isinstance(raw_document, str) or not isinstance(raw, str)
                or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(raw_document) or raw_document[start:end] != raw):
            continue
        key = SourceKey(plan.scope, str(identity.get('document_id') or ''),
            str(identity.get('canonical_path') or ''), str(identity.get('content_sha256') or ''))
        bundles = _current_bundles(original.get('_evidence_sets'), key)
        if bundles is None:
            continue
        records = {key: {'source': identity, 'raw_document': raw_document}}
        contracts = compile_need_contracts(question, plan)
        # Use existing finite window/block alternatives, not full-parent rescue.
        ranges = set(source_block_alternatives(raw).spans)
        if any(c.requirement in {'set', 'set_with_explanations'} for c in contracts):
            # Whole introduced lists are finite source structures, not parents.
            # The existing finite list enumeration remains a work bound.
            for intro, items in source_graph(raw_document, key).lists:
                left, right = intro.start, max((s.end for s in items), default=intro.end)
                if start <= left < right <= end and len(items) <= 8:
                    ranges.add((left - start, right - start))
        for limit in _projection_limits(raw):
            _, a, b = _focused_snippet(raw, (question,), limit=limit)
            ranges.add((a, b))
        ranges = sorted(ranges, key=lambda s: (
            not _is_complete_source_span(raw, raw[s[0]:s[1]], span_start=s[0]),
            -(s[1] - s[0]), s[0]))[:16]
        for a, b in ranges:
            snippet = raw[a:b]
            if not snippet.strip():
                continue
            normalized = _docs_source(dict(original), display_snippet=snippet)
            if normalized is None:
                continue
            normalized['line_start'], normalized['line_end'] = _focused_line_range(
                raw, a, b, original.get('line_start'))
            normalized.update(project_identity=expected_project_identity,
                authority=str(original.get('authority') or 'supporting'),
                scope=str(original.get('doc_scope') or 'project'))
            candidate = {**original, **normalized, 'char_span': [start + a, start + b],
                'char_start': start + a, 'char_end': start + b, 'snippet': snippet}
            dispositions = tuple(classify_need_context(contract, reference_plan=plan,
                candidate=candidate, bundles=bundles, prepared_sources=records)
                for contract in contracts[:12])
            permitted = tuple(row for row in dispositions if row.state != 'blocked')
            if len(outcomes) < 32:
                outcomes.append({'candidate_id': str(normalized.get('evidence_id') or ''),
                    'span': [start + a, start + b], 'dispositions': [asdict(row) for row in dispositions]})
            if not permitted:
                continue
            # No qualified/root/host attribution is manufactured for this row.
            normalized['retrieval_query_matches'] = {}
            normalized['retrieval_query_ids'] = []
            decision = context_selection_decision([normalized], public_ids)
            payload = _payload([normalized], decision=decision, query_plan=query_plan)
            yield dict(original), normalized, contracts, permitted


def precedence_context_variants(candidates, **kwargs):
    """Use explicit relation/disposition data, never infer precedence from prose."""
    for original, variant, contracts, dispositions in iter_need_context_variants(candidates, **kwargs):
        needs = {row.need_id for row in dispositions}
        wanted = tuple(contract.need.need_id for contract in contracts
                       if contract.need.relation == 'precedence' and contract.need.need_id in needs)
        if wanted:
            yield original, variant, wanted


def project_need_context_fallback(candidates, **kwargs):
    """Keep the empty-packet fallback for other unresolved request shapes."""
    for original, normalized, _, _ in iter_need_context_variants(candidates, **kwargs):
        plan = kwargs['query_plan']
        public_ids = tuple(plan.get('public_query_ids') or plan.get('query_ids') or ())
        decision = context_selection_decision([normalized], public_ids)
        payload = _payload([normalized], decision=decision, query_plan=plan)
        public = payload['sources'][0]
        entry = _snapshot_entry(original, public)
        kwargs['diagnostics']['final_visible_evidence_ids'] = [public['evidence_id']]
        return payload, {public['evidence_id']: entry}
    return None


def set_context_variants(candidates, **kwargs):
    """Prefer intact requested list context, without certifying category mapping."""
    question = str(kwargs['query_plan'].get('original_question') or '')
    for original, variant, contracts, dispositions in iter_need_context_variants(candidates, **kwargs):
        root = _current_plan(original['_reference_root_plan'], question)
        identity = original['_reference_evidence']['source']
        key = SourceKey(root.scope, identity['document_id'], identity['canonical_path'],
                        identity['content_sha256'])
        raw = original['_reference_evidence']['raw_document']
        body = variant['snippet']
        permitted = {row.need_id for row in dispositions}
        wanted = []
        for contract in contracts:
            count = contract.expected_count or len(contract.category_spans)
            if (contract.need.need_id not in permitted or
                    contract.requirement not in {'set', 'set_with_explanations'} or count < 2):
                continue
            focus = {term for span in contract.focus_spans
                     for term in documentation_query_terms(question[span.start:span.end])}
            if not focus or not all(_visible_term_present(term, body, exact=False) for term in focus):
                continue
            # This is structural completeness for ordering only. Each category's
            # meaning/explanation remains unverified; no full-support credit.
            if any(len(items) == count and raw[intro.start:max(s.end for s in items)] in body
                   for intro, items in source_graph(raw, key).lists):
                wanted.append(contract.need.need_id)
        if wanted:
            yield original, variant, tuple(wanted)
