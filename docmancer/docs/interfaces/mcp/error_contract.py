from __future__ import annotations

import os
import traceback
from typing import Any

_RETRYABLE_BY_REASON: dict[str, bool | None] = {
    "bad_request": False,
    "validation_error": False,
    "unknown_tool": False,
    "config_shadowing": False,
    "project_local_config_shadowed": False,
    "network_required": True,
    "confirmation_required": True,
    "transport_size_limit": True,
    "full_output_too_large": True,
    "unhandled_exception": False,
}

_HINTS_BY_REASON: dict[str, list[str]] = {
    "bad_request": ["Fix the MCP tool arguments and retry."],
    "validation_error": ["Fix the MCP tool arguments and retry."],
    "unknown_tool": ["Use list_tools to discover available MCP tools."],
    "config_shadowing": ["Start MCP from the repo config, set DOCMANCER_HOME, or use an explicit override if available."],
    "project_local_config_shadowed": ["Start MCP from the repo config, set DOCMANCER_HOME, or use an explicit override if available."],
    "network_required": ["Retry only after explicit user approval for network access."],
    "confirmation_required": ["Ask the user to approve the required lifecycle/network action, then retry."],
    "transport_size_limit": ["Retry with compact output, lower limit/tokens, or pagination."],
    "full_output_too_large": ["Retry with output_mode='compact', lower limit/tokens, page/page_size, or include_sections."],
    "unhandled_exception": ["Check diagnostics/logs; retry only after the underlying issue is fixed."],
}

_VALIDATION_REASON_CODES = {
    "empty_library",
    "empty_question",
    "empty_project_path",
    "empty_canonical_id",
    "invalid_integer",
    "bad_request",
    "validation_error",
}


def _retryable_for(reason_code: str) -> bool | None:
    if reason_code in _RETRYABLE_BY_REASON:
        return _RETRYABLE_BY_REASON[reason_code]
    if reason_code in _VALIDATION_REASON_CODES:
        return False
    return False


def _hints_for(reason_code: str, hints: list[str] | None) -> list[str]:
    result = list(hints or [])
    if not result:
        result.extend(_HINTS_BY_REASON.get(reason_code, []))
    if not result and reason_code in _VALIDATION_REASON_CODES:
        result.append("Fix the MCP tool arguments and retry.")
    return result


def debug_errors_enabled(args: dict[str, Any] | None = None) -> bool:
    output_mode = str((args or {}).get("output_mode") or "").lower()
    return output_mode == "debug" or os.environ.get("DOCATLAS_MCP_DEBUG_ERRORS") == "1"


def build_mcp_error_payload(
    *,
    reason_code: str,
    message: str,
    exception: BaseException | None = None,
    tool: str | None = None,
    handler: str | None = None,
    phase: str = "unknown",
    retryable: bool | None = None,
    hints: list[str] | None = None,
    warnings: list[Any] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    exception_type = type(exception).__name__ if exception is not None else None
    error: dict[str, Any] = {
        "reason_code": reason_code,
        "message": message,
        "exception_type": exception_type,
        "retryable": _retryable_for(reason_code) if retryable is None else retryable,
        "where": {"tool": tool, "handler": handler, "phase": phase},
        "hints": _hints_for(reason_code, hints),
    }
    if debug and exception is not None:
        error["traceback"] = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    return {
        "status": "failed",
        "error": error,
        "reason_code": reason_code,
        "message": message,
        "warnings": list(warnings or []),
    }


def build_bad_request_payload(reason_code: str, message: str, *, tool: str | None = None) -> dict[str, Any]:
    return build_mcp_error_payload(reason_code=reason_code, message=message, tool=tool, phase="validation")
