"""Explicit parser-ownership contract for bounded project-doc questions.

Ownership is intentionally observable so a new QuestionPlan rule cannot silently
steal a legacy-compatible question without a reviewed migration.
"""
from __future__ import annotations

from dataclasses import dataclass

from docmancer.docs.domain.question_plan import compile_question_plan


@dataclass(frozen=True, slots=True)
class QuestionOwnership:
    owner: str
    parse_trace: tuple[str, ...]
    unresolved_parts: tuple[str, ...]


FROZEN_LEGACY_QUESTIONS = (
    "How does prepare_docs sync_project_docs work?",
    (
        "What does Phase 3.1 require for RetrievalDispatcher, the raw topic, "
        "EvidenceRequirementSet hints, and vector or embedding calls?"
    ),
)

FROZEN_QUESTION_PLAN_QUESTIONS = (
    "Which source types are supported for indexing?",
    "How do I sync project docs after changing a file?",
    "What are the three public Docs MCP tools and when do I use each one?",
    "How does evidence selection differ from question planning?",
    "Where is the project answer contract documented?",
    "What happens when the preview plan is stale?",
    "Why does clear-index always delete remote Qdrant collections?",
)


def classify_question_ownership(question: str) -> QuestionOwnership:
    plan = compile_question_plan(question)
    if plan.handled:
        return QuestionOwnership(
            "question_plan",
            tuple(plan.parse_trace),
            tuple(plan.unresolved_parts),
        )
    return QuestionOwnership("legacy", (), ())


def frozen_ownership_mismatches() -> tuple[str, ...]:
    errors: list[str] = []
    for question in FROZEN_LEGACY_QUESTIONS:
        owner = classify_question_ownership(question)
        if owner.owner != "legacy":
            errors.append(f"legacy ownership drift: {question!r} -> {owner.owner}")
    for question in FROZEN_QUESTION_PLAN_QUESTIONS:
        owner = classify_question_ownership(question)
        if owner.owner != "question_plan" or owner.unresolved_parts:
            errors.append(
                f"question-plan ownership drift: {question!r} -> "
                f"{owner.owner}:{owner.unresolved_parts}"
            )
    return tuple(errors)


__all__ = [
    "FROZEN_LEGACY_QUESTIONS", "FROZEN_QUESTION_PLAN_QUESTIONS",
    "QuestionOwnership", "classify_question_ownership",
    "frozen_ownership_mismatches",
]
