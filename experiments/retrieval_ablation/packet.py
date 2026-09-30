"""Private project-Markdown PacketPort; no new public tool or answer authority.

Only the legacy lexical-overlap rejection may be bypassed, and only when the
same real qualification trace has no missing exact/parent identity. All other
rejections remain hard. This is deliberately conservative, not a replacement
semantic judge. Incoming qualified flags are never accepted as a certificate.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .adapters import SQLTrace, _canonical_reason, _eligible_rows


def _minimal_admission(qualification) -> bool:
    if qualification.qualified:
        return True  # Preserve genuine source/owner-qualified admission.
    trace = qualification.trace
    if trace.get('missing_exact_terms') or trace.get('missing_parent_exact_terms'):
        return False
    return (qualification.reason == 'insufficient_visible_match'
            and trace.get('admission_route') in (None, 'legacy_strict'))


def _qualify(original, query_text, project_identity):
    from docmancer.docs.domain.evidence_qualification import qualify_evidence
    traces, admitted = {}, False
    for query_id, text in query_text.items():
        q = qualify_evidence({'query_text': text}, query_id=query_id,
            visible_text=original['content'], evidence_text=original['content'],
            candidate=original, expected_project_identity=project_identity,
            catalog_role=str(original.get('catalog_role') or ''))
        traces[query_id] = dict(q.trace)
        admitted |= _minimal_admission(q)
    original['retrieval_query_matches'] = traces
    original['retrieval_query_ids'] = [k for k, v in traces.items() if v.get('qualified') is True]
    return admitted


def _queries(question: str, lookups: list[str]) -> dict[str, str]:
    return {'query-original': question, **{
        f'query-lookup-{i}': text for i, text in enumerate(lookups, 1)}}


def _prepare(store, diagnostic: dict, sources: dict, question: str, lookups: list[str], measurements=None):
    from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
    filters = diagnostic['filters']
    if (filters.get('source_class') != 'project_file' or filters.get('project_docs') is not True or not filters.get('project_path')
            or not filters.get('project_identity') or filters.get('doc_scope') != 'project'
            or filters.get('resolved_version') != ''):
        raise ValueError('PacketPort requires an explicit project-only scope')
    if diagnostic['generation_id'] != store.active_generation_id():
        raise ValueError('packet generation changed')
    with store._connect() as conn:
        generation, allowed, snapshots, _, scanned, scanned_bytes = _eligible_rows(store, conn, SQLTrace(), filters, sources)
    if generation != diagnostic['generation_id']:
        raise ValueError('packet generation changed')
    references = SourceReferenceContext(store, question=question, filters=filters)
    if not references.complete:
        raise ValueError('complete reference catalog required')
    query_text = _queries(question, lookups)
    prepared, rejected = [], []
    for candidate in diagnostic['candidates']:
        row = candidate['row']
        current = allowed.get(row['hydration_id'])
        # Compare native fields to current canonical rows, not supplied approval flags.
        if (current is None or row.get('id') != current['hydration_id']
                or any(row.get(k) != v for k, v in current.items() if k != 'id')):
            raise ValueError('native candidate changed since retrieval')
        if _canonical_reason(row, snapshots.get(row['source']), sources):
            raise ValueError('native candidate lost canonical integrity')
        hydrated = store.fetch_sections_by_id([row['hydration_id']])
        if len(hydrated) != 1 or hydrated[0].text != row['display_text']:
            raise ValueError('native hydration mismatch')
        chunks = references.prepare(hydrated)
        if len(chunks) != 1 or '_reference_evidence' not in chunks[0].metadata:
            raise ValueError('source reference preparation failed')
        chunk = chunks[0]
        original = {**chunk.metadata, 'path': chunk.metadata['source_path'],
            'content': chunk.text, 'snippet': chunk.text,
            'char_start': row['char_start'], 'char_end': row['char_end'],
            'line_start': row['line_start'], 'line_end': row['line_end']}
        for text in query_text.values():
            references.plan(text)
        admitted = _qualify(original, query_text, filters['project_identity'])
        if admitted:
            prepared.append((candidate, original))
        else:
            rejected.append({'stable_chunk_id': candidate['stable_chunk_id'],
                             'qualification': original['retrieval_query_matches']})
    if measurements is not None:
        measurements.append({'policy_scan_rows': scanned, 'policy_scan_display_bytes': scanned_bytes,
            'hydration_calls': len(diagnostic['candidates']),
            'reference_document_bytes': sum(len(doc[0].encode('utf-8')) for doc in references.documents.values() if doc)})
    return prepared, rejected, query_text


def _render(prepared: list[tuple[dict, dict]], query_text: dict[str, str]):
    from docmancer.docs.application._docs_context_payload import _payload
    from docmancer.docs.application.context_selection import context_selection_decision
    from docmancer.docs.application.model_visible_projection import _docs_source, _snapshot_entry

    public, snapshot = [], {}
    for candidate, original in prepared:
        row = _docs_source(original)
        if row is None:
            raise ValueError('whole unit is not renderable')
        # The production renderer trims surrounding whitespace only. Locate its
        # exact slice; do not normalize literals or invent original-file offsets.
        text = original['content']
        offset = len(text) - len(text.lstrip())
        start = original['char_start'] + offset
        end = start + len(row['snippet'])
        raw = original['_reference_evidence']['raw_document']
        if raw[start:end] != row['snippet']:
            raise ValueError('renderer changed canonical unit text')
        row.update(project_identity=original['project_identity'],
            authority=str(original.get('authority') or 'supporting'),
            scope=str(original.get('doc_scope') or 'project'),
            line_start=raw.count('\n', 0, start) + 1,
            line_end=raw.count('\n', 0, end - 1) + 1)
        if row['evidence_id'] in snapshot:
            raise ValueError('duplicate canonical public identity')
        snapshot[row['evidence_id']] = _snapshot_entry(original, row)
        public.append({**row, 'retrieval_query_matches': original['retrieval_query_matches'],
                       'retrieval_query_ids': original['retrieval_query_ids']})
    decision = context_selection_decision(public, query_text)
    return _payload(public, decision=decision), snapshot


def _key(candidate, original):
    ref = original['_reference_evidence']
    return (ref['source']['document_id'], ref['source']['content_sha256'],
            ref['char_start'], ref['char_end'])


def _bundles(prepared, query_text, project_identity, assembly):
    from .structure import bounded_bundle
    bundles, traces = [], []
    for candidate, original in prepared:
        if not assembly:
            bundles.append([(candidate, original)])
            continue
        bundle, trace = bounded_bundle(candidate, original)
        # Recompute actual gates on the entire assembled window. Seed approval
        # never qualifies new text, and required headings cannot be dropped.
        admissible = [(_qualify(o, query_text, project_identity), c.get('delivery_role')) for c, o in bundle]
        # A separately bound owner header is required structural context, not a
        # standalone factual assertion. Its real negative qualification trace is
        # retained; source/reference checks were performed by _context_row.
        if any(not admitted and role != 'owner_declaration' for admitted, role in admissible):
            trace['status'] = 'ASSEMBLED_WINDOW_REJECTED'
            bundle = []
        traces.append(trace)
        if bundle:
            bundles.append(bundle)
    return bundles, traces


def pack_native(store, diagnostic: dict, *, sources: dict[str, str], question: str,
                lookups: list[str] | None = None, max_tokens: int = 800,
                source_entries: int = 3, sections_per_source: int = 2,
                soft_gate: bool = False, assembly: bool = False) -> dict[str, Any]:
    """Pack native units or source-bound bundles in the unchanged seed order.

    Separate citations and every required heading consume actual DTO entries and
    tokens. Selection never tears a bundle or truncates an atomic condition.
    """
    from docmancer.docs.application.model_visible_projection import (
        docs_context_budget_tokens, validate_model_visible_projection,
        project_insufficient, _refresh_estimate,
    )
    if any(type(v) is not int or v <= 0 for v in (max_tokens, source_entries, sections_per_source)):
        raise ValueError('positive integer packet budgets required')
    if max_tokens > 800 or source_entries > 3 or sections_per_source > 2:
        raise ValueError('packet budgets exceed frozen public caps')
    inputs, before, scans = deepcopy(diagnostic), deepcopy(diagnostic), []
    prepared, rejected, query_text = _prepare(store, inputs, sources, question, lookups or [], scans)
    bundles, assembly_trace = _bundles(prepared, query_text, inputs['filters']['project_identity'], assembly)
    selected, omissions, per_source, used = [], [], {}, set()
    payload, snapshot = None, {}
    for bundle in bundles:
        # Canonical duplicates can share a required heading without receiving
        # an extra rank/vote. Original bundle and its dependency remain in trace.
        addition = [(c, o) for c, o in bundle if _key(c, o) not in used]
        if not addition:
            continue
        reason = None
        counts = dict(per_source)
        for candidate, _ in addition:
            key = candidate['row']['source']
            counts[key] = counts.get(key, 0) + 1
        if soft_gate and any(not original['retrieval_query_ids'] for c, original in bundle
                             if c.get('delivery_role') != 'owner_declaration'):
            reason = 'legacy_soft_gate'
        elif len(selected) + len(addition) > source_entries or max(counts.values()) > sections_per_source:
            reason = 'source_entry_cap'
        if reason is None:
            try:
                trial, bindings = _render([*selected, *addition], query_text)
            except ValueError:
                reason = 'whole_unit_not_renderable'
            else:
                if docs_context_budget_tokens(trial) > max_tokens:
                    reason = 'whole_unit_token_budget'
                elif validate_model_visible_projection(trial, snapshot=bindings, max_tokens=max_tokens):
                    raise ValueError('production DTO validation failed')
                else:
                    selected.extend(addition)
                    used.update(_key(c, o) for c, o in addition)
                    per_source, payload, snapshot = counts, trial, bindings
        if reason:
            omissions.append({'stable_chunk_id': bundle[0][0]['stable_chunk_id'], 'reason': reason})
    if payload is None:
        payload = project_insufficient(kind='docs_context', missing=['No complete admissible unit fits.'],
                                       recommended_next_action=None, max_tokens=max_tokens)
        payload.update(answer_supported=False, answer_available=False, edit_ready=False,
                       support_status='insufficient_evidence')
        _refresh_estimate(payload)
    # Freshly hydrate and re-derive selected bundles after final materialization,
    # with the same deterministic closure. No stored approval flags are trusted.
    selected_ids = {c['stable_chunk_id'] for c, _ in selected}
    final_input = {**inputs, 'candidates': [c for c in inputs['candidates'] if c['stable_chunk_id'] in selected_ids]}
    checked, final_rejections, _ = _prepare(store, final_input, sources, question, lookups or [], scans)
    fresh_bundles, _ = _bundles(checked, query_text, inputs['filters']['project_identity'], assembly)
    fresh = {(c['stable_chunk_id'], *_key(c, o)): o for bundle in fresh_bundles for c, o in bundle}
    if final_rejections or any(fresh.get((c['stable_chunk_id'], *_key(c, o))) != o for c, o in selected):
        raise ValueError('final packet lost hard-policy or reference eligibility')
    errors = validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=max_tokens)
    if docs_context_budget_tokens(payload) > max_tokens:
        errors.append('contract token budget exceeded')
    if any(payload.get(key) is not False for key in ('answer_supported', 'answer_available', 'edit_ready')):
        errors.append('retrieval-only authorization violation')
    if diagnostic != before:
        raise ValueError('native input mutated during packet delivery')
    if errors:
        raise ValueError('invalid final packet: ' + '; '.join(errors))
    return {'model_visible_packet': payload, 'packet_snapshot': snapshot,
        'packet_status': 'EXECUTED', 'audit_errors': errors,
        'budget_tokens': docs_context_budget_tokens(payload),
        'packet_rejections': rejected, 'packet_omissions': omissions,
        'prepared_candidates': [original for bundle in bundles for _, original in bundle],
        'selected_native_ids': [row['stable_chunk_id'] for row, _ in selected],
        'assembly_trace': assembly_trace, 'packet_preparation_cost': scans,
        'quality_status': 'UNJUDGED', 'packet_adapter_scope': 'project-markdown-only'}
