from __future__ import annotations

from typing import Any


def library_docs_source_options(
    library: str,
    ecosystem: str | None,
    version: str | None,
    source_type: str | None,
    candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return explicit choices for resolving a missing library docs source."""
    options: list[dict[str, Any]] = [
        {
            "id": "manual_docs_url",
            "label": "Provide documentation URL",
            "requires_confirmation": True,
            "arguments_patch": {
                "library": library,
                "ecosystem": ecosystem,
                "version": version,
                "source_type": source_type,
                "docs_url": "<docs_url>",
            },
        }
    ]

    for index, candidate in enumerate(candidates or [], start=1):
        arguments_patch = _candidate_arguments_patch(candidate)
        options.append(
            {
                "id": f"discovered_candidate_{index}",
                "label": candidate.get("name") or candidate.get("docs_url") or f"Discovered candidate {index}",
                "requires_confirmation": True,
                "quality_guarantee": False,
                "confidence": candidate.get("confidence"),
                "why": candidate.get("why"),
                "arguments_patch": arguments_patch,
            }
        )

    options.append(
        {
            "id": "best_effort_web_discovery",
            "label": "Use best-effort web discovery",
            "requires_confirmation": True,
            "quality_guarantee": False,
            "arguments_patch": {
                "library": library,
                "ecosystem": ecosystem,
                "version": version,
                "source_type": source_type,
                "allow_network": True,
            },
        }
    )
    return options


def library_docs_source_next_actions(
    library: str,
    ecosystem: str | None,
    version: str | None,
    source_type: str | None,
    candidates: list[dict[str, Any]] | None,
    source_options: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = [
        {
            "type": "ask_user_for_library_docs_source",
            "tool": None,
            "requires_confirmation": True,
            "question": f"Which documentation source should be used for {library}?",
            "options": source_options,
            "quality_warning": "If the user does not know, best-effort web discovery can be used, but quality is not guaranteed.",
        }
    ]

    candidate_list = list(candidates or [])
    if candidate_list:
        actions.append(
            {
                "type": "get_library_docs",
                "tool": "get_library_docs",
                "requires_confirmation": True,
                "reason": "Use the first discovered candidate only after user confirmation.",
                "arguments_patch": _candidate_arguments_patch(candidate_list[0]),
            }
        )

    actions.append(
        {
            "type": "best_effort_web_discovery",
            "tool": "get_library_docs",
            "requires_confirmation": True,
            "reason": "Use only if the user cannot provide an authoritative docs_url.",
            "arguments_patch": {
                "library": library,
                "ecosystem": ecosystem,
                "version": version,
                "source_type": source_type,
                "allow_network": True,
            },
        }
    )
    return actions


def source_required_diagnostics(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "reason_code": "library_docs_source_required",
        "legacy_reason_code": "needs_docs_url",
        "reason_aliases": ["library_docs_source_required", "needs_docs_url"],
        "requires_confirmation": True,
    }
    diagnostics.update(extra or {})
    return diagnostics


def _candidate_arguments_patch(candidate: dict[str, Any]) -> dict[str, Any]:
    if candidate.get("arguments_patch"):
        return dict(candidate["arguments_patch"])

    arguments_patch: dict[str, Any] = {}
    for key in ("docs_url", "ecosystem", "version", "source_type"):
        value = candidate.get(key)
        if value is not None:
            arguments_patch[key] = value
    return arguments_patch
