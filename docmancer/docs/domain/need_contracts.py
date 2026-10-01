"""Private original-span enrichment of existing RetrievalNeed; no source I/O."""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Literal
from .admission_grammar import parse_admission_frame
from .need_composition import independent_sentence_spans, mask_protected, compositional_parts
from .query_reference_binding import ReferencePlan, query_mentions
from .query_terms import query_constraint_roles
from .question_retrieval_needs import RetrievalNeed, retrieval_needs


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


def compile_need_contracts(question: str, references: ReferencePlan) -> tuple[NeedContract, ...]:
    """Retain unknown sentences rather than letting a known child consume them.

    Interpretation is distinct from context eligibility. A full independent
    request can be probed with the existing strict qualifier while its semantic
    interpretation remains unresolved and cannot certify whole-root coverage.
    """
    if not question.strip():
        return ()
    ranges = independent_sentence_spans(question) or ((0, len(question)),)
    rows = []
    for index, (start, end) in enumerate(ranges, 1):
        text = question[start:end]
        frame = parse_admission_frame(text) if references.question == question else None
        parts = compositional_parts(text) if references.question == question else ()
        if parts:
            old = retrieval_needs(text)
            original_exact = tuple(dict.fromkeys((*query_constraint_roles(text).hard_exact,
                *(m.text.casefold() for m in query_mentions(text) if m.syntax_role == 'symbol_identity'))))
            ids = tuple(f'sentence-{index}:part-{i+1}' for i in range(len(parts)))
            shift = lambda spans: tuple(QuerySpan(start+a, start+b) for a, b in spans)
            for number, part in enumerate(parts):
                context = '' if part.prerequisite is None else text[parts[part.prerequisite].start:parts[part.prerequisite].end]
                need = RetrievalNeed(ids[number], start+part.start, start+part.end,
                    text[part.start:part.end], old[0].subject if len(old) == 1 else '',
                    part.relation, context, original_exact)
                rows.append(NeedContract(need, shift(part.focus), shift(part.constraints),
                    () if part.prerequisite is None else (ids[part.prerequisite],),
                    part.requirement, part.expected_count, 'supported',
                    shift(part.alternatives), shift(part.categories)))
            continue
        old = retrieval_needs(text)
        subject = frame.subject if frame else old[0].subject if len(old) == 1 else ''
        relation = frame.operator if frame else old[0].relation if len(old) == 1 else 'requested_part'
        mentions = query_mentions(text)
        # Existing normalized identities stay intact; explicit literal spelling
        # with significant whitespace also stays in the original-span contract.
        exact = tuple(dict.fromkeys((*query_constraint_roles(text).hard_exact,
            *(m.text.casefold() for m in mentions if m.syntax_role == 'symbol_identity'))))
        need = RetrievalNeed(f'sentence-{index}', start, end, text, subject, relation, '', exact)
        focus = tuple(QuerySpan(start + m.start, start + m.end) for m in mentions
                      if m.syntax_role in {'symbol_identity', 'semantic_subject', 'unresolved'})
        condition = re.search(r'\b(?:when|if|unless|only|except|когда|если|только|кроме)\b',
                              mask_protected(text), re.I)
        constraints = ((QuerySpan(start + condition.start(), end),) if condition else ())
        rows.append(NeedContract(need, focus, constraints, (),
            'scalar' if frame else 'unknown', None, 'supported' if frame else 'unresolved'))
    return tuple(rows)
