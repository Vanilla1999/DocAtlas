from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

import docmancer.docs.domain.answer_completeness as completeness_module
from docmancer.docs.domain.answer_completeness import (
    derive_project_answer_completeness,
    evaluate_project_answer_completeness,
)
from docmancer.docs.domain.recovery_handoff import (
    has_safe_local_source_handoff,
    is_safe_local_source_handoff,
)
from docmancer.docs.interfaces.mcp.recovery_projection import (
    _annotate_recovery_handoff,
)


def _safe_action() -> dict[str, object]:
    return {
        "tool": "code_search",
        "type": "search_local_source",
        "handled_by": "coding_agent",
        "requires_confirmation": False,
        "repeat_docs_context": False,
        "auto_execute": False,
    }









