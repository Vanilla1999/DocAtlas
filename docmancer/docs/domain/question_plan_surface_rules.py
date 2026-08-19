"""Typed QuestionPlan rules for bounded natural-language surface families."""
from __future__ import annotations

import re

from docmancer.docs.domain.question_plan_core import PlannedFacet, QuestionPlan, _clean, _technical


_PUBLIC_TOOLS = ("get_docs_context", "prepare_docs", "docs_status")


def public_tool_usage(q: str) -> QuestionPlan | None:
    match = re.fullmatch(
        r"when\s+should\s+i\s+use\s+(get_docs_context|prepare_docs|docs_status)",
        _clean(q),
        re.I,
    )
    if match is None:
        return None
    subject, kind, aliases = _technical(match.group(1), "code_symbol")
    return QuestionPlan(
        facets=(PlannedFacet(
            "usage", subject, relation="usage", subject_kind=kind,
            subject_aliases=aliases, span_text=q,
        ),),
        clauses=(q,),
        parse_trace=("surface_rule:public_tool_usage",),
    )


def public_tools_with_purposes(q: str) -> QuestionPlan | None:
    if re.fullmatch(
        r"what\s+are\s+(?:the\s+)?public\s+(?:docs\s+mcp\s+)?tools\s+and\s+their\s+purposes",
        _clean(q),
        re.I,
    ) is None:
        return None
    return QuestionPlan(
        facets=tuple(
            PlannedFacet(
                "purpose", tool, relation="purpose", response_mode="purpose",
                subject_kind="code_symbol", subject_aliases=(tool,),
                context="Docs MCP public tools", span_text=q,
            )
            for tool in _PUBLIC_TOOLS
        ),
        clauses=(q,),
        parse_trace=("surface_rule:public_tools_purposes",),
    )


def python_version_support(q: str) -> QuestionPlan | None:
    cleaned = _clean(q)
    if re.fullmatch(r"what\s+python\s+versions?\s+does\s+docatlas\s+support", cleaned, re.I):
        subject = "DocAtlas"
    elif re.fullmatch(r"which\s+python\s+versions?\s+are\s+supported", cleaned, re.I):
        subject = "DocAtlas"
    else:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "attribute", subject, attribute="python_version",
            value_kind="version_range", response_mode="value", span_text=q,
        ),),
        clauses=(q,),
        parse_trace=("surface_rule:python_version_support",),
    )


def mcp_request_handling(q: str) -> QuestionPlan | None:
    if re.fullmatch(r"how\s+does\s+(?:the\s+)?mcp\s+server\s+handle\s+requests", _clean(q), re.I) is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "relation", "MCP server", relation="request_handling", span_text=q,
        ),),
        clauses=(q,),
        parse_trace=("surface_rule:mcp_request_handling",),
    )


def provider_request_timeout(q: str) -> QuestionPlan | None:
    if re.fullmatch(r"what\s+is\s+the\s+timeout\s+for\s+provider\s+requests", _clean(q), re.I) is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "attribute", "provider requests", attribute="timeout",
            value_kind="duration", response_mode="value", span_text=q,
        ),),
        clauses=(q,),
        parse_trace=("surface_rule:provider_request_timeout",),
    )


__all__ = [
    "mcp_request_handling", "provider_request_timeout", "public_tool_usage",
    "public_tools_with_purposes", "python_version_support",
]
