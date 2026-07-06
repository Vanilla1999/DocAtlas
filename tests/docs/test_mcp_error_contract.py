from __future__ import annotations

from docmancer.docs.interfaces.mcp.error_contract import build_mcp_error_payload


def test_unknown_tool_error_contract_keeps_legacy_fields() -> None:
    payload = build_mcp_error_payload(
        reason_code="unknown_tool",
        message="unknown tool: missing",
        tool="missing",
        phase="validation",
    )

    assert payload["status"] == "failed"
    assert payload["reason_code"] == "unknown_tool"
    assert payload["message"] == "unknown tool: missing"
    assert payload["error"]["reason_code"] == "unknown_tool"
    assert payload["error"]["retryable"] is False
    assert payload["error"]["where"] == {"tool": "missing", "handler": None, "phase": "validation"}


def test_unhandled_exception_hides_traceback_without_debug() -> None:
    payload = build_mcp_error_payload(
        reason_code="unhandled_exception",
        message="boom",
        exception=RuntimeError("boom"),
        tool="get_project_context",
        handler="handle_project_tool",
        phase="execution",
        debug=False,
    )

    assert payload["error"]["exception_type"] == "RuntimeError"
    assert "traceback" not in payload["error"]


def test_unhandled_exception_includes_traceback_in_debug() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        payload = build_mcp_error_payload(
            reason_code="unhandled_exception",
            message="boom",
            exception=exc,
            tool="get_project_context",
            handler="handle_project_tool",
            phase="execution",
            debug=True,
        )

    assert payload["error"]["exception_type"] == "RuntimeError"
    assert "RuntimeError: boom" in payload["error"]["traceback"]


def test_bad_request_error_contract_has_fix_arguments_hint() -> None:
    payload = build_mcp_error_payload(
        reason_code="empty_question",
        message="question must not be empty",
        tool="get_project_context",
        phase="validation",
    )

    assert payload["reason_code"] == "empty_question"
    assert payload["message"] == "question must not be empty"
    assert payload["error"]["reason_code"] == "empty_question"
    assert payload["error"]["retryable"] is False
    assert "Fix the MCP tool arguments and retry." in payload["error"]["hints"]
