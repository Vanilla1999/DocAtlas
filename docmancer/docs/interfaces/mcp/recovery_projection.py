"""MCP projection helpers for bounded documentation-failure recovery.

This module only explains failed canonical support. It never grants support and
never replaces a concrete lifecycle/status/user-confirmation recovery with a
semantic rephrase.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from docmancer.docs.application.model_visible_projection import estimate_projection_tokens
from docmancer.docs.application.recovery import build_recovery_diagnosis, recovery_action

_RECOVERY_SUMMARY_KEYS = (
    "documentation_supported", "investigation_allowed", "hard_stop",
    "recovery_origin", "recovery_reason_code", "recovery_disposition",
)


def is_operational_recovery_action(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return bool(
        value.get("tool") in {"prepare_docs", "docs_status"}
        or value.get("type") == "ask_user_for_library_docs_source"
        or value.get("requires_confirmation")
    )


def _first_operational_action(payload: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [payload.get("next_action"), *(payload.get("next_actions") or [])]
    return next(
        (item for item in candidates if is_operational_recovery_action(item)),
        None,
    )


def _clean_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _refresh_estimate(payload: dict[str, Any]) -> None:
    payload["estimated_tokens"] = 0
    for _ in range(3):
        actual = estimate_projection_tokens(payload)
        if payload["estimated_tokens"] == actual:
            break
        payload["estimated_tokens"] = actual


def _attach_recovery_diagnosis(
    payload: dict[str, Any],
    *,
    question: str,
    request: dict[str, Any],
    canonical_selection: Any,
    operational_reason_code: Any = None,
) -> dict[str, Any]:
    if canonical_selection is None:
        return payload
    support = getattr(canonical_selection, "support_decision", None)
    if support is not None and bool(getattr(support, "answer_supported", False)):
        return payload
    diagnosis = build_recovery_diagnosis(
        question,
        canonical_selection,
        operational_reason_code=(
            payload.get("operational_reason_code")
            or operational_reason_code
            or payload.get("reason_code")
        ),
    )
    if not diagnosis:
        return payload

    updated = dict(payload)
    updated.update({
        "documentation_supported": bool(diagnosis.get("documentation_supported")),
        "investigation_allowed": bool(diagnosis.get("investigation_allowed", True)),
        "hard_stop": bool(diagnosis.get("hard_stop")),
        "recovery_origin": str(diagnosis.get("origin") or "selection"),
        "recovery_reason_code": str(
            diagnosis.get("reason_code") or "support_not_provable"
        ),
        "recovery_disposition": str(
            diagnosis.get("disposition") or "search_local_source"
        ),
    })

    # A concrete lifecycle/status/user-confirmation action describes a known
    # operational state and is more precise than changing the wording. Preserve
    # it unless canonical evidence reports an authoritative hard stop.
    operational = _first_operational_action(updated)
    if operational is not None and not bool(diagnosis.get("hard_stop")):
        updated.update({
            "recovery_origin": "operational",
            "recovery_reason_code": str(
                updated.get("operational_reason_code")
                or "operational_recovery_precedence"
            ),
            "recovery_disposition": "use_operational_recovery",
        })
        return updated

    action = recovery_action(
        diagnosis,
        project_path=_clean_string(request.get("project_path")),
        scope=_clean_string(request.get("scope")),
        mode=_clean_string(request.get("mode")),
    )
    if action:
        existing = [
            item
            for item in updated.get("next_actions") or []
            if isinstance(item, dict) and item != action
        ]
        updated["next_action"] = action
        updated["next_actions"] = [action, *existing]
    return updated


def _recovery_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(payload[key])
        for key in _RECOVERY_SUMMARY_KEYS
        if key in payload
    }


def _annotate_recovery_handoff(
    projection: dict[str, Any], recovery: dict[str, Any] | None
) -> None:
    if bool(projection.get("hard_stop")):
        projection.update({
            "disposition": "resolve_authoritative_conflict",
            "edit_ready": False,
            "source_search_status": "blocked",
        })
        _refresh_estimate(projection)
        return
    if not isinstance(recovery, dict):
        return
    if recovery.get("type") == "rephrase_question":
        projection.update({
            "disposition": "rephrase_question",
            "edit_ready": False,
            "source_search_status": "not_required",
            "requires_confirmation": False,
        })
    elif recovery.get("tool") == "code_search":
        projection.update({
            "disposition": "search_local_source",
            "edit_ready": False,
            "source_search_status": "required",
            "requires_confirmation": False,
        })
    _refresh_estimate(projection)


__all__ = [
    "_annotate_recovery_handoff",
    "_attach_recovery_diagnosis",
    "_recovery_summary",
    "is_operational_recovery_action",
]
