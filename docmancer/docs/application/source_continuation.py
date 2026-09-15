"""Bounded source capabilities plus one budgeted docs-context recovery target."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from . import _source_continuation_core as _core
from .model_visible_projection_helpers import docs_context_budget_tokens

SourceReference = _core.SourceReference
SourceReadGateway = _core.SourceReadGateway
SourceContinuationReader = _core.SourceContinuationReader
source_continuation_uri = _core.source_continuation_uri
attach_source_continuation_locators = _core.attach_source_continuation_locators


def source_range_uri(
    project_root: str, source: dict[str, Any], *, line_start: int, line_end: int,
) -> str | None:
    """Build an opaque identity for one server-registered bounded range."""
    digest = source.get("_source_snapshot_sha256")
    catalog = source.get("_source_catalog_hash")
    path = source.get("path") or source.get("path_or_url")
    if (
        not project_root or not digest or not catalog or not source.get("project_identity") or not path
        or type(line_start) is not int or type(line_end) is not int
        or line_start < 1 or line_end < line_start
    ):
        return None
    material = [
        "range", project_root, source.get("project_identity"), path, digest, catalog,
        source.get("doc_scope") or source.get("scope"), source.get("module_path"),
        line_start, line_end,
    ]
    identity = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:24]
    return SourceContinuationReader.uri_prefix + identity


def _candidate_identity(source: dict[str, Any]) -> str:
    return str(
        source.get("stable_id") or source.get("stable_chunk_id")
        or source.get("evidence_id") or source.get("source") or source.get("path") or ""
    )[:300]


def _read_next_row(
    root: str, source: dict[str, Any], *, line_start: int, line_end: int, reason: str,
) -> dict[str, Any] | None:
    uri = source_range_uri(root, source, line_start=line_start, line_end=line_end)
    path = source.get("path") or source.get("path_or_url")
    digest = source.get("_source_snapshot_sha256")
    identity = source.get("project_identity")
    if not uri or not path or not digest or not identity:
        return None
    return {
        "source_uri": uri,
        "path": str(path),
        "project_identity": str(identity),
        "snapshot_sha256": str(digest),
        "line_start": line_start,
        "line_end": line_end,
        "reason": reason,
    }


def prepare_docs_context_read_next(
    projection: dict[str, Any], snapshot: dict[str, Any], retrieval: dict[str, Any], *, root: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Choose one bounded recovery capability without reading source text."""
    if not root or str((projection.get("context_quality") or {}).get("status") or "") == "checked":
        return None, None

    plan = retrieval.get("documentation_query_plan")
    coverage = plan.get("_component_coverage") if isinstance(plan, dict) else None
    missing = {str(value) for value in (coverage or {}).get("missing_component_ids") or () if value}
    diagnostics = ((retrieval.get("retrieval_diagnostics") or {}).get("docs_context_projection") or {})
    rejections = diagnostics.get("projection_rejections") or ()
    candidates = tuple(
        item for item in retrieval.get("context_pack") or ()
        if isinstance(item, dict) and str(item.get("source_class") or "") == "project_doc"
    )

    for rejection in rejections:
        if not isinstance(rejection, dict) or rejection.get("reason") != "token_budget":
            continue
        component_ids = {str(value) for value in rejection.get("component_ids") or () if value}
        if missing and not (component_ids & missing):
            continue
        candidate_id = str(rejection.get("candidate_id") or "")
        source = next((item for item in candidates if _candidate_identity(item) == candidate_id), None)
        if source is None:
            continue
        start, end = source.get("line_start"), source.get("line_end")
        if type(start) is not int or type(end) is not int or not (0 < start <= end):
            continue
        end = min(end, start + SourceContinuationReader.max_lines - 1)
        reason = "requested_part_missing" if component_ids & missing else "inspect_source_context"
        target = _read_next_row(root, source, line_start=start, line_end=end, reason=reason)
        if target is not None:
            return target, source

    for projected in projection.get("sources") or ():
        if not isinstance(projected, dict) or not projected.get("evidence_id"):
            continue
        bound = snapshot.get(projected["evidence_id"])
        original = bound.get("source") if isinstance(bound, dict) else None
        if not isinstance(original, dict):
            continue
        raw_start, raw_end = original.get("line_start"), original.get("line_end")
        quote_start, quote_end = projected.get("line_start"), projected.get("line_end")
        if any(type(value) is not int for value in (raw_start, raw_end, quote_start, quote_end)):
            continue
        if not (0 < raw_start <= quote_start <= quote_end <= raw_end):
            continue
        start = max(raw_start, quote_start - 20)
        end = min(raw_end, start + SourceContinuationReader.max_lines - 1)
        if start >= quote_start and end <= quote_end:
            continue
        target = _read_next_row(
            root, original, line_start=start, line_end=end, reason="inspect_source_context",
        )
        if target is not None:
            return target, original
    return None, None


def docs_context_read_next_cost(payload: dict[str, Any], target: dict[str, Any]) -> int:
    """Measure the target's incremental cost in the actual serialized packet."""
    from .model_visible_projection import _refresh_estimate
    base = deepcopy(payload)
    base["read_next"] = []
    _refresh_estimate(base)
    trial = deepcopy(base)
    trial["read_next"] = [deepcopy(target)]
    _refresh_estimate(trial)
    return max(0, docs_context_budget_tokens(trial) - docs_context_budget_tokens(base))


def attach_docs_context_read_next(
    payload: dict[str, Any], target: dict[str, Any] | None, *, max_tokens: int,
) -> bool:
    """Attach one target only when the complete packet still fits."""
    from .model_visible_projection import _refresh_estimate
    payload["read_next"] = [deepcopy(target)] if isinstance(target, dict) else []
    _refresh_estimate(payload)
    if target is not None and docs_context_budget_tokens(payload) > max_tokens:
        payload["read_next"] = []
        _refresh_estimate(payload)
        return False
    return target is not None


def _reference_for_source(project_root: str, source: dict[str, Any]) -> SourceReference | None:
    path = source.get("path") or source.get("path_or_url")
    digest = source.get("_source_snapshot_sha256")
    catalog = source.get("_source_catalog_hash")
    identity = source.get("project_identity")
    line_end = source.get("line_end")
    if not path or not digest or not catalog or not identity or type(line_end) is not int or line_end < 1:
        return None
    return SourceReference(
        project_root, str(identity), str(path), str(digest), str(catalog),
        str(source.get("authority") or "supporting"),
        str(source.get("doc_scope") or source.get("scope") or "project"),
        source.get("module_path"), line_end,
    )


def _target_source(target: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any] | None:
    for bound in snapshot.values():
        source = bound.get("source") if isinstance(bound, dict) else None
        if not isinstance(source, dict):
            continue
        path = source.get("path") or source.get("path_or_url")
        start, end = source.get("line_start"), source.get("line_end")
        if (
            path == target.get("path")
            and source.get("project_identity") == target.get("project_identity")
            and source.get("_source_snapshot_sha256") == target.get("snapshot_sha256")
            and type(start) is int and type(end) is int
            and start <= target.get("line_start", 0) <= target.get("line_end", -1) <= end
        ):
            return source
    return None


def _mark_target_binding_failure(projection: dict[str, Any]) -> None:
    projection["recovery_reason_code"] = "source_unavailable"
    quality = projection.get("context_quality")
    if not isinstance(quality, dict) or quality.get("status") == "checked":
        return
    reasons = [str(value) for value in quality.get("reasons") or () if value]
    if "source_unavailable" not in reasons:
        if len(reasons) < 2:
            reasons.append("source_unavailable")
        elif quality.get("status") == "unverified":
            reasons[-1] = "source_unavailable"
    quality["reasons"] = list(dict.fromkeys(reasons))[:2]


def bind_project_source_continuations(
    reader: Any, project_root: str, projection: dict[str, Any], snapshot: dict[str, Any],
) -> None:
    """Register legacy continuations and the one emitted bounded range."""
    from .model_visible_projection import _refresh_estimate
    _core.bind_project_source_continuations(reader, project_root, projection, snapshot)
    targets = projection.get("read_next") or ()
    target = targets[0] if len(targets) == 1 and isinstance(targets[0], dict) else None
    if target is None:
        return
    source = _target_source(target, snapshot)
    reference = _reference_for_source(project_root, source) if source is not None else None
    if (
        reference is None
        or reader.issue_range(
            reference,
            line_start=target["line_start"], line_end=target["line_end"],
            uri=target["source_uri"],
        ) is None
    ):
        projection["read_next"] = []
        _mark_target_binding_failure(projection)
        _refresh_estimate(projection)


__all__ = [
    "SourceReference", "SourceReadGateway", "SourceContinuationReader",
    "source_continuation_uri", "source_range_uri",
    "attach_source_continuation_locators", "prepare_docs_context_read_next",
    "docs_context_read_next_cost", "attach_docs_context_read_next",
    "bind_project_source_continuations",
]
