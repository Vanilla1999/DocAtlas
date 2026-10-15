"""Legacy conflict-plan adapter; no relation can be inferred from prose."""
from __future__ import annotations
from .need_composition import compositional_parts
from .question_plan_core import PlannedFacet, QuestionPlan


def conflict_question_plan(question: str) -> QuestionPlan | None:
    return None
