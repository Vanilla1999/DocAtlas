"""Small serialization helpers for model-visible projections."""
from __future__ import annotations

import json
import math

from copy import deepcopy
from typing import Any


def bounded_action(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if value.get("type") == "ask_user_for_library_docs_source":
        return _source_choice_advisory(value)
    allowed = (
        "tool", "type", "action", "handled_by", "arguments_patch", "question",
        "requires_confirmation", "confirmation_reason", "reason", "observations",
        "security_scope", "decision_options", "agent_question", "query_terms",
        "suggested_doc_paths", "suggested_symbols", "suggested_layers",
        "repeat_docs_context",
    )
    result = {
        key: deepcopy(value[key])
        for key in allowed
        if value.get(key) not in (None, {}, [])
    }
    result["auto_execute"] = False
    return result


def source_choice_action(retrieval: dict[str, Any]) -> dict[str, Any] | None:
    """Retain only a producer-authored source question, never a tool grant."""
    if (
        retrieval.get("status") != "confirmation_required"
        or retrieval.get("requires_confirmation") is not True
        or retrieval.get("reason_code") != "library_docs_source_required"
        or retrieval.get("confirmation_reason") != "library_docs_source"
        or retrieval.get("hard_stop")
        or retrieval.get("unresolved_conflicts")
        or retrieval.get("recovery_origin") == "conflict"
        or retrieval.get("recovery_reason_code") == "authoritative_evidence_conflict"
    ):
        return None
    delivery = retrieval.get("delivery_decision")
    if delivery is not None:
        if not isinstance(delivery, dict):
            return None
        deliverable = delivery.get("deliverable")
        if deliverable is not None and deliverable is not True:
            return None
    selection = retrieval.get("selection_decision")
    selection = (
        selection.get("selection_decision", selection) if isinstance(selection, dict)
        else getattr(selection, "selection_decision", selection)
    )
    conflicts = (
        selection.get("unresolved_conflicts") if isinstance(selection, dict)
        else getattr(selection, "unresolved_conflicts", None)
    )
    if conflicts:
        return None
    support = retrieval.get("support_decision")
    support_reason = (
        support.get("reason_code") if isinstance(support, dict)
        else getattr(support, "reason_code", None)
    )
    if support_reason is not None and not isinstance(support_reason, str):
        return None
    if support_reason in {"authoritative_evidence_conflict", "conflicting_authoritative_evidence"}:
        return None
    return _source_choice_advisory(retrieval.get("next_action"))


def _source_choice_advisory(value: Any) -> dict[str, Any] | None:
    if (
        not isinstance(value, dict)
        or value.get("type") != "ask_user_for_library_docs_source"
        or value.get("tool") is not None
        or value.get("requires_confirmation") is not True
        or not isinstance(value.get("question"), str)
        or not value["question"].strip()
    ):
        return None
    result: dict[str, Any] = {
        "type": "ask_user_for_library_docs_source",
        "tool": None,
        "question": value["question"],
        "requires_confirmation": True,
        "auto_execute": False,
    }
    if "quality_warning" in value:
        if not isinstance(value["quality_warning"], str):
            return None
        result["quality_warning"] = value["quality_warning"]
    if "options" in value:
        if not isinstance(value["options"], list):
            return None
        options = [_source_choice_option(option) for option in value["options"]]
        if any(option is None for option in options):
            return None
        result["options"] = options
    return result


def _source_choice_option(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, Any] = {}
    for key in ("id", "label", "docs_url", "why"):
        if key not in value:
            continue
        item = value[key]
        if not isinstance(item, str) and not (key == "why" and item is None):
            return None
        result[key] = item
    if "confidence" in value:
        confidence = value["confidence"]
        if (isinstance(confidence, bool) or (
            confidence is not None and not isinstance(confidence, (str, int, float))
        )):
            return None
        if isinstance(confidence, float) and not math.isfinite(confidence):
            return None
        result["confidence"] = confidence
    for key in ("requires_confirmation", "quality_guarantee"):
        if key in value:
            if not isinstance(value[key], bool):
                return None
            if key == "requires_confirmation" and value[key] is not True:
                return None
            if key == "quality_guarantee" and value[key] is not False:
                return None
            result[key] = value[key]
    if "arguments_patch" in value:
        arguments = value["arguments_patch"]
        if not isinstance(arguments, dict):
            return None
        patch: dict[str, Any] = {}
        for key in ("library", "ecosystem", "version", "source_type", "docs_url"):
            if key in arguments:
                if arguments[key] is not None and not isinstance(arguments[key], str):
                    return None
                patch[key] = arguments[key]
        if "action" in arguments:
            if (not isinstance(arguments["action"], str)
                or arguments["action"] not in {"discover_library_docs", "prefetch_library_docs"}):
                return None
            patch["action"] = arguments["action"]
        result["arguments_patch"] = patch
    return result


def cited_patch_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    values: list[Any] = [
        payload.get("acceptance_conditions"),
        payload.get("invariants"),
        payload.get("forbidden_changes"),
        payload.get("implementation_guidance"),
        (payload.get("targets") or {}).get("likely_files"),
        (payload.get("targets") or {}).get("symbols"),
        *((payload.get("checks") or {}).values()),
    ]
    return [
        item
        for value in values
        if isinstance(value, list)
        for item in value
        if isinstance(item, dict) and item.get("provenance") != "user_request"
    ]


def sanitized_projection_manifest(
    snapshot: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return deterministic audit metadata without full source text."""

    allowed = (
        "evidence_id", "path_or_url", "path", "section", "symbol_or_section",
        "authority", "instruction_trust", "scope", "version_binding",
        "content_sha256",
    )
    return [
        {
            key: deepcopy(projected[key])
            for key in allowed
            if projected.get(key) not in (None, "")
        }
        for _, value in sorted(snapshot.items())
        for projected in [value.get("projected_source") or value]
    ]


__all__ = ["bounded_action", "source_choice_action", "cited_patch_items", "sanitized_projection_manifest"]


def canonical_projection_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def estimate_projection_tokens(value: Any) -> int:
    size = len(canonical_projection_bytes(value))
    return max(1, math.ceil(size / 4))


def docs_context_budget_tokens(value: Any) -> int:
    """Admit only DTOs fitting both the public estimate and pinned offline codec."""
    from .projection_tokenizer import projection_token_count

    return max(estimate_projection_tokens(value), projection_token_count(canonical_projection_bytes(value)))
