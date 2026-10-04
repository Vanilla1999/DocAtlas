"""Scoped research selection replacement; real MCP serialization/validation."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from v2plan.next07_grounded_candidate import proposals, read_decision
from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
from docmancer.docs.application._project_context_service_shared import project_context_pack
from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application.model_visible_projection import (
    _docs_source, _snapshot_entry, validate_model_visible_projection,
)
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
from docmancer.docs.interfaces.mcp import context_tools


def prepared(service, root, question, trace):
    original = SourceReferenceContext.prepare
    inventory, bound = {}, {}

    def observe(context, chunks, *args, **kwargs):
        result = original(context, chunks, *args, **kwargs)
        for chunk in result:
            evidence = chunk.metadata.get('_reference_evidence')
            if not evidence:
                continue
            source = evidence['source']
            inventory[chunk.source] = dict(raw=evidence['raw_document'],
                identity=source['document_id'], canonical_path=source['canonical_path'],
                snapshot_id=source['scope']['snapshot_id'], url='',
                title=chunk.metadata.get('document_title') or '')
            bound[chunk.source] = context, chunk, args, kwargs
        return result

    with patch.object(SourceReferenceContext, 'prepare', observe):
        service.query_project_docs(root, question, scope='project')
    ranked, omissions = proposals(list(inventory.values()), question)
    trace.update(input=list(inventory.values()), proposed=ranked, omissions=omissions)
    lookup = {d['identity']: key for key, d in inventory.items()}
    rebound = []
    for row in ranked:
        context, chunk, args, kwargs = bound[lookup[row['identity']]]
        unit = chunk.model_copy(update={'text': row['content'], 'metadata': {
            **chunk.metadata, 'char_span': [row['start'], row['end']]}})
        rebound.extend(original(context, [unit], *args, **kwargs))
    with patch.object(service.project_docs, 'query_project_docs', return_value=rebound):
        result = service.get_project_docs(root, question, scope='project')
    trace['current_catalog_result'] = asdict(result)
    rows = project_context_pack(question=question, project_docs=result, dependency_docs=None)
    return [{**row, 'snippet': row['display_text'],
        'char_span': [row['char_start'], row['char_end']]} for row in rows]


def first_fit(rows, question, identity, trace, max_tokens=800):
    sources, snapshot, spans = [], {}, []
    trace['decisions'] = []
    for row in rows:
        decision = read_decision(row, question=question, expected_project_identity=identity)
        event = dict(path=row['path'], span=row['char_span'], allowed=decision.allowed,
            reason=decision.reason)
        trace['decisions'].append(event)
        if not decision.allowed:
            event['stage'] = 'rejected'
            continue
        source_identity = row['_reference_evidence']['source']
        key = (source_identity['document_id'], source_identity['scope']['snapshot_id'])
        start, end = row['char_span']
        if any(k == key and a <= start and end <= b for k, a, b in spans):
            event['stage'] = 'duplicate_contained'
            continue
        visible = _docs_source(row, display_snippet=row['snippet'])
        if visible is None:
            event['stage'] = 'invalid_source'
            continue
        # Keep the entire original quote, including original whitespace.
        visible.update(snippet=row['snippet'], project_identity=row['project_identity'],
            authority=row['authority'], scope=row['doc_scope'],
            line_start=row['line_start'], line_end=row['line_end'])
        packet = _payload(sources + [visible])
        cost = docs_context_budget_tokens(packet)
        event['whole_dto_cost'] = cost
        if len(sources) >= 3 or cost > min(800, max_tokens):
            event['stage'] = 'budget_omission'
            continue
        event['stage'] = 'selected'
        sources.append(visible)
        snapshot[visible['evidence_id']] = _snapshot_entry(row, visible)
        spans.append((key, start, end))
    payload = _payload(sources)
    trace['selected'] = deepcopy(sources)
    trace['validator'] = validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800)
    trace['budget'] = docs_context_budget_tokens(payload)
    return payload, snapshot


@contextmanager
def installed(service, trace):
    """Caller-controlled opt-in, never document-controlled; no payload handler patch."""
    native_context = service.get_project_context
    native_projection = context_tools.project_docs_context
    rows, request = [], {}

    def context(*args, **kwargs):
        retrieval = native_context(*args, **kwargs)
        root = kwargs.get('project_path') or args[0]
        question = kwargs.get('question') or args[1]
        if is_dataclass(retrieval):
            retrieval = asdict(retrieval)
        rows[:] = prepared(service, root, question, trace)
        request.update(question=question, identity=rows[0]['project_identity'] if rows else retrieval.get('project_identity'))
        trace['native_orchestration'] = deepcopy(retrieval)
        # Discard competing native selection, not a fallback or merged packet.
        retrieval['context_pack'] = rows
        return retrieval

    def projection(*, retrieval, max_tokens=800, **kwargs):
        trace['projection_calls'] = trace.get('projection_calls', 0) + 1
        return first_fit(rows, request['question'], request['identity'], trace, max_tokens)

    trace['origins'] = dict(context=str(native_context), projection=str(native_projection),
        candidate_sha256=hashlib.sha256(Path(__file__).with_name('next07_grounded_candidate.py').read_bytes()).hexdigest())
    with patch.object(service, 'get_project_context', context), patch.object(
            context_tools, 'project_docs_context', projection):
        yield
    trace['restored'] = service.get_project_context == native_context and context_tools.project_docs_context is native_projection
