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

_GENERIC_COMPONENT_SUBJECTS = frozenset({
    "project", "repository", "system", "product", "server", "subsystem",
    "somewhere", "anywhere", "something",
    "проект", "репозиторий", "система", "продукт", "сервер", "подсистема",
    "где-то", "что-то",
})


def _component_subject(value: str) -> str:
    subject = _clean(value).strip("`\"'")
    return "" if subject.casefold() in _GENERIC_COMPONENT_SUBJECTS else subject


def semantic_components(q: str) -> QuestionPlan | None:
    """Compile the internal grammar used by closed EN/RU surface adapters."""
    cleaned = _clean(q)

    def unresolved() -> QuestionPlan:
        return QuestionPlan(
            clauses=(q,), unresolved_parts=("unresolved_query_subject",),
            parse_trace=("fail_closed:component_subject",),
        )

    match = re.fullmatch(r"component product overview for (.+)", cleaned, re.I)
    if match is not None:
        if not (subject := _component_subject(match.group(1))):
            return unresolved()
        return QuestionPlan(facets=(
            PlannedFacet("definition", subject, span_text=q),
            PlannedFacet("purpose", subject, relation="purpose", response_mode="purpose", span_text=q),
            PlannedFacet("relation", subject, relation="problem_solved", span_text=q),
        ), clauses=(q,), parse_trace=("component:product_overview",))
    match = re.fullmatch(r"component architecture and module boundaries for (.+)", cleaned, re.I)
    if match is not None:
        if not (subject := _component_subject(match.group(1))):
            return unresolved()
        return QuestionPlan(facets=(
            PlannedFacet("relation", subject, relation="architecture", span_text=q),
            PlannedFacet("relation", subject, relation="module_boundaries", span_text=q),
        ), clauses=(q,), parse_trace=("component:architecture_boundaries",))
    match = re.fullmatch(r"component operation flow (.+?) from (.+?) to (.+)", cleaned, re.I)
    if match is not None:
        operation, source, target = (_component_subject(match.group(i)) for i in range(1, 4))
        if operation and source and target:
            return QuestionPlan(facets=(PlannedFacet(
                "workflow", operation, relation="sequence", target=target,
                context=f"from {source} to {target}", response_mode="workflow", span_text=q,
            ),), clauses=(q,), parse_trace=("component:operation_flow",))
        return unresolved()
    match = re.fullmatch(r"component public tool inventory for (.+)", cleaned, re.I)
    if match is not None:
        if _unsafe_free_text(match.group(1)) or not (subject := _component_subject(match.group(1))):
            return unresolved()
        # This open surface recognizes names, not an exhaustive per-member
        # answer contract. Visible inventory proof must not close that scope.
        return QuestionPlan(facets=(PlannedFacet(
            "inventory", subject, attribute="public_tools", item_kind="public_tool",
            value_kind="identifier_list", response_mode="names", span_text=q,
        ),), clauses=(q,), parse_trace=("component:public_tool_inventory",),
            component_scope_complete=False)
    match = re.fullmatch(r"component selection behavior for (.+?) selecting (.+)", cleaned, re.I)
    if match is not None:
        subject, target = (_component_subject(match.group(i)) for i in range(1, 3))
        if subject and target:
            return QuestionPlan(facets=(PlannedFacet(
                "behavior", subject, relation="selection_policy", target=target, span_text=q,
            ),), clauses=(q,), parse_trace=("component:selection_behavior",))
        return unresolved()
    match = re.fullmatch(
        r"component (install verify|read test|initialize ingest query|action consequences|configuration invalid behavior) for (.+)",
        cleaned, re.I,
    )
    if match is None:
        return None
    if not (subject := _component_subject(match.group(2))):
        return unresolved()
    specifications = {
        "install verify": (("installation", "workflow"), ("verification", "workflow")),
        "read test": (("reading", "workflow"), ("testing", "workflow")),
        "initialize ingest query": (("initialization", "workflow"), ("ingestion", "workflow"), ("query", "workflow")),
        "action consequences": (("procedure", "workflow"), ("consequences", "relation")),
        "configuration invalid behavior": (("configuration", "workflow"), ("invalid_behavior", "relation")),
    }
    family = match.group(1).casefold()
    return QuestionPlan(facets=tuple(
        PlannedFacet(kind, subject, relation=relation, response_mode="workflow" if kind == "workflow" else "value", span_text=q)
        for relation, kind in specifications[family]
    ), clauses=(q,), parse_trace=(f"component:{family.replace(' ', '_')}",))


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
    "semantic_components",
]
