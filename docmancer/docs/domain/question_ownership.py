"""Explicit parser-ownership and canonical-signature contract.

Ownership is intentionally observable so a new QuestionPlan rule cannot silently
steal a legacy-compatible question without a reviewed migration.  The gate also
freezes the semantic contract shape: keeping the same parser owner is not enough
if kind/subject/relation/target/cardinality or another proof field drifts.
"""
from __future__ import annotations

from dataclasses import dataclass

from docmancer.docs.domain.project_answer_contract import build_project_answer_contract
from docmancer.docs.domain.question_plan import compile_question_plan


CanonicalSignatureRow = tuple[
    str, str, str | None, str | None, str | None, str,
    str | None, str | None, int | None, str, str | None,
]
CanonicalSignature = tuple[CanonicalSignatureRow, ...]


@dataclass(frozen=True, slots=True)
class QuestionOwnership:
    owner: str
    parse_trace: tuple[str, ...]
    unresolved_parts: tuple[str, ...]
    signature: CanonicalSignature


@dataclass(frozen=True, slots=True)
class FrozenOwnershipCase:
    question: str
    owner: str
    signature: CanonicalSignature
    unresolved_parts: tuple[str, ...] = ()


def _signature(question: str) -> CanonicalSignature:
    contract = build_project_answer_contract(question)
    return tuple(
        (
            row.kind,
            row.subject,
            row.attribute,
            row.relation,
            row.target,
            row.value_kind,
            row.expected_value,
            row.item_kind,
            row.cardinality,
            row.response_mode,
            row.context,
        )
        for row in contract.proof_obligations
    )


FROZEN_OWNERSHIP_CASES = (
    FrozenOwnershipCase(
        "How does prepare_docs sync_project_docs work?",
        "legacy",
        ((
            "workflow", "prepare_docs", None, "sequence", "sync_project_docs",
            "text", None, None, None, "workflow", None,
        ),),
    ),
    FrozenOwnershipCase(
        "What does docs_status report and when should it be used?",
        "question_plan",
        (),
        (
            "unresolved_question_clause:What does docs_status report",
            "unresolved_question_clause:when should it be used",
        ),
    ),
    FrozenOwnershipCase(
        "What are the three public Docs MCP tools?",
        "legacy",
        ((
            "inventory", "Docs MCP", "public_tools", None, None,
            "identifier_list", None, "public_tool", 3, "names", None,
        ),),
    ),
    FrozenOwnershipCase(
        "Which source types are supported for indexing?",
        "question_plan",
        ((
            "inventory", "source types", "source", None, None,
            "identifier_list", None, "source", None, "names", "indexing",
        ),),
    ),
    FrozenOwnershipCase(
        "How do I sync project docs after changing a file?",
        "question_plan",
        ((
            "command", "sync_project_docs", None, "invocation", None,
            "call_expression", "sync_project_docs", None, None, "call", None,
        ),),
    ),
    FrozenOwnershipCase(
        "What are the three public Docs MCP tools and when do I use each one?",
        "question_plan",
        (
            (
                "relation", "get_docs_context", None, "public_tool_usage", None,
                "text", None, None, None, "value", "Docs MCP public tools",
            ),
            (
                "relation", "prepare_docs", None, "public_tool_usage", None,
                "text", None, None, None, "value", "Docs MCP public tools",
            ),
            (
                "relation", "docs_status", None, "public_tool_usage", None,
                "text", None, None, None, "value", "Docs MCP public tools",
            ),
        ),
    ),
    FrozenOwnershipCase(
        "How does evidence selection differ from question planning?",
        "question_plan",
        ((
            "comparison", "evidence selection", None, "contrast",
            "question planning", "text", None, None, None, "value", None,
        ),),
    ),
    FrozenOwnershipCase(
        "Where is the project answer contract documented?",
        "question_plan",
        ((
            "location", "project answer contract", None, "location", None,
            "path", None, None, None, "path", None,
        ),),
    ),
    FrozenOwnershipCase(
        "What happens when the preview plan is stale?",
        "question_plan",
        ((
            "relation", "preview plan", None, "conditional_outcome", None,
            "text", None, None, None, "value", "preview plan is stale",
        ),),
    ),
    FrozenOwnershipCase(
        "Why does clear-index always delete remote Qdrant collections?",
        "question_plan",
        ((
            "relation", "clear-index", None, "premise_check",
            "delete remote Qdrant collections", "text", "always", None,
            None, "value", None,
        ),),
    ),
    FrozenOwnershipCase(
        "What are the public tools and their purposes?",
        "question_plan",
        (
            (
                "purpose", "get_docs_context", None, "purpose", None,
                "text", None, None, None, "purpose", "Docs MCP public tools",
            ),
            (
                "purpose", "prepare_docs", None, "purpose", None,
                "text", None, None, None, "purpose", "Docs MCP public tools",
            ),
            (
                "purpose", "docs_status", None, "purpose", None,
                "text", None, None, None, "purpose", "Docs MCP public tools",
            ),
        ),
    ),
    FrozenOwnershipCase(
        "Назови три публичных инструмента Docs MCP и когда использовать каждый.",
        "question_plan",
        (
            (
                "relation", "get_docs_context", None, "public_tool_usage", None,
                "text", None, None, None, "value", "Docs MCP public tools",
            ),
            (
                "relation", "prepare_docs", None, "public_tool_usage", None,
                "text", None, None, None, "value", "Docs MCP public tools",
            ),
            (
                "relation", "docs_status", None, "public_tool_usage", None,
                "text", None, None, None, "value", "Docs MCP public tools",
            ),
        ),
    ),
    FrozenOwnershipCase(
        "What is the difference between evidence selection and question planning?",
        "question_plan",
        ((
            "comparison", "evidence selection", None, "contrast",
            "question planning", "text", None, None, None, "value", None,
        ),),
    ),
    FrozenOwnershipCase(
        "Explain the storage mutation coordination contract.",
        "question_plan",
        ((
            "relation", "storage mutation coordination", None, "storage_coordination", None,
            "text", None, None, None, "value", "cleanup and refresh",
        ),),
    ),
    FrozenOwnershipCase(
        (
            "What does Phase 3.1 require for RetrievalDispatcher, the raw topic, "
            "EvidenceRequirementSet hints, and vector or embedding calls?"
        ),
        "unsupported",
        (
            (
                "exact_fact", "vectors", None, "contract_fact", None,
                "text", None, None, None, "value", None,
            ),
            (
                "exact_fact", "RetrievalDispatcher", None, "contract_fact", None,
                "text", None, None, None, "value", None,
            ),
            (
                "exact_fact", "EvidenceRequirementSet", None, "contract_fact", None,
                "text", None, None, None, "value", None,
            ),
        ),
        ("legacy_unresolved:requirement_items",),
    ),
)


FROZEN_LEGACY_QUESTIONS = tuple(
    case.question for case in FROZEN_OWNERSHIP_CASES if case.owner == "legacy"
)
FROZEN_QUESTION_PLAN_QUESTIONS = tuple(
    case.question for case in FROZEN_OWNERSHIP_CASES if case.owner == "question_plan"
)
FROZEN_UNSUPPORTED_QUESTIONS = tuple(
    case.question for case in FROZEN_OWNERSHIP_CASES if case.owner == "unsupported"
)


def classify_question_ownership(question: str) -> QuestionOwnership:
    plan = compile_question_plan(question)
    contract = build_project_answer_contract(question)
    if plan.handled:
        owner = "question_plan"
        trace = tuple(plan.parse_trace)
    elif contract.unresolved_parts:
        owner = "unsupported"
        trace = tuple(contract.parse_trace)
    else:
        owner = "legacy"
        trace = ()
    return QuestionOwnership(
        owner,
        trace,
        tuple(contract.unresolved_parts),
        _signature(question),
    )


def frozen_ownership_mismatches() -> tuple[str, ...]:
    errors: list[str] = []
    for case in FROZEN_OWNERSHIP_CASES:
        observed = classify_question_ownership(case.question)
        if observed.owner != case.owner:
            errors.append(
                f"ownership drift: {case.question!r} -> "
                f"{observed.owner}, expected {case.owner}"
            )
        if observed.signature != case.signature:
            errors.append(
                f"canonical signature drift: {case.question!r} -> "
                f"{observed.signature!r}, expected {case.signature!r}"
            )
        if observed.unresolved_parts != case.unresolved_parts:
            errors.append(
                f"unresolved contract drift: {case.question!r} -> "
                f"{observed.unresolved_parts!r}, expected {case.unresolved_parts!r}"
            )
    return tuple(errors)


__all__ = [
    "CanonicalSignature", "CanonicalSignatureRow", "FROZEN_LEGACY_QUESTIONS",
    "FROZEN_OWNERSHIP_CASES", "FROZEN_QUESTION_PLAN_QUESTIONS",
    "FROZEN_UNSUPPORTED_QUESTIONS", "FrozenOwnershipCase", "QuestionOwnership",
    "classify_question_ownership", "frozen_ownership_mismatches",
]
