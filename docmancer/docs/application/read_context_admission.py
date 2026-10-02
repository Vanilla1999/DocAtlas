"""Bounded, original-query context admission; never qualification or coverage.

Recompute source binding and lexical locality on each proposed visible window.
No generated query, source read, score-based approval or semantic claim is used.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from docmancer.docs.domain.evidence_qualification import qualify_evidence, _substantive_markdown_line
from docmancer.docs.domain.query_terms import documentation_query_terms, query_constraint_roles
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.source_dependency_graph import digest
from .need_context_disposition import _applicable_context
from .need_context_projection import _current_plan


@dataclass(frozen=True, slots=True)
class ReadContextAdmission:
    allowed: bool
    reason: str


def read_context_admission(candidate: Mapping[str, Any], *, question: str,
                           expected_project_identity: str | None,
                           lifecycle_intent: str = 'current') -> ReadContextAdmission:
    """A conservative local-topic route, independent of whole-query coverage.

    Three distinct original-query terms must coexist in a substantive sentence,
    including an adjacent lexical pair from the original query. A question echo
    is not context. This is a context-locality policy, NOT a lowered qualification
    ratio: qualification, coverage and answer permission remain unchanged.
    """
    def reject(reason: str) -> ReadContextAdmission:
        return ReadContextAdmission(False, reason)

    if not question or not expected_project_identity or candidate.get('source_class') != 'project_doc':
        return reject('missing_project_request')
    if candidate.get('instruction_risk_flags'):
        return reject('unsafe_evidence')
    root = candidate.get('_reference_root_plan')
    evidence = candidate.get('_reference_evidence')
    if not isinstance(root, Mapping) or not isinstance(evidence, Mapping):
        return reject('source_not_prepared')
    plan = _current_plan(root, question)
    if plan is None or plan.scope.project_id != expected_project_identity:
        return reject('reference_plan_mismatch')
    raw = evidence.get('raw_document')
    identity = evidence.get('source')
    if (not isinstance(raw, str) or not isinstance(identity, Mapping)
            or digest(raw) != identity.get('content_sha256')):
        return reject('source_snapshot_mismatch')
    body = str(candidate.get('snippet') or '')
    span = candidate.get('char_span')
    if (not isinstance(span, (list, tuple)) or len(span) != 2
            or any(type(x) is not int for x in span)
            or not 0 <= span[0] < span[1] <= len(raw)
            or raw[span[0]:span[1]] != body
            or not isinstance(evidence.get('char_start'), int)
            or not isinstance(evidence.get('char_end'), int)
            or not evidence['char_start'] <= span[0] < span[1] <= evidence['char_end']):
        return reject('source_window_mismatch')
    roles = query_constraint_roles(question)
    checked = qualify_evidence(
        {'query_text': question, 'query_origin': 'original',
         'query_terms': list(documentation_query_terms(question)),
         'exact_terms': list(roles.hard_exact), 'bound_subjects': list(roles.bound_subjects)},
        query_id='query-original', visible_text=body, evidence_text=body,
        candidate=candidate, expected_project_identity=expected_project_identity,
        lifecycle_intent=lifecycle_intent,
        catalog_role=str(candidate.get('catalog_role') or ''),
    )
    # Only the lexical ratio refusal is eligible for this separate route.
    # Unknown reference/source/semantic refusals fail closed.
    if checked.reason not in {'visible_fields', 'insufficient_visible_match'}:
        return reject(checked.reason)
    if checked.trace.get('missing_exact_terms') or checked.trace.get('missing_bound_subjects'):
        return reject('missing_exact_or_subject')
    if not checked.trace.get('reference_visible_span'):
        return reject('source_window_mismatch')
    # Existing constraint interpretation is a veto only, never a generated
    # retrieval probe or a topic/proof witness. Unresolved conditions stay closed.
    for contract in compile_need_contracts(question, plan):
        if contract.constraint_spans and not _applicable_context(contract, question, body):
            return reject('condition_support_unavailable')
    terms = {str(t).casefold() for t in checked.trace.get('body_matched_terms') or ()}
    if local_topic_witness(body, question=question, terms=terms):
        return ReadContextAdmission(True, 'bound_local_topic_context')
    return reject('no_local_topic_witness')


def local_topic_witness(body: str, *, question: str, terms: set[str],
                        require_pair: bool = True,
                        sentence_pattern: re.Pattern[str] | None = None) -> bool:
    """Shared substantive locality/echo checks, never source eligibility or proof.

    Original reads still require an adjacent pair. A separately checked typed
    relation preference may supply its own relation anchor instead; it cannot
    bypass the substantive sentence, three-term or question-echo checks.
    """
    query_words = re.findall(r'\w+(?:[.-]\w+)*', question.casefold())
    pairs = set(zip(query_words, query_words[1:]))
    # Local sentence evidence cannot be borrowed from headings, paths or other
    # paragraphs. Retain word order and function words for the lexical pair.
    for paragraph in re.split(r'\n\s*\n', body):
        raw_lines = paragraph.splitlines()
        lines = [_substantive_markdown_line(line) for index, line in enumerate(raw_lines)
                 if not line.lstrip().startswith(('#', '```', '~~~'))
                 and not re.fullmatch(r'[=-]{3,}', line.strip())
                 and not (index + 1 < len(raw_lines)
                          and re.fullmatch(r'[=-]{3,}', raw_lines[index + 1].strip()))]
        prose = ' '.join(lines) if sentence_pattern is not None else '\n'.join(lines)
        for sentence in re.split(r'(?<=[.!?])\s+|\n', prose):
            words = re.findall(r'\w+(?:[.-]\w+)*', sentence.casefold())
            local = terms & set(words)
            if ('?' in sentence or len(local) < 3
                    or ' '.join(words) in ' '.join(query_words)):
                continue
            if sentence_pattern is not None and not sentence_pattern.search(sentence):
                continue
            if not require_pair or any(a in local and b in local for a, b in pairs & set(zip(words, words[1:]))):
                return True
    return False


def iter_read_context_variants(candidates, *, query_plan, expected_project_identity,
                               max_tokens, diagnostics, lifecycle_intent='current'):
    """Finite original-byte windows, rechecked at prefit and final delivery."""
    from docmancer.docs.domain.context_blocks import source_block_alternatives
    from docmancer.docs.domain.context_windows import _focused_line_range, _focused_snippet, _projection_limits
    from .model_visible_projection import _docs_source, docs_context_budget_tokens
    from .context_selection import context_selection_decision
    from ._docs_context_payload import _payload

    question = str(query_plan.get('original_question') or '')
    public_ids = tuple(query_plan.get('public_query_ids') or ())
    explicit_paths = {str(p).replace('\\', '/').strip('/') for p in query_plan.get('explicit_paths') or ()}
    for original in candidates[:24]:
        if not isinstance(original, Mapping):
            continue
        if explicit_paths and str(original.get('path') or '').replace('\\', '/').strip('/') not in explicit_paths:
            continue
        evidence = original.get('_reference_evidence')
        if not isinstance(evidence, Mapping):
            continue
        raw, document = evidence.get('text'), evidence.get('raw_document')
        start, end = evidence.get('char_start'), evidence.get('char_end')
        if (not isinstance(raw, str) or not isinstance(document, str)
                or type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(document) or document[start:end] != raw):
            continue
        ranges = {(a, b) for a, b in source_block_alternatives(raw).spans if b - a <= 640}
        for limit in _projection_limits(raw):
            _, a, b = _focused_snippet(raw, (question,), limit=limit)
            if b - a <= 640:
                ranges.add((a, b))
        for a, b in sorted(ranges, key=lambda span: (-(span[1] - span[0]), span[0]))[:16]:
            normalized = _docs_source(dict(original), display_snippet=raw[a:b])
            if normalized is None:
                continue
            candidate = {**original, **normalized, 'snippet': raw[a:b],
                         'char_span': [start + a, start + b]}
            decision = read_context_admission(candidate, question=question,
                expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent)
            rows = diagnostics.setdefault('read_context_admission', [])
            if len(rows) < 32:
                rows.append({'candidate_id': normalized.get('evidence_id'),
                             'allowed': decision.allowed, 'reason': decision.reason})
            if not decision.allowed:
                continue
            normalized['line_start'], normalized['line_end'] = _focused_line_range(raw, a, b, original.get('line_start'))
            normalized['retrieval_query_matches'] = {}
            normalized['retrieval_query_ids'] = []
            selection = context_selection_decision([normalized], public_ids)
            if docs_context_budget_tokens(_payload([normalized], decision=selection, query_plan=query_plan)) <= max_tokens:
                yield dict(original), normalized


def project_read_context_fallback(candidates, **kwargs):
    from .model_visible_projection import _snapshot_entry
    from .context_selection import context_selection_decision
    from ._docs_context_payload import _payload

    for original, normalized in iter_read_context_variants(candidates, **kwargs):
        plan = kwargs['query_plan']
        selection = context_selection_decision([normalized], tuple(plan.get('public_query_ids') or ()))
        payload = _payload([normalized], decision=selection, query_plan=plan)
        public = payload['sources'][0]
        kwargs['diagnostics']['final_visible_evidence_ids'] = [public['evidence_id']]
        return payload, {public['evidence_id']: _snapshot_entry(original, public)}
    return None


def iter_prefit_context_variants(candidates, *, lifecycle_intent='current', **kwargs):
    """Preserve final-selection proposals and independently checked read windows.

    Do not union the unrestricted typed topical fallback: question echoes and
    scattered terms must not gain prefit eligibility from a weaker route.
    Every final window is checked again; this iterator grants no public credit.
    """
    from .need_context_projection import preferred_context_variants

    for original, variant, _ in preferred_context_variants(candidates, **kwargs):
        yield original, variant
    yield from iter_read_context_variants(candidates, lifecycle_intent=lifecycle_intent, **kwargs)


def project_checked_context_fallback(candidates, *, lifecycle_intent='current', **kwargs):
    """Keep existing typed context ordering, then the independent read route."""
    from .need_context_projection import project_need_context_fallback

    contextual = project_need_context_fallback(candidates, **kwargs)
    if contextual is not None:
        return contextual
    return project_read_context_fallback(candidates, lifecycle_intent=lifecycle_intent, **kwargs)
