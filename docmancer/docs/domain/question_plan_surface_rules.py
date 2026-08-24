"""Typed QuestionPlan rules for bounded natural-language surface families."""
from __future__ import annotations

import re

from docmancer.docs.domain.question_plan_core import (
    PlannedFacet,
    QuestionPlan,
    _clean,
    _technical,
    _unsafe_free_text,
)


_PUBLIC_TOOLS = ("get_docs_context", "prepare_docs", "docs_status")


def _governance_facet_plan(value: str, *, scope: str) -> PlannedFacet:
    """Classify only explicit governance value cues into typed proof families.

    The relation remains an internal QuestionPlan detail; the public question
    surface is unchanged. Typing must never invent an expected value from a
    topical noun alone: e.g. ``background location scope`` is not implicitly
    ``deferred`` and ``versioning policy`` is not a concrete version request.
    """

    normalized = " ".join(value.casefold().replace("_", " ").split())
    if re.search(r"\b(?:owner|ownership|владел|принадлеж)\w*\b", normalized):
        relation, value_kind, expected = "governance_ownership", "text", None
    elif re.search(r"\bversion\b|\bpinned?\b|\bверси(?:я|ю|и|ей|е)\b|\bзакреп\w*\b", normalized):
        relation, value_kind, expected = "governance_version", "version_range", None
    elif re.search(r"\b(?:defer(?:red|ral)?|отлож\w*)\b", normalized):
        relation, value_kind, expected = "governance_state", "text", "deferred"
    elif (
        re.fullmatch(r"notification\s+permission|разрешени\w*\s+уведом\w*", normalized)
        or re.search(
            r"\b(?:permission\s+(?:requirement|request)|required\s+permission|"
            r"уведом\w*\s+разрешени\w*\s+(?:треб\w*|запраш\w*))\b",
            normalized,
        )
    ):
        relation, value_kind, expected = "governance_requirement", "text", None
    else:
        relation, value_kind, expected = "governance_facet", "text", None
    return PlannedFacet(
        "relation",
        value,
        relation=relation,
        value_kind=value_kind,
        expected_value=expected,
        context=scope,
        response_mode="value",
        span_text=value,
    )


def governance_facets(q: str) -> QuestionPlan | None:
    match = re.fullmatch(
        r"\s*(?:"
        r"what\s+(?:project\s+)?(?:rules|policies)\s+govern\s+(.+?)\s*,\s*including\s+(.+?)|"
        r"какие\s+(?:проектные\s+)?(?:правила|политики)\s+определяют\s+(.+?)\s*,\s*включая\s+(.+?)"
        r")\s*[?!.]*\s*",
        q,
        re.I,
    )
    if match is None:
        return None
    scope = _clean(match.group(1) or match.group(3))
    raw_facets = match.group(2) or match.group(4) or ""
    facets = [
        _clean(re.sub(r"^(?:and|и)\s+", "", value, flags=re.I))
        for value in re.split(r"\s*,\s*|\s+(?:and|и)\s+", raw_facets, flags=re.I)
        if _clean(re.sub(r"^(?:and|и)\s+", "", value, flags=re.I))
    ]
    if (
        not scope
        or _unsafe_free_text(scope)
        or not 2 <= len(facets) <= 6
        or any(len(value) < 3 or _unsafe_free_text(value) for value in facets)
    ):
        return QuestionPlan(
            clauses=(q,),
            unresolved_parts=("unresolved_governance_facets",),
            parse_trace=("fail_closed:governance_facets",),
        )
    planned = [
        PlannedFacet(
            "relation", scope, relation="governed_scope",
            response_mode="value", span_text=scope,
        )
    ]
    planned.extend(_governance_facet_plan(value, scope=scope) for value in facets)
    return QuestionPlan(
        facets=tuple(planned),
        clauses=(q,),
        parse_trace=("frame:governance_facets",),
    )


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
        parse_trace=("surface_rule:public_tools_with_purposes",),
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
    if re.fullmatch(
        r"how\s+does\s+(?:the\s+)?mcp\s+server\s+handle\s+requests",
        _clean(q),
        re.I,
    ) is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "relation", "MCP server", relation="request_handling", span_text=q,
        ),),
        clauses=(q,),
        parse_trace=("surface_rule:mcp_request_handling",),
    )


def provider_request_timeout(q: str) -> QuestionPlan | None:
    if re.fullmatch(
        r"what\s+is\s+the\s+timeout\s+for\s+provider\s+requests",
        _clean(q),
        re.I,
    ) is None:
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
    "governance_facets", "mcp_request_handling", "provider_request_timeout",
    "public_tool_usage", "public_tools_with_purposes", "python_version_support",
]
