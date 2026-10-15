"""Unresolved original-span literal contracts; no semantics or source I/O."""
from __future__ import annotations
from dataclasses import dataclass, replace
import re
from typing import Literal
from .query_reference_binding import ReferencePlan, ResolvedReference, ScopeKey, query_mentions
from .question_retrieval_needs import RetrievalNeed, _literal_symbol_mentions, retrieval_needs


@dataclass(frozen=True, slots=True)
class QuerySpan:
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class NeedContract:
    need: RetrievalNeed
    focus_spans: tuple[QuerySpan, ...]
    constraint_spans: tuple[QuerySpan, ...]
    prerequisite_need_ids: tuple[str, ...]
    requirement: Literal['scalar', 'set', 'set_with_explanations', 'unknown']
    expected_count: int | None
    interpretation: Literal['supported', 'unresolved']
    alternative_spans: tuple[QuerySpan, ...] = ()
    category_spans: tuple[QuerySpan, ...] = ()


def _verified_locator_ids(question: str, references: ReferencePlan) -> frozenset[str]:
    """Accept only current, canonical resolved locator occurrences.

    This is placement, not proof of source identity: the qualifier still checks
    the nominated source against its prepared snapshot. A symbol may be promoted
    only by the resolver's double-quoted literal catalog-stem convention, never
    by a supplied role on a backtick or qualified symbol.
    """
    if (not isinstance(references, ReferencePlan) or references.question != question
            or references.catalog_complete is not True
            or not isinstance(references.scope, ScopeKey)
            or not all(isinstance(value, str) for value in (
                references.scope.project_id, references.scope.version, references.scope.snapshot_id))
            or not references.scope.project_id or not references.scope.snapshot_id
            or not isinstance(references.references, tuple)):
        return frozenset()
    mentions = query_mentions(question)
    if len(references.references) != len(mentions):
        return frozenset()
    locators = set()
    for ref, mention in zip(references.references, mentions):
        if (not isinstance(ref, ResolvedReference) or ref.mention != mention
                or type(ref.mention.start) is not int or type(ref.mention.end) is not int
                or type(ref.mention.explicit) is not bool):
            return frozenset()
        if ref.role == 'source_locator':
            quoted_stem = (mention.syntax_role == 'symbol_identity'
                and mention.explicit and mention.start > 0 and mention.end < len(question)
                and question[mention.start - 1] == question[mention.end] == '"'
                and re.fullmatch(r'[\w-]+', mention.text) is not None)
            if mention.syntax_role != 'source_locator' and not quoted_stem:
                return frozenset()
            if (ref.state == 'resolved' and ref.reason == 'unique_catalog_source'
                    and isinstance(ref.source_ids, tuple) and len(ref.source_ids) == 1
                    and isinstance(ref.source_ids[0], str) and ref.source_ids[0]):
                locators.add(mention.mention_id)
        elif ref.role != mention.syntax_role:
            return frozenset()
    return frozenset(locators)


def compile_need_contracts(question: str, references: ReferencePlan) -> tuple[NeedContract, ...]:
    """Retain original bytes without certifying any part or whole-root meaning.

    Current canonical locator occurrences place constraints outside the body;
    they never infer a subject, relation or requirement. Source-locator binding
    remains the separate current-source qualifier's responsibility.
    """
    needs = retrieval_needs(question)
    if not needs:
        return ()
    locator_ids = _verified_locator_ids(needs[0].query_span_text, references)
    symbols = tuple(mention for mention in _literal_symbol_mentions(needs[0].query_span_text)
                    if mention.mention_id not in locator_ids)
    exact = tuple(dict.fromkeys(mention.text.casefold() for mention in symbols))
    need = replace(needs[0], need_id='sentence-1', hard_exact=exact)
    focus = tuple(QuerySpan(mention.start, mention.end) for mention in symbols)
    return (NeedContract(need, focus, (), (), 'unknown', None, 'unresolved'),)
