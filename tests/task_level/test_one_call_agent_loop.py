from __future__ import annotations

import json
from pathlib import Path

import pytest

from docmancer.docs.application.model_visible_projection import estimate_projection_tokens
from eval.task_level.one_call_agent_loop import (
    FakeLoopAdapter,
    HistoryBlock,
    LoopBudgetProfile,
    LoopCapabilities,
    OneCallAgentLoop,
    ToolExecution,
    ToolOutputLimitError,
    capture_tool_execution,
    compact_retained_history,
    estimated_loop_tokens,
    validate_docatlas_result,
)


PATCH_CONTEXT = {
    "status": "ok",
    "kind": "patch_context",
    "objective": "Implement the bounded change.",
    "sources": [{"evidence_id": "ev-1", "content_sha256": "0" * 64}],
    "targets": {"likely_files": [], "symbols": []},
    "invariants": [],
    "forbidden_changes": [],
    "implementation_guidance": [],
    "checks": {"compile": [], "tests": [], "semantic_checks": []},
    "uncertainties": [],
    "omitted_counts": {},
    "estimated_tokens": 0,
}
for _ in range(3):
    PATCH_CONTEXT["estimated_tokens"] = estimate_projection_tokens(PATCH_CONTEXT)













