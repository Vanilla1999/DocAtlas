"""Bounded optional search proposals, separate from question/proof authority.

All focal words come from original question spans. These keys never replace a
need's text, source scope, exact identities, conditions, or supported verdict.
"""
from __future__ import annotations

from dataclasses import replace
import re
from typing import Iterable

from docmancer.docs.domain.documentation_query_plan import DocumentationLookup, DocumentationQueryPlan
from docmancer.docs.domain.need_contracts import NeedContract, compile_need_contracts
from docmancer.docs.domain.need_composition import mask_protected
from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references
from docmancer.docs.domain.query_terms import supplemental_query_is_useful

SEARCH_ORIGINS = frozenset({'exact_anchor', 'exact_path', 'host_lookup',
    'canonical_intent', 'concept_alias', 'retrieval_hint', 'lexical_topic'})
# A grammatical subject after a composition verb, not a library/answer lexicon.
_COMPOSITION_FOCUS = re.compile(
    r'\b(?:состоит|состоят|образует|образуют|constitute|constitutes|compose|composes)\s+'
    r'(?P<focus>[\w.-]+(?:\s+[\w.-]+){0,3}?)(?=\s+(?:в|для|in|for)\b|[?.!]|$)', re.I)
_QUOTED = re.compile(r'`[^`\n]+`|"[^"\n]+"')
_ASCII_TOPIC = re.compile(r'(?<!\w)[a-z][a-z0-9_-]*(?:\s+[a-z][a-z0-9_-]*)*(?!\w)')


def _focal_texts(question: str, contract: NeedContract) -> tuple[str, ...]:
    need = contract.need
    a, b = need.query_span_start, need.query_span_end
    if not (0 <= a < b <= len(question) and question[a:b] == need.query_span_text):
        return ()
    clause = question[a:b]
    choices = []
    match = _COMPOSITION_FOCUS.search(mask_protected(clause))
    if match:
        choices.append(clause[match.start('focus'):match.end('focus')])
    for span in contract.focus_spans:
        if not (a <= span.start < span.end <= b):
            continue
        text = question[span.start:span.end]
        # Quote delimiters are not new content; retain significant leading
        # literal space rather than stripping it from the search spelling.
        quotation = next((m for m in _QUOTED.finditer(question, a, b)
                          if m.start() <= span.start and span.end <= m.end()), None)
        if quotation:
            text = quotation[0]
        if text != clause and len(text) <= 160:
            choices.append(text)
    # Categories are facets of the requested topic, not independent topics.
    # Combine only original spans; do not inject expected API names or answers.
    categories = tuple(span for span in contract.category_spans
                       if a <= span.start < span.end <= b)
    if categories and choices:
        topic = choices[0]
        choices.extend(f'{topic} {question[span.start:span.end]}' for span in categories
                       if len(topic) + 1 + span.end - span.start <= 160)
    if re.search(r'[А-Яа-яЁё]', mask_protected(clause)):
        choices.extend(m[0] for m in _ASCII_TOPIC.finditer(clause)
                       if len(m[0]) <= 160 and not any(
                           span.start <= a + m.start() and a + m.end() <= span.end
                           for span in categories))
    # The full independent clause is a safe search fallback, never a root rewrite.
    if clause.strip() != question.strip() and len(clause) <= 500:
        choices.append(clause)
    return tuple(dict.fromkeys(x for x in choices if supplemental_query_is_useful(x)))


def legacy_search_queries(plan: DocumentationQueryPlan, supplemental_queries: Iterable[str] = ()) -> tuple[DocumentationLookup, ...]:
    """Reproduce the old optional work envelope, excluding newly proposed keys."""
    result = []
    seen = set()
    for row in plan.queries:
        if (row.origin not in SEARCH_ORIGINS or row.query_id.startswith('query-focus-')
                or not supplemental_query_is_useful(row.text) or row.text in seen):
            continue
        result.append(row)
        seen.add(row.text)
    for index, text in enumerate(supplemental_queries, 1):
        if text and text not in seen and supplemental_query_is_useful(text):
            result.append(DocumentationLookup(f'query-supplemental-{index}', text,
                'retrieval_hint', False, relation='host_lookup'))
            seen.add(text)
    return tuple(result[:12])


def schedule_need_queries(plan: DocumentationQueryPlan, contracts: Iterable[NeedContract], *,
                          optional_limit: int = 12, supplemental_queries: Iterable[str] = ()) -> tuple[DocumentationLookup, ...]:
    """Reallocate existing slots; never multiply them by the number of needs.

    The two existing differently filtered root reads are outside this optional
    schedule. Public lookups/path requests have priority; needs are round-robin.
    """
    if type(optional_limit) is not int or not 0 <= optional_limit <= 12:
        raise ValueError('optional_limit must be an integer between zero and twelve')
    legacy = legacy_search_queries(plan, supplemental_queries)
    limit = min(optional_limit, len(legacy))
    groups = [_focal_texts(plan.original_question, contract) for contract in contracts]
    groups = [group for group in groups if group]
    existing = {row.text: row for row in legacy}
    selected = []
    seen = {plan.original_question.strip()}

    def add(row):
        key = row.text.strip()  # never normalize within a quote or code spelling
        if len(selected) < limit and key not in seen:
            selected.append(row)
            seen.add(key)

    if not groups:
        for row in legacy:
            add(row)
        return tuple(selected)
    for origin in ('exact_path', 'host_lookup'):
        for row in legacy:
            if row.origin == origin:
                add(row)
    # One initial direction per need before redundant directions. Bounded by
    # the shared limit even for a long or partly unsupported original request.
    for round_index in range(max(map(len, groups), default=0)):
        for need_index, group in enumerate(groups, 1):
            if len(selected) >= limit:
                break
            if round_index >= len(group):
                continue
            text = group[round_index]
            row = existing.get(text) or DocumentationLookup(
                f'query-focus-{need_index}-{round_index+1}', text, 'retrieval_hint', False,
                relation='host_lookup')
            add(row)
    for row in legacy:
        add(row)
    return tuple(selected)


def scheduled_plan(plan: DocumentationQueryPlan, *, supplemental_queries: Iterable[str] = ()) -> tuple[DocumentationQueryPlan, tuple[DocumentationLookup, ...]]:
    """Expose executed proposals to the same source/tagging plan, privately.

    Existing questions/obligations remain unchanged, including unscheduled and
    unsupported ones. Reapplication is deterministic; it cannot add more slots.
    """
    refs = resolve_references(plan.original_question, catalog=(), scope=ScopeKey('', '', ''))
    contracts = compile_need_contracts(plan.original_question, refs)
    scheduled = schedule_need_queries(plan, contracts, supplemental_queries=supplemental_queries)
    ids = {q.query_id for q in plan.queries}
    # Old requirement probes were not plan members: adding them would change
    # their qualification origin and can spuriously trigger component rescue.
    additions = tuple(q for q in scheduled if q.query_id.startswith('query-focus-')
                      and q.query_id not in ids)
    return (replace(plan, queries=(*plan.queries, *additions)) if additions else plan), scheduled


def requirement_search_probes(requirements) -> tuple[str, ...]:
    """The existing mandatory-probe allowance, not a new per-need allowance."""
    from .evidence_selection import requirement_probe_query
    return tuple(dict.fromkeys(text for item in requirements or ()
        if getattr(item, 'mandatory', False) and (text := requirement_probe_query(item))))[:8]
