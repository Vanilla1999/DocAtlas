"""Bind conflicting-setting questions before legacy topical-definition fallback."""
from __future__ import annotations
from .need_composition import compositional_parts
from .question_plan_core import PlannedFacet, QuestionPlan


def conflict_question_plan(question: str) -> QuestionPlan | None:
    parts = compositional_parts(question)
    if len(parts) != 1 or parts[0].relation != 'precedence':
        return None
    part = parts[0]
    if len(part.alternatives) != 2:
        return None
    left, right = (question[a:b] for a, b in part.alternatives)
    attribute = question[part.focus[0][0]:part.focus[0][1]] if part.focus else None
    context = ' '.join(question[a:b] for a, b in part.constraints) or None
    # Parsing identifies the question's relation, not an answer-side direction.
    # Do not claim the old proof model certifies the new dependency semantics.
    return QuestionPlan(facets=(PlannedFacet('relation', left, relation='precedence',
        target=right, attribute=attribute, context=context, span_text=question,
        query_span_start=0, query_span_end=len(question)),),
        clauses=(question,), parse_trace=('composition:conflicting_property',),
        consumed_spans=((0, len(question)),), component_scope_complete=False)
