"""Terminal bounded projection helpers for insufficient documentation evidence."""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Iterable

_SAFE_MISSING_ID_RE = re.compile(r"^[A-Za-z0-9_.:/=-]{1,180}$")
_RECOVERY_SUMMARY_KEYS = (
    "documentation_supported", "investigation_allowed", "hard_stop",
    "recovery_origin", "recovery_reason_code", "recovery_disposition",
    "edit_ready", "source_search_status", "requires_confirmation",
)


def bounded_missing_value(value: Any, *, default: str) -> str:
    if isinstance(value, list):
        for item in value:
            text = str(item or "").strip()
            if _SAFE_MISSING_ID_RE.fullmatch(text):
                return text
    return default



def compact_recovery_action_for_budget(
    payload: dict[str, Any],
    limit: int,
    *,
    estimate_tokens: Any,
    refresh_estimate: Any,
) -> tuple[bool, bool]:
    """Compact a recovery action without splitting confirmation semantics."""
    action = payload.get("recommended_next_action")
    if not isinstance(action, dict):
        return False, False
    protected = bool(
        action.get("requires_confirmation") and action.get("confirmation_reason")
    )
    removable = [
        "observations", "decision_options", "agent_question", "security_scope", "reason"
    ]
    if not protected:
        removable.append("confirmation_reason")
    for key in removable:
        action.pop(key, None)
        refresh_estimate(payload)
        if estimate_tokens(payload) <= limit:
            return True, protected
    return False, protected

def _minimal_recovery_action(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if value.get("requires_confirmation") and value.get("confirmation_reason"):
        tool = value.get("tool")
        arguments = value.get("arguments_patch") if isinstance(value.get("arguments_patch"), dict) else {}
        if tool in {"prepare_docs", "docs_status"} and arguments:
            return {
                "tool": tool,
                "type": value.get("type") or tool,
                "arguments_patch": deepcopy(arguments),
                "requires_confirmation": True,
                "confirmation_reason": str(value["confirmation_reason"]),
                "auto_execute": False,
            }
    if value.get("type") != "rephrase_question":
        return None
    arguments = value.get("arguments_patch") if isinstance(value.get("arguments_patch"), dict) else {}
    question = str(arguments.get("question") or "")[:320]
    if not question:
        return None
    return {
        "tool": "get_docs_context",
        "type": "rephrase_question",
        "arguments_patch": {"question": question},
        "auto_execute": False,
    }


def apply_terminal_insufficient_projection(
    payload: dict[str, Any],
    *,
    kind: Any,
    missing: str,
    original_action: Any,
    support_keys: Iterable[str],
) -> None:
    recovery_summary = {
        key: deepcopy(payload[key])
        for key in _RECOVERY_SUMMARY_KEYS
        if key in payload
    }
    support = {
        key: payload[key]
        for key in support_keys
        if key in payload and key != "reason_code"
    }
    payload.clear()
    payload.update({
        "status": "insufficient_evidence",
        "kind": "docs_answer" if kind == "docs_answer" else "patch_context",
        "missing": [missing],
        "answer_supported": False,
        "answer_available": False,
        "support_status": "insufficient_evidence",
        "estimated_tokens": 0,
        **support,
        **recovery_summary,
    })
    minimal_recovery = _minimal_recovery_action(original_action)
    if minimal_recovery is not None:
        payload["recommended_next_action"] = minimal_recovery


__all__ = ["apply_terminal_insufficient_projection", "bounded_missing_value"]
