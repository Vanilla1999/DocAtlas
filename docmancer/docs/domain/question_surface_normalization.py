"""Legacy surface-adapter interfaces without semantic rewrites."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from docmancer.docs.domain.question_plan_core import QuestionPlan


@dataclass(frozen=True, slots=True)
class SurfaceNormalization:
    text: str
    rule: str


def _result(text: str, rule: str) -> SurfaceNormalization:
    return SurfaceNormalization(text=text, rule=rule)


def _semantic_identity(value: str) -> str:
    return value


def _ru_semantic_value(value: str) -> str:
    return value


def rebind_surface_plan(plan: QuestionPlan, *, raw: str, rule: str,
                        finalize: Callable[[str, QuestionPlan], QuestionPlan]) -> QuestionPlan:
    # A caller-supplied canonical plan is not proof of meaning equivalence.
    return QuestionPlan(clauses=(raw,), unresolved_parts=("unsupported_surface_rewrite",),
                        parse_trace=("surface_rewrite_unavailable",))


def normalize_question_surface(question: str) -> SurfaceNormalization | None:
    return None


__all__ = ["SurfaceNormalization", "normalize_question_surface", "rebind_surface_plan"]
