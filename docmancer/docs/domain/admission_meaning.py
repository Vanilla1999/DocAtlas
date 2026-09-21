"""Private per-need meanings. Unsupported residue never authorizes a rewrite."""
from __future__ import annotations

from dataclasses import dataclass, replace
import re
from .admission_grammar import MeaningSlot, parse_admission_frame
from .question_retrieval_needs import RetrievalNeed, retrieval_needs
from .query_reference_binding import ReferencePlan


@dataclass(frozen=True, slots=True)
class AdmissionDemand:
    need: RetrievalNeed
    operator: str
    arguments: tuple[MeaningSlot, ...]
    constraints: tuple[MeaningSlot, ...]
    unsupported_spans: tuple[tuple[int, int], ...]


def compile_admission_demands(question: str, references: ReferencePlan) -> tuple[AdmissionDemand, ...]:
    """Reuse existing need boundaries and retain exact original question spans."""
    needs = retrieval_needs(question)
    if not needs and question.strip():
        needs = (RetrievalNeed('need-1', 0, len(question), question, '', 'requested_part', '', ()),)
    result = []
    for need in needs:
        a, b = need.query_span_start, need.query_span_end
        frame = parse_admission_frame(question[a:b]) if references.question == question else None
        if frame is None or need.context:
            result.append(AdmissionDemand(need, 'unknown', (), (), ((a, b),)))
        else:
            shifted = lambda slots: tuple(replace(s, start=s.start+a, end=s.end+a) for s in slots)
            result.append(AdmissionDemand(need, frame.operator, shifted(frame.arguments),
                                          shifted(frame.constraints), ()))
    # Retrieval planning may intentionally omit an unrecognized sentence. An
    # equivalence audit may not: retain every uncovered meaningful source range.
    cursor = 0
    for start, end in sorted((n.query_span_start, n.query_span_end) for n in needs):
        if start > cursor and re.search(r"\w", question[cursor:start]):
            gap = RetrievalNeed(f"residue-{cursor}", cursor, start, question[cursor:start], "", "requested_part", "", ())
            result.append(AdmissionDemand(gap, "unknown", (), (), ((cursor, start),)))
        cursor = max(cursor, end)
    if cursor < len(question) and re.search(r"\w", question[cursor:]):
        gap = RetrievalNeed(f"residue-{cursor}", cursor, len(question), question[cursor:], "", "requested_part", "", ())
        result.append(AdmissionDemand(gap, "unknown", (), (), ((cursor, len(question)),)))
    return tuple(sorted(result, key=lambda d: d.need.query_span_start))


def same_supported_meaning(left: AdmissionDemand, right: AdmissionDemand) -> bool:
    """No inferred translation authority from equal literals or lexical overlap."""
    if left.unsupported_spans or right.unsupported_spans or left.operator == 'unknown':
        return False
    signature = lambda value: (value.operator,
        tuple(sorted((s.role, s.canonical) for s in value.arguments)),
        tuple(sorted((s.role, s.canonical) for s in value.constraints)))
    return signature(left) == signature(right)


def questions_have_same_supported_meaning(left: str, right: str) -> bool:
    """Pure whole-question audit, used only after both sides fully compile."""
    from .query_reference_binding import ScopeKey, resolve_references
    scope = ScopeKey('', '', '')
    a = compile_admission_demands(left, resolve_references(left, catalog=(), scope=scope))
    b = compile_admission_demands(right, resolve_references(right, catalog=(), scope=scope))
    return bool(a and len(a) == len(b) and all(same_supported_meaning(x, y) for x, y in zip(a, b)))
