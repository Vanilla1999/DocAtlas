"""Local observer for reproducible project-context quality captures."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from docmancer.docs.interfaces.mcp import context_tools
from docmancer.mcp.docs_server import call_docs_tool_payload
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        rows = [_json_value(item) for item in value]
        return sorted(rows, key=lambda item: json.dumps(
            item, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ))
    raise TypeError(f"unsupported capture value: {type(value).__name__}")


def freeze_call(
    request: dict[str, Any], public_payload: dict[str, Any],
    projection_attempts: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Detach and explicitly normalize one capture for JSON persistence."""
    return _json_value(deepcopy({
        "request": request,
        "public_payload": public_payload,
        "projection_attempts": list(projection_attempts),
    }))


def build_run_manifest(
    *, code_sha: str, corpus_hash: str, lock_hash: str, root_question: str,
    strategy: str, subquestions: tuple[str, ...], request: dict[str, Any],
    elapsed_seconds: float, public_payload: dict[str, Any],
) -> dict[str, Any]:
    """Freeze reproducibility metadata without judging answer quality."""
    strategy_record = {
        "root_question": str(root_question),
        "strategy": str(strategy),
        "subquestions": [str(value) for value in subquestions],
    }
    encoded = json.dumps(
        strategy_record, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return deepcopy({
        "code_sha": str(code_sha),
        "corpus_hash": str(corpus_hash),
        "lock_hash": str(lock_hash),
        **strategy_record,
        "strategy_freeze_sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
        "request": request,
        "elapsed_seconds": float(elapsed_seconds),
        "admission_tokens": docs_context_budget_tokens(public_payload),
    })


def capture_public_call(service: Any, request: dict[str, Any]) -> dict[str, Any]:
    """Observe one real public call without replacing projection behavior."""
    real = context_tools.project_docs_context
    attempts: list[dict[str, Any]] = []

    def observe(*args: Any, **kwargs: Any):
        retrieval = kwargs.get("retrieval")
        before = deepcopy(retrieval)
        payload, snapshot = real(*args, **kwargs)
        attempts.append(deepcopy({
            "before_projection": before,
            "after_projection": retrieval,
            "projected_payload": payload,
            "snapshot": snapshot,
        }))
        return payload, snapshot

    with patch.object(context_tools, "project_docs_context", observe):
        public = call_docs_tool_payload("get_docs_context", deepcopy(request), service)
    return freeze_call(request, public, tuple(attempts))


__all__ = ["build_run_manifest", "capture_public_call", "freeze_call"]
