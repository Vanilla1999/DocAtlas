"""Bounded compositional parser for project-documentation questions.

This layer exists to keep natural-language parsing separate from proof
validation. It intentionally recognizes a small auditable grammar and marks
unresolved subjects/operations instead of inventing generic proof identities.
Rule precedence is explicit in ``_RULES``; adding a rule cannot silently change
another rule's order inside one long conditional chain.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Literal

from docmancer.docs.domain.technical_terms import TechnicalTermKind, coerce_technical_term

PlanKind = Literal[
    "definition", "purpose", "behavior", "usage", "workflow", "inventory",
    "command", "relation",
]


@dataclass(frozen=True, slots=True)
class PlannedFacet:
    kind: PlanKind
    subject: str
    relation: str | None = None
    attribute: str | None = None
    target: str | None = None
    value_kind: str = "text"
    expected_value: str | None = None
    item_kind: str | None = None
    response_mode: str = "value"
    context: str | None = None
    subject_kind: TechnicalTermKind | None = None
    subject_aliases: tuple[str, ...] = ()
    span_text: str | None = None


@dataclass(frozen=True, slots=True)
class QuestionPlan:
    facets: tuple[PlannedFacet, ...] = ()
    clauses: tuple[str, ...] = ()
    unresolved_parts: tuple[str, ...] = ()
    parse_trace: tuple[str, ...] = ()

    @property
    def handled(self) -> bool:
        return bool(self.facets or self.unresolved_parts)


Rule = Callable[[str], QuestionPlan | None]


def _clean(value: str) -> str:
    value = " ".join(str(value or "").strip(" ?!.,:").split())
    return re.sub(r"^(?:the|a|an)\s+", "", value, flags=re.I)[:160]


def _technical(
    value: str,
    kind: TechnicalTermKind | None = None,
) -> tuple[str, TechnicalTermKind | None, tuple[str, ...]]:
    value = _clean(value)
    if not value:
        return "", None, ()
    if kind is not None or re.search(r"[_-]|^[A-Z][A-Z0-9_]+$|\.yaml$", value):
        term = coerce_technical_term(value, kind, context=value)
        return term.raw, term.kind, term.aliases
    return value, None, ()


def _command_sync(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*(?:which|what)\s+command\s+"
        r"(?:does\s+[^?]+?\s+use\s+to\s+)?syncs?\s+project\s+docs?\b.*",
        q,
        re.I,
    )
    if match is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            kind="command",
            subject="sync_project_docs",
            relation="invocation",
            value_kind="call_expression",
            expected_value="sync_project_docs",
            response_mode="call",
            subject_kind="code_symbol",
            subject_aliases=("sync_project_docs", "sync-project-docs", "sync project docs"),
            span_text=match.group(0),
        ),),
        clauses=(q,),
        parse_trace=("command:sync_project_docs",),
    )


def _source_type_inventory(q: str) -> QuestionPlan | None:
    if re.match(r"^\s*what\s+source\s+types?\s+are\s+supported\s+for\s+indexing\b", q, re.I) is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            kind="inventory",
            subject="source types",
            attribute="source",
            item_kind="source",
            value_kind="identifier_list",
            response_mode="names",
            span_text="source types",
        ),),
        clauses=(q,),
        parse_trace=("inventory:source_types",),
    )


def _release_checklist_compound(q: str) -> QuestionPlan | None:
    match = re.match(r"^\s*what\s+is\s+(.+?)\s+and\s+what\s+(.+?)\?*$", q, re.I)
    if match is None:
        return None
    left, right = _clean(match.group(1)), _clean(match.group(2))
    if re.search(r"\bgates?\s+block\s+release\b", right, re.I) is None:
        return None
    return QuestionPlan(
        facets=(
            PlannedFacet("purpose", left, relation="purpose", response_mode="purpose", span_text=match.group(1)),
            PlannedFacet("relation", "release", relation="blocking_gates", span_text=match.group(2)),
        ),
        clauses=(left, right),
        parse_trace=("compound:purpose", "compound:blocking_gates"),
    )


def _token_bounding_compound(q: str) -> QuestionPlan | None:
    match = re.match(r"^\s*what\s+is\s+(.+?)\s+and\s+how\s+is\s+(.+?)\?*$", q, re.I)
    if match is None:
        return None
    left, right = _clean(match.group(1)), _clean(match.group(2))
    if re.search(r"token[- ]bounded", right, re.I) is None:
        return None
    return QuestionPlan(
        facets=(
            PlannedFacet("definition", left, span_text=match.group(1)),
            PlannedFacet("relation", left, relation="token_bounding", context=right, span_text=match.group(2)),
        ),
        clauses=(left, right),
        parse_trace=("compound:definition", "compound:token_bounding"),
    )


def _public_tools_with_usage(q: str) -> QuestionPlan | None:
    if re.match(
        r"^\s*what\s+are\s+the\s+three\s+public\s+docs\s+mcp\s+tools\s+"
        r"and\s+when\s+do\s+i\s+use\s+each\s+one",
        q,
        re.I,
    ) is None:
        return None
    return QuestionPlan(
        facets=(
            PlannedFacet(
                "inventory", "Docs MCP", attribute="public_tools", item_kind="public_tool",
                value_kind="identifier_list", response_mode="names",
                span_text="three public Docs MCP tools",
            ),
            PlannedFacet("relation", "Docs MCP", relation="per_tool_usage", span_text="when do I use each one"),
        ),
        clauses=(q,),
        parse_trace=("inventory:public_tools", "relation:per_tool_usage"),
    )


def _env_var_purpose_usage(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*what\s+is\s+(DOCMANCER_[A-Z0-9_]+)\s+and\s+when\s+should\s+it\s+be\s+used",
        q,
        re.I,
    )
    if match is None:
        return None
    subject, kind, aliases = _technical(match.group(1), "env_var")
    return QuestionPlan(
        facets=(
            PlannedFacet(
                "purpose", subject, relation="purpose", response_mode="purpose",
                subject_kind=kind, subject_aliases=aliases, span_text=match.group(1),
            ),
            PlannedFacet(
                "usage", subject, relation="usage", subject_kind=kind,
                subject_aliases=aliases, span_text="when should it be used",
            ),
        ),
        clauses=(q,),
        parse_trace=("env:purpose", "env:usage"),
    )


def _conditional_clear_index(q: str) -> QuestionPlan | None:
    match = re.match(r"^\s*what\s+does\s+(clear-index)\s+do\s+when\s+(.+?)\?*$", q, re.I)
    if match is None:
        return None
    subject, kind, aliases = _technical(match.group(1), "cli_command")
    return QuestionPlan(
        facets=(PlannedFacet(
            "relation", subject, relation="conditional_behavior", context=_clean(match.group(2)),
            subject_kind=kind, subject_aliases=aliases, span_text=match.group(0),
        ),),
        clauses=(q,),
        parse_trace=("relation:conditional_behavior",),
    )


def _configuration_workflow(q: str) -> QuestionPlan | None:
    match = re.match(r"^\s*how\s+do\s+i\s+configure\s+(?:a\s+)?project\s+in\s+([^?]+?)\?*$", q, re.I)
    if match is None:
        return None
    raw = _clean(match.group(1))
    preferred: TechnicalTermKind | None = "config_key" if "." in match.group(1) and not match.group(1).endswith(".yaml") else None
    subject, kind, aliases = _technical(raw, preferred)
    return QuestionPlan(
        facets=(PlannedFacet(
            "workflow", subject, relation="configuration", context="project configuration",
            response_mode="workflow", subject_kind=kind, subject_aliases=aliases,
            span_text=match.group(1),
        ),),
        clauses=(q,),
        parse_trace=("workflow:configuration",),
    )


def _contamination_definition(q: str) -> QuestionPlan | None:
    if re.match(r"^\s*what\s+is\s+contamination\s+protection\s+in\s+(?:the\s+)?eval\s+protocols", q, re.I) is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "definition", "contamination protection", context="eval protocols",
            span_text="contamination protection",
        ),),
        clauses=(q,),
        parse_trace=("definition:contamination_protection",),
    )


def _named_run_or_verify(q: str) -> QuestionPlan | None:
    match = re.match(r"^\s*how\s+do\s+i\s+(run|verify)\s+(.+?)\?*$", q, re.I)
    if match is None:
        return None
    action, subject = match.group(1).casefold(), _clean(match.group(2))
    if subject.casefold() == "project answer quality protocols":
        subject = "project answer quality protocol"
    context = None
    if " from " in subject:
        subject, context = subject.split(" from ", 1)
    return QuestionPlan(
        facets=(PlannedFacet(
            "workflow" if action == "run" else "relation",
            subject,
            relation="procedure" if action == "run" else "verification",
            context=context,
            response_mode="workflow" if action == "run" else "value",
            span_text=match.group(2),
        ),),
        clauses=(q,),
        parse_trace=(f"{action}:{subject}",),
    )


def _named_behavior(q: str) -> QuestionPlan | None:
    match = re.match(r"^\s*how\s+does\s+(.+?)\s+(work|choose|split)\b.*", q, re.I)
    if match is None:
        return None
    subject = _clean(match.group(1))
    action = match.group(2).casefold()
    if subject.casefold() == "prepare_docs sync_project_docs":
        return None
    if not subject or subject.casefold() in {"the project", "project"}:
        return None
    relation = "behavior"
    if subject.casefold() == "indexing" and action == "split":
        relation = "chunking"
    elif action == "choose":
        relation = "selection_policy"
    return QuestionPlan(
        facets=(PlannedFacet("behavior", subject, relation=relation, span_text=match.group(1)),),
        clauses=(q,),
        parse_trace=(f"behavior:{relation}:{subject}",),
    )


def _two_cell_smoke(q: str) -> QuestionPlan | None:
    match = re.match(r"^\s*what\s+is\s+the\s+(.+?smoke\s+procedure)\s+for\s+(.+?)\?*$", q, re.I)
    if match is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "workflow", _clean(match.group(1)), relation="procedure",
            context=_clean(match.group(2)), response_mode="workflow", span_text=match.group(1),
        ),),
        clauses=(q,),
        parse_trace=("workflow:smoke_procedure",),
    )


def _test_markers_and_offline_suite(q: str) -> QuestionPlan | None:
    if re.match(
        r"^\s*what\s+test\s+markers\s+are\s+available\s+and\s+how\s+do\s+i\s+run\s+the\s+offline\s+suite",
        q,
        re.I,
    ) is None:
        return None
    return QuestionPlan(
        facets=(
            PlannedFacet(
                "inventory", "test suite", attribute="marker", item_kind="marker",
                value_kind="identifier_list", response_mode="names", span_text="test markers",
            ),
            PlannedFacet(
                "workflow", "offline suite", relation="procedure",
                response_mode="workflow", span_text="run the offline suite",
            ),
        ),
        clauses=(q,),
        parse_trace=("inventory:test_marker", "workflow:offline_suite"),
    )


_RULES: tuple[Rule, ...] = (
    _command_sync,
    _source_type_inventory,
    _release_checklist_compound,
    _token_bounding_compound,
    _public_tools_with_usage,
    _env_var_purpose_usage,
    _conditional_clear_index,
    _configuration_workflow,
    _contamination_definition,
    _named_run_or_verify,
    _named_behavior,
    _two_cell_smoke,
    _test_markers_and_offline_suite,
)


def compile_question_plan(question: str) -> QuestionPlan:
    q = " ".join(str(question or "").split())[:4000]
    for rule in _RULES:
        plan = rule(q)
        if plan is not None and plan.handled:
            return plan
    return QuestionPlan()


__all__ = ["PlannedFacet", "QuestionPlan", "compile_question_plan"]
