from __future__ import annotations

import os
import traceback
from typing import Any


MAX_ERROR_MESSAGE_CHARS = 1_000
MAX_ERROR_TRACEBACK_CHARS = 4_000
MAX_ERROR_HINTS = 5

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
    "handler_exception": False,
    "permission_denied": False,
}

_HINTS_BY_REASON: dict[str, list[str]] = {
    "bad_request": ["Fix the MCP tool arguments and retry."],
    "validation_error": ["Fix the MCP tool arguments and retry."],
    "empty_question": ["Provide a non-empty question, for example: 'Flutter Riverpod providers' or 'FastAPI dependency injection'."],
    "unknown_tool": ["Use list_tools to discover available MCP tools."],
    "config_shadowing": ["Start MCP from the repo config, set DOCMANCER_HOME, or use an explicit override if available."],
    "project_local_config_shadowed": ["Start MCP from the repo config, set DOCMANCER_HOME, or use an explicit override if available."],
    "network_required": ["Retry only after explicit user approval for network access."],
    "confirmation_required": ["Ask the user to approve the required lifecycle/network action, then retry."],
    "transport_size_limit": ["Retry with compact output, lower limit/tokens, or pagination."],
    "full_output_too_large": ["Retry with output_mode='compact', lower limit/tokens, page/page_size, or include_sections."],
    "unhandled_exception": ["Check diagnostics/logs; retry only after the underlying issue is fixed."],
    "handler_exception": ["Check diagnostics/logs; retry only after the underlying handler issue is fixed."],
    "permission_denied": ["Check filesystem permissions or run with access to the requested resource."],
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
    bounded_message = _bounded_text(message, MAX_ERROR_MESSAGE_CHARS)
    bounded_reason = _bounded_text(reason_code, 100)
    exception_type = _bounded_text(type(exception).__name__, 200) if exception is not None else None
    error: dict[str, Any] = {
        "reason_code": bounded_reason,
        "message": bounded_message,
        "exception_type": exception_type,
        "retryable": _retryable_for(reason_code) if retryable is None else retryable,
        "where": {
            "tool": _bounded_text(tool, 200) if tool is not None else None,
            "handler": _bounded_text(handler, 200) if handler is not None else None,
            "phase": _bounded_text(phase, 100),
        },
        "hints": [
            _bounded_text(item, 500)
            for item in _hints_for(reason_code, hints)[:MAX_ERROR_HINTS]
        ],
    }
    if debug and exception is not None:
        error["traceback"] = _bounded_text(
            "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)),
            MAX_ERROR_TRACEBACK_CHARS,
        )
    return {
        "status": "failed",
        "error": error,
        "reason_code": bounded_reason,
        "message": bounded_message,
        "warnings": [_bounded_warning(item) for item in list(warnings or [])[:MAX_ERROR_HINTS]],
    }


def _bounded_text(value: Any, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _bounded_warning(value: Any) -> Any:
    if isinstance(value, str):
        return _bounded_text(value, 500)
    if isinstance(value, dict):
        allowed = ("code", "message", "reason", "path")
        return {
            key: _bounded_text(value[key], 500)
            for key in allowed
            if value.get(key) not in (None, "")
        }
    return _bounded_text(value, 500)


def build_bad_request_payload(reason_code: str, message: str, *, tool: str | None = None) -> dict[str, Any]:
    return build_mcp_error_payload(reason_code=reason_code, message=message, tool=tool, phase="validation")
