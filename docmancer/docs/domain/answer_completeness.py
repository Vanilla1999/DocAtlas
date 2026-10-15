"""Context availability diagnostics, without inferred answer/task requirements.

Literal retrieval overlap and source authority are not semantic completeness or
mutation authorization. The downstream selector owns technical source eligibility.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA_VERSION = "answer-completeness-1.0"


def extract_project_answer_requirements(question: str) -> list[str]:
    """No story, layer, action or expected-answer requirements from free text."""
    return []


def extract_query_relevance_terms(question: str, intent: Any | None = None) -> list[str]:
    """Bounded literal retrieval terms; never a proof obligation or topic rewrite."""
    return list(dict.fromkeys(re.findall(r"[\w.-]+", question or "")))[:8]


def evaluate_project_answer_completeness(
    *, question: str, context_pack: list[dict[str, Any]],
    answer_available: bool, intent: Any,
) -> dict[str, Any]:
    available = bool(context_pack)
    answer_type = "partial" if available else "unavailable"
    return {
        "answer_type": answer_type,
        "answer_completeness": {
            "schema_version": SCHEMA_VERSION,
            "status": answer_type,
            "answer_type": answer_type,
            "coverage_score": 0.0,
            "matched_terms": [],
            "missing_terms": [],
            "coverage_by_requirement": [],
            "source_search_required": False,
            "source_search_status": "not_required",
            "disposition": "use_context" if available else "unavailable",
            "edit_ready": False,
            "reason_codes": ["context_only_no_semantic_certification"],
        },
        "recommended_next_actions": [],
    }


def derive_project_answer_completeness(
    *, question: str, context_pack: list[dict[str, Any]], answer_available: bool,
    intent: Any, support_decision: Any, assigned_requirement_ids: list[str],
) -> dict[str, Any]:
    result = evaluate_project_answer_completeness(
        question=question, context_pack=context_pack,
        answer_available=answer_available, intent=intent,
    )
    result["answer_completeness"]["canonical_support"] = {
        "answer_supported": False,
        "mandatory_requirement_ids": list(
            getattr(support_decision, "mandatory_requirement_ids", ()),
        ),
        "assigned_requirement_ids": sorted(assigned_requirement_ids),
    }
    return result
