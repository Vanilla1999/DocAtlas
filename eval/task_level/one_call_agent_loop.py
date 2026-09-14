"""Provider-neutral one-call agent loop with the current DocAtlas result contract."""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from . import _one_call_agent_loop_core as _core
from ._one_call_agent_loop_core import *  # noqa: F401,F403

_BASE_VALIDATE_DOCATLAS_RESULT = _core.validate_docatlas_result
_QUALITY_STATUSES = {"checked", "partial", "unverified", "unavailable"}
_QUALITY_REASONS = {
    "coverage_unverified", "requested_part_missing", "budget_limited",
    "source_unavailable", "source_changed", "structure_unverified",
}
_RANGE_KEYS = {
    "source_uri", "path", "project_identity", "snapshot_sha256",
    "line_start", "line_end", "reason",
}


def _validate_context_extensions(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    quality = payload.get("context_quality")
    if quality is not None:
        if not isinstance(quality, dict) or set(quality) != {"status", "reasons"}:
            errors.append("docs_context context_quality has an invalid shape")
        else:
            reasons = quality.get("reasons")
            if quality.get("status") not in _QUALITY_STATUSES:
                errors.append("docs_context context_quality has an invalid status")
            if (
                not isinstance(reasons, list)
                or len(reasons) > 2
                or len(set(reasons)) != len(reasons)
                or any(reason not in _QUALITY_REASONS for reason in reasons)
            ):
                errors.append("docs_context context_quality has invalid reasons")

    read_next = payload.get("read_next")
    if read_next is not None:
        if not isinstance(read_next, list) or len(read_next) > 1:
            errors.append("docs_context read_next must contain at most one target")
        else:
            for target in read_next:
                if (
                    not isinstance(target, dict)
                    or set(target) != _RANGE_KEYS
                    or not isinstance(target.get("source_uri"), str)
                    or not re.fullmatch(r"docatlas://source/[0-9a-f]{24}", target["source_uri"])
                    or not isinstance(target.get("path"), str) or not target["path"]
                    or not isinstance(target.get("project_identity"), str) or not target["project_identity"]
                    or not isinstance(target.get("snapshot_sha256"), str)
                    or not re.fullmatch(r"sha256:[0-9a-f]{64}", target["snapshot_sha256"])
                    or type(target.get("line_start")) is not int
                    or type(target.get("line_end")) is not int
                    or not 0 < target["line_start"] <= target["line_end"]
                    or not isinstance(target.get("reason"), str)
                    or not re.fullmatch(r"[a-z0-9_]{1,64}", target["reason"])
                ):
                    errors.append("docs_context read_next has an invalid registered range")
    return errors


def validate_docatlas_result(payload: dict[str, Any]) -> list[str]:
    """Validate legacy fields plus bounded quality/recovery extensions."""
    if not isinstance(payload, dict) or payload.get("kind") != "docs_context":
        return _BASE_VALIDATE_DOCATLAS_RESULT(payload)

    legacy_payload = deepcopy(payload)
    legacy_payload.pop("context_quality", None)
    legacy_payload.pop("read_next", None)
    try:
        for _ in range(3):
            legacy_payload["estimated_tokens"] = _core.estimate_projection_tokens(legacy_payload)
    except (TypeError, ValueError):
        pass
    errors = list(_BASE_VALIDATE_DOCATLAS_RESULT(legacy_payload))
    errors.extend(_validate_context_extensions(payload))

    try:
        actual_tokens = _core.estimate_projection_tokens(payload)
    except (TypeError, ValueError):
        actual_tokens = -1
        errors.append("DocAtlas result must be JSON serializable")
    declared_tokens = payload.get("estimated_tokens")
    if (
        not isinstance(declared_tokens, int)
        or isinstance(declared_tokens, bool)
        or declared_tokens != actual_tokens
    ):
        errors.append("DocAtlas estimated_tokens does not match the canonical payload")
    try:
        if _core.docs_context_budget_tokens(payload) > 800:
            errors.append("docs_context exceeds whole-payload admission budget")
    except (TypeError, ValueError):
        errors.append("DocAtlas result must be JSON serializable")
    return list(dict.fromkeys(errors))


# OneCallAgentLoop is defined in the core module, so its global lookup must use
# the extended validator too. This keeps one authoritative implementation of
# the loop while the public facade owns the evolving wire contract.
_core.validate_docatlas_result = validate_docatlas_result
