"""Deprecated semantic command-rule adapters.

Keep parser helper signatures for callers, but never guess a product command,
expected API value or workflow from a natural-language request.
"""
from __future__ import annotations

from docmancer.docs.domain.question_plan_core import QuestionPlan


def _docs_mcp_server_command(q: str) -> QuestionPlan | None:
    return None


def _command_sync(q: str) -> QuestionPlan | None:
    return None


def _offline_suite_run(q: str) -> QuestionPlan | None:
    return None


def _two_cell_cardinality(q: str) -> QuestionPlan | None:
    return None


__all__ = [
    "_docs_mcp_server_command", "_command_sync", "_offline_suite_run",
    "_two_cell_cardinality",
]
