"""Bounded source capabilities plus one budgeted docs-context recovery target."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from . import _source_continuation_core as _core
from .model_visible_projection_helpers import docs_context_budget_tokens
from .source_recovery_ranges import unseen_adjacent_range, verified_missing_ranges

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
    from docmancer.docs.domain.minimal_context_config import minimal_context_enabled
    prefix = "docatlas://source/v2/" if minimal_context_enabled() else SourceContinuationReader.uri_prefix
    return prefix + identity


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
    from docmancer.docs.domain.minimal_context_config import minimal_context_enabled
    if minimal_context_enabled():
        # Candidate delivery already contains full selected structural units.
        # Semantic rejection is not deferred evidence and creates no read-next.
        return None, None
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

    selection = retrieval.get("selection_decision") or {}
    assignments = tuple(
        row for row in selection.get("assignments", ()) if isinstance(row, dict)
    ) if isinstance(selection, dict) else ()
    current_call_candidates = list(candidates)
    current_call_candidates.extend(
        bound["source"] for bound in snapshot.values()
        if isinstance(bound, dict) and isinstance(bound.get("source"), dict)
        and bound["source"].get("source_class") == "project_doc"
    )
    seen_sources = set()
    for original in current_call_candidates:
        key = (
            _candidate_identity(original), original.get("_source_snapshot_sha256"),
            original.get("project_identity"),
        )
        if key in seen_sources:
            continue
        seen_sources.add(key)
        for _, start, end in verified_missing_ranges(
            original, assignments, frozenset(missing),
        ):
            if end - start + 1 > SourceContinuationReader.max_lines:
                continue
            target = _read_next_row(
                root, original, line_start=start, line_end=end,
                reason="requested_part_missing",
            )
            if target is not None:
                return target, original

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
        adjacent = unseen_adjacent_range(
            original, visible_start=quote_start, visible_end=quote_end,
            max_lines=SourceContinuationReader.max_lines,
        )
        if adjacent is None:
            continue
        start, end = adjacent
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
    """Attach one target without displacing the already accepted context."""
    from .model_visible_projection import _refresh_estimate
    payload["read_next"] = [deepcopy(target)] if isinstance(target, dict) else []
    _refresh_estimate(payload)
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
    *, binding_intent: str = "rebind",
) -> None:
    """Register legacy continuations and the one emitted bounded range."""
    from docmancer.docs.domain.minimal_context_config import minimal_context_enabled
    if minimal_context_enabled():
        _bind_atomic(reader, project_root, projection, snapshot, binding_intent=binding_intent)
        return
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


def _bind_atomic(reader: Any, project_root: str, projection: dict, snapshot: dict,
                 *, binding_intent: str = "rebind") -> None:
    """Prepare, price, revalidate and commit the complete capability batch.

    Failure replaces the packet with an explicit body-free refusal. The live
    reader remains unchanged; no part of a rejected batch becomes readable.
    """
    from docmancer.docs.domain.minimal_context_config import EMERGENCY_TOKENS
    from .projection_tokenizer import projection_token_count
    from .model_visible_projection_helpers import canonical_projection_bytes
    from .standalone_text_view import render_standalone_text
    from .model_visible_projection import _refresh_estimate, validate_model_visible_projection

    def reject(reason: str, **details: Any) -> None:
        projection.clear()
        projection.update(kind="docs_context", status="error", reason_code=reason,
                          hard_stop=True, sources=[], read_next=[], next_portion=None,
                          context_quality={"status": "unverified", "reasons": [reason]},
                          **details)
        snapshot.clear()

    if projection.get("hard_stop") or projection.get("reason_code") == "context_emergency_stop":
        return
    rendered = render_standalone_text(projection)
    body = rendered.text.encode("utf-8") if rendered.text is not None else canonical_projection_bytes(projection)
    measured = projection_token_count(body)
    if measured > EMERGENCY_TOKENS:
        reject("context_emergency_stop", measured_tokens=measured, emergency_tokens=EMERGENCY_TOKENS)
        return
    if not isinstance(reader, SourceContinuationReader) or not reader.minimal:
        reject("source_reference_contract_mismatch")
        return
    if (binding_intent not in {"rebind", "fresh_query"} or
            binding_intent == "fresh_query" and reader._registration_only):
        reject("source_reference_contract_mismatch")
        return
    with reader._lock:
        staged = reader.registration_snapshot()
        packet = deepcopy(projection)
        # Preserve native live lineage objects; copy only the mutable DTO binding.
        bindings = {key: {**bound, "projected_source": dict(bound.get("projected_source") or {})}
                    for key, bound in snapshot.items()}
        references = []
        issued_uris = []
        try:
            for projected in packet.get("sources") or ():
                uri = projected.get("source_uri")
                if not uri:
                    continue
                bound = bindings[projected["evidence_id"]]
                source = bound["source"]
                if binding_intent == "fresh_query":
                    if uri != source_continuation_uri(project_root, source):
                        raise ValueError("noncanonical_fresh_locator")
                    uri = staged.fresh_locator(uri)
                    projected["source_uri"] = uri
                    bound["projected_source"]["source_uri"] = uri
                    bound["source_uri"] = uri
                reference = _reference_for_source(project_root, {**source, "line_end": projected["line_end"]})
                if reference is None or staged.issue(reference, uri=uri) is None:
                    raise ValueError("source_reference_rejected")
                references.append(reference)
                issued_uris.append(uri)
            for target in packet.get("read_next") or ():
                source = _target_source(target, bindings)
                if binding_intent == "fresh_query":
                    canonical = source_range_uri(project_root, source, line_start=target["line_start"],
                                                 line_end=target["line_end"]) if source else None
                    if not canonical or target["source_uri"] != canonical:
                        raise ValueError("noncanonical_fresh_range")
                    target["source_uri"] = staged.fresh_locator(canonical)
                reference = _reference_for_source(project_root, source) if source else None
                if reference is None or staged.issue_range(reference, line_start=target["line_start"],
                        line_end=target["line_end"], uri=target["source_uri"]) is None:
                    raise ValueError("source_reference_rejected")
                references.append(reference)
                issued_uris.append(target["source_uri"])
            _refresh_estimate(packet)
            if validate_model_visible_projection(packet, snapshot=bindings):
                raise ValueError("source_projection_binding_mismatch")
            rendered = render_standalone_text(packet)
            body = rendered.text.encode("utf-8") if rendered.text is not None else canonical_projection_bytes(packet)
            measured = projection_token_count(body)
            if measured > EMERGENCY_TOKENS:
                reject("context_emergency_stop", measured_tokens=measured, emergency_tokens=EMERGENCY_TOKENS)
                return
            # Verify source bytes too: catalog authorization alone cannot detect
            # a filesystem edit between selection and capability publication.
            for reference in dict.fromkeys(references):
                if reader.gateway.authorize(reference):
                    raise ValueError("source_reference_rejected")
                raw = reader.gateway.read_snapshot(reference)
                if "sha256:" + hashlib.sha256(raw).hexdigest() != reference.content_sha256:
                    raise ValueError("source_changed")
                if reader.gateway.authorize(reference):
                    raise ValueError("source_reference_rejected")
            if any(staged.clock() >= staged._cursors[uri].expires for uri in issued_uris):
                raise ValueError("source_reference_expired")
        except (KeyError, TypeError, ValueError, OSError):
            reject("source_reference_batch_rejected")
            return
        reader._cursors = staged._cursors
        reader._spent = staged._spent
        reader._issuances = staged._issuances
        projection.clear()
        projection.update(packet)
        snapshot.clear()
        snapshot.update(bindings)


__all__ = [
    "SourceReference", "SourceReadGateway", "SourceContinuationReader",
    "source_continuation_uri", "source_range_uri",
    "attach_source_continuation_locators", "prepare_docs_context_read_next",
    "docs_context_read_next_cost", "attach_docs_context_read_next",
    "bind_project_source_continuations",
]
