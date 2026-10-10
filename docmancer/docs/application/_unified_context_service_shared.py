from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass, replace
from typing import Any

from docmancer.docs.application.evidence_selection import SelectionDecision, aggregate_mixed_selection
from docmancer.docs.application.project_context_service import context_pack_snippet
from docmancer.docs.domain.content_trust import annotate_context_pack
from docmancer.docs.domain.library_source_options import library_docs_source_options, source_required_diagnostics
from docmancer.docs.domain.mutation_intent import MutationIntentContract, build_mutation_intent
from docmancer.docs.domain.snippets import build_snippet_presentation, validate_response_style
from docmancer.docs.exact_version import resolve_python_versioned_docs
from docmancer.docs.models import DeliveryDecision, DocsResult, ProjectContextResult, UnifiedDocsContextResult
from docmancer.docs.resolver import docs_snapshot_is_exact

_LATEST_ALIASES = {"latest", "stable", "main", "*"}


def _looks_like_imperative_patch_task(tokens: list[str]) -> bool:
    """Legacy hook: prose cannot select a mutation contract."""
    return False


def _snippet_first_fallback_question(question: str, library: str) -> str:
    # Keep existing callers compatible without adding presentation keywords to
    # the user's request. Library identity is scope, not replacement query text.
    return question


def _without_snippet_not_available(warnings: list[Any]) -> list[Any]:
    return [warning for warning in warnings if warning != "snippet_not_available"
        and not (isinstance(warning, dict) and warning.get("code") == "snippet_not_available")]


def _exact_version_match(result: DocsResult) -> bool | None:
    if not result.requested_version:
        return None
    url = result.identity.get("docs_url_resolved") or result.identity.get("docs_url") if isinstance(result.identity, dict) else None
    return docs_snapshot_is_exact(result.requested_version, url) and (result.resolved_version or result.version) == result.requested_version


__all__ = [name for name in globals() if not name.startswith('__')]
