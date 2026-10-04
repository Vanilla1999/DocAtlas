"""Scoped research selection replacement; real MCP serialization/validation."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import asdict, is_dataclass, replace
import hashlib
import json
import traceback
from functools import wraps
from pathlib import Path
from unittest.mock import patch

from v2plan.next07_grounded_candidate import proposals, read_decision
from docmancer.docs.domain.read_delivery_limits import (
    current_read_delivery_limits, use_read_delivery_limits,
)
from docmancer.docs.domain.source_coordinates import source_line_range
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
    limits = current_read_delivery_limits()
    token_limit = limits.max_tokens if limits is not None else min(800, max_tokens)
    source_limit = limits.max_sources if limits is not None else 3
    snippet_limit = limits.max_snippet_chars if limits is not None else 3_000
    sources, snapshot, spans = [], {}, []
    trace['delivery_limits'] = dict(max_tokens=token_limit, max_sources=source_limit,
                                    max_snippet_chars=snippet_limit)
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
        # Verify coordinates against the original slice, not a text search.
        # Do not repair a mutated line range to make it pass.
        raw = row['_reference_evidence']['raw_document']
        actual_lines = source_line_range(raw, start, end)
        if (raw[start:end] != row['snippet']
                or actual_lines != (row['line_start'], row['line_end'])):
            event['stage'] = 'invalid_source'
            event['reason'] = 'source_coordinate_mismatch'
            continue
        source_kwargs = {} if limits is None else {'max_snippet_chars': snippet_limit}
        if limits is not None:
            # Equal text at different original offsets is not the same citation.
            citation = json.dumps({'source': source_identity, 'span': [start, end]},
                                  ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            source_kwargs['evidence_id'] = 'ev-' + hashlib.sha256(citation.encode()).hexdigest()[:16]
        visible = _docs_source(row, display_snippet=row['snippet'], **source_kwargs)
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
        if ((source_limit is not None and len(sources) >= source_limit)
                or (token_limit is not None and cost > token_limit)):
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


def _record_exception(trace, stage, exc):
    """Private diagnostic only: no locals or traceback in the public DTO."""
    trace.setdefault('exceptions', []).append({
        'stage': stage,
        'exception_type': type(exc).__name__,
        'message': str(exc),
        'traceback': ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    })


def _replace_context_pack(result, rows):
    """Retain the service's typed contract and all nested canonical decisions."""
    if not is_dataclass(result) or isinstance(result, type):
        raise TypeError('get_project_context must return a dataclass, not a serialized DTO')
    # asdict is for diagnostic serialization, never the value returned to the
    # unified service. That service reads .context_pack, .status, .project_docs.
    return replace(result, context_pack=rows)


def _check_supported_request(arguments):
    """This existing harness prepares root-only, current project documentation.

    Do not silently widen a module request with prepared(scope='project'), or
    drop explicit lookup/lifecycle semantics. These routes need separate wiring;
    failure here is NOT successful source-guard or native acceptance evidence.
    """
    if (arguments.get('scope') != 'project'
            or arguments.get('module') or arguments.get('module_path')
            or arguments.get('lookup_queries')
            or arguments.get('lifecycle_intent') not in (None, 'current')
            or arguments.get('request_intent') not in (None, 'read')):
        raise NotImplementedError('I.4 wiring requires an explicit root-only current project read')


@contextmanager
def installed(service, trace, *, delivery_limits=None):
    """Typed research wiring; handler/source guards/validation remain native."""
    native_context = service.get_project_context
    native_projection = context_tools.project_docs_context
    native_validator = context_tools.validate_model_visible_projection
    app = service.unified_context
    native_unified = app.get_docs_context
    request = {}

    @wraps(native_context)
    def context(project_path, question, **kwargs):
        try:
            # The public facade is a variadic forwarder; its signature does
            # not expose project_path/question as named binding parameters.
            _check_supported_request(kwargs)
            result = native_context(project_path, question, **kwargs)
            root = project_path
            rows = prepared(service, root, question, trace)
            request.update(question=question,
                identity=rows[0]['project_identity'] if rows else None)
            trace['native_orchestration'] = asdict(result) if is_dataclass(result) else repr(result)
            trace['context_result_type'] = type(result).__qualname__
            return _replace_context_pack(result, rows)
        except Exception as exc:
            _record_exception(trace, 'project_context', exc)
            raise

    @wraps(native_unified)
    def unified(*args, **kwargs):
        # An early operational result must not reuse another request's rows.
        request.clear()
        try:
            return native_unified(*args, **kwargs)
        except Exception as exc:
            # Capture before the MCP dispatcher sanitizes handler exceptions.
            _record_exception(trace, 'unified_context', exc)
            raise

    def projection(*, retrieval, max_tokens=800, **kwargs):
        try:
            trace['projection_calls'] = trace.get('projection_calls', 0) + 1
            if 'question' not in request:
                raise RuntimeError('candidate project context was not reached for this request')
            rows = retrieval.get('context_pack')
            if not isinstance(rows, list):
                raise TypeError('project projection requires the guarded context_pack list')
            # Read actual post-unified/handler input, not cached pre-guard rows.
            # This preserves source removals and trust annotations from the
            # native path. first_fit and read_decision are not changed here.
            trace['projection_input'] = deepcopy(rows)
            return first_fit(rows, request['question'], request['identity'], trace, max_tokens)
        except Exception as exc:
            _record_exception(trace, 'projection', exc)
            raise

    @wraps(native_validator)
    def validator(*args, **kwargs):
        errors = native_validator(*args, **kwargs)
        trace.setdefault('handler_validation', []).append({
            'errors': list(errors), 'max_tokens': kwargs.get('max_tokens'),
        })
        # Final handler snapshot, after any capability binding. Offline audit
        # must not use an earlier snapshot with different source_uri fields.
        trace['final_snapshot'] = deepcopy(kwargs.get('snapshot') or {})
        return errors

    trace['origins'] = dict(context=str(native_context), projection=str(native_projection),
        unified=str(native_unified), validator=str(native_validator),
        candidate_sha256=hashlib.sha256(Path(__file__).with_name('next07_grounded_candidate.py').read_bytes()).hexdigest())
    trace['restored'] = False
    try:
        with ExitStack() as stack:
            if delivery_limits is not None:
                stack.enter_context(use_read_delivery_limits(delivery_limits))
            stack.enter_context(patch.object(service, 'get_project_context', context))
            stack.enter_context(patch.object(app, 'get_docs_context', unified))
            stack.enter_context(patch.object(context_tools, 'project_docs_context', projection))
            stack.enter_context(patch.object(context_tools, 'validate_model_visible_projection', validator))
            yield
    finally:
        trace['restored'] = (
            service.get_project_context == native_context
            and app.get_docs_context == native_unified
            and context_tools.project_docs_context is native_projection
            and context_tools.validate_model_visible_projection is native_validator
        )
