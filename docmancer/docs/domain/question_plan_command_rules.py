"""Bounded command and workflow rules extracted from question_plan."""
from __future__ import annotations

import re

from docmancer.docs.domain.question_plan_core import (
    PlannedFacet,
    QuestionPlan,
    _clean,
    _technical,
    _unsafe_free_text,
)

def _docs_mcp_server_command(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*(?:which|what)\s+command\s+(?:starts?|runs?|launches?|serves?)\s+"
        r"(?:the\s+)?docs\s+mcp\s+server\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if match is None:
        return None
    subject, kind, aliases = _technical("docs-serve", "cli_command")
    return QuestionPlan(
        facets=(PlannedFacet(
            kind="command",
            subject=subject,
            relation="invocation",
            value_kind="call_expression",
            expected_value="docs-serve",
            response_mode="call",
            context="Docs MCP server",
            subject_kind=kind,
            subject_aliases=aliases,
            span_text=match.group(0),
        ),),
        clauses=(q,),
        parse_trace=("command:docs_mcp_server",),
    )


def _command_sync(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*(?:which|what)\s+command\s+"
        r"(?:does\s+[^?]+?\s+use\s+to\s+)?syncs?\s+project\s+docs?"
        r"(?:\s+after\s+(?:file\s+changes|(?:changing|editing|updating|modifying)\s+(?:a\s+|the\s+)?file))?"
        r"\s*[?!.]*\s*$",
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


_OFFLINE_SUITE_CONTEXT_RE = re.compile(
    r"(?:DocAtlas|[A-Za-z][A-Za-z0-9_.-]{1,80})",
    re.I,
)


def _offline_suite_run(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*how\s+do\s+i\s+run\s+the\s+offline(?:\s+test)?\s+suite"
        r"(?:\s+for\s+(.+?))?\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if match is None:
        return None
    context = _clean(match.group(1) or "DocAtlas")
    if (
        _unsafe_free_text(context)
        or _OFFLINE_SUITE_CONTEXT_RE.fullmatch(context) is None
    ):
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "workflow",
            "offline suite",
            relation="procedure",
            context=context,
            response_mode="workflow",
            span_text=match.group(0),
        ),),
        clauses=(q,),
        parse_trace=("workflow:offline_suite",),
    )

def _two_cell_cardinality(q: str) -> QuestionPlan | None:
    match = re.match(
        r"^\s*how\s+does\s+(?:the\s+)?(two[- ]cell\s+smoke\s+procedure)\s+"
        r"(?:verify|audit|check)\s+(provider[- ]call\s+cardinality)\s*[?!.]*\s*$",
        q,
        re.I,
    )
    if match is None:
        return None
    return QuestionPlan(
        facets=(PlannedFacet(
            "relation",
            _clean(match.group(1)),
            relation="verification",
            context=_clean(match.group(2)),
            span_text=match.group(0),
        ),),
        clauses=(q,),
        parse_trace=("verification:two_cell_provider_cardinality",),
    )

__all__ = [
    "_docs_mcp_server_command", "_command_sync", "_offline_suite_run",
    "_two_cell_cardinality",
]
