"""Compatibility DTOs without natural-language topic routing."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ProjectQueryIntent:
    name: str
    broad: bool = False
    wants_release_history: bool = False
    wants_docs_mcp: bool = False
    wants_packs_mcp: bool = False
    wants_architecture: bool = False
    wants_how_to: bool = False
    wants_troubleshooting: bool = False
    wants_code_symbols: bool = False


PUBLIC_DOCS_MCP_TOOL_NAMES = ("get_docs_context", "prepare_docs", "docs_status")
# Import compatibility only; no topic phrase registry remains.
PACKS_MCP_PHRASES: tuple[str, ...] = ()


def is_product_purpose_question(question: str) -> bool:
    return False


def mentions_docs_mcp_surface(question: str) -> bool:
    """Recognize only literal public protocol identifiers, never paraphrases."""
    return any(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", question)
        for name in PUBLIC_DOCS_MCP_TOOL_NAMES)


def is_concept_definition_or_contrast(question: str) -> bool:
    return False


def classify_project_query_intent(question: str) -> ProjectQueryIntent:
    return ProjectQueryIntent(name="general")
