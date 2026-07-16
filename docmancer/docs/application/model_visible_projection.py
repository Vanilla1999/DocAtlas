"""Canonical, provider-free projection from rich retrieval to model-visible context."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any, Iterable

from docmancer.docs.application.action_packet import evidence_identity_for_item
from docmancer.docs.application.evidence_selection import (
    docs_selection_config,
    select_evidence,
)
from docmancer.docs.domain.request_intent import model_projection_kind


DOCS_ANSWER_MAX_TOKENS = 800
PATCH_CONTEXT_TARGET_TOKENS = 1_500
PATCH_CONTEXT_HARD_TOKENS = 2_000
INSUFFICIENT_EVIDENCE_MAX_TOKENS = 300
MAX_DOCS_SOURCES = 3
FORBIDDEN_MODEL_KEYS = frozenset({
    "context_pack", "content", "surrounding_context", "ingestion_diagnostics",
    "retrieval_diagnostics", "diagnostics", "repo_map", "code_graph",
    "primary_snippet", "primary_snippets", "primary_snippet_alternatives",
    "supporting_snippets", "successful_logs", "indexing_logs", "test_logs",
})

def canonical_projection_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def estimate_projection_tokens(value: Any) -> int:
    size = len(canonical_projection_bytes(value))
    return max(1, math.ceil(size / 4))


def projection_kind(question: str) -> str:
    """Classify explicit change requests without treating how-to questions as edits."""

    return model_projection_kind(question)


def project_docs_answer(
    *,
    question: str,
    retrieval: dict[str, Any],
    max_tokens: int = DOCS_ANSWER_MAX_TOKENS,
    selection_diagnostics: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Create one deduplicated source list and an internal immutable snapshot."""

    candidates = _docs_candidates(retrieval)
    decision = select_evidence(
        candidates,
        question=question,
        config=docs_selection_config(max_tokens),
        trust_contract=retrieval.get("trust_contract") or {},
        exact_version=_requested_exact_version(retrieval),
        required_evidence_paths=retrieval.get("required_evidence_paths") or (),
        required_target_paths=retrieval.get("required_target_paths") or (),
        public_requirements=retrieval.get("public_requirements") or (),
        project_identity=retrieval.get("project_identity"),
        module_id=retrieval.get("module_id"),
    )
    if selection_diagnostics is not None:
        selection_diagnostics.update(decision.audit_manifest())
    sources: list[dict[str, Any]] = []
    snapshot: dict[str, dict[str, Any]] = {}
    omitted = len(decision.omissions)
    for item in decision.selected_items:
        normalized = _docs_source(item)
        if normalized is None:
            omitted += 1
            continue
        evidence_id = normalized["evidence_id"]
        sources.append(normalized)
        snapshot[evidence_id] = {"source": deepcopy(item), **normalized}

    retrieval_issues = _docs_retrieval_issues(retrieval)
    if decision.status != "ok" or not sources or retrieval_issues:
        missing = [str(retrieval.get("message") or "No complete source-backed documentation answer is available.")]
        missing.extend(decision.missing_requirements)
        missing.extend(decision.unresolved_conflicts)
        missing.extend(retrieval_issues)
        return project_insufficient(
            kind="docs_answer", missing=missing,
            recommended_next_action=retrieval.get("next_action"), max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
        ), snapshot

    answer, answer_evidence_ids = _answer_text(question, retrieval, sources)
    payload: dict[str, Any] = {
        "status": "ok",
        "kind": "docs_answer",
        "answer": answer,
        "answer_evidence_ids": answer_evidence_ids,
        "sources": sources,
        "omitted_counts": {"sources": omitted} if omitted else {},
        "estimated_tokens": 0,
    }
    _refresh_estimate(payload)
    if estimate_projection_tokens(payload) > min(DOCS_ANSWER_MAX_TOKENS, max_tokens):
        return project_insufficient(
            kind="docs_answer", missing=["The selected documentation evidence exceeds the bounded answer budget."],
            recommended_next_action=None, max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
        ), snapshot
    return payload, snapshot


def _requested_exact_version(retrieval: dict[str, Any]) -> str | None:
    """Return a version only when retrieval says the binding is exact."""

    exactness = str(retrieval.get("docs_exactness") or "").casefold().replace("-", "_")
    if exactness not in {"exact", "exact_version", "version_exact", "exact_version_indexed"}:
        return None
    value = retrieval.get("requested_version") or retrieval.get("resolved_version")
    return str(value).strip() if value is not None and str(value).strip() else None


def project_patch_context(
    *, packet: dict[str, Any], evidence_items: Iterable[dict[str, Any]], max_tokens: int = PATCH_CONTEXT_TARGET_TOKENS
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Flatten a validated ActionPacket without exposing its rich evidence input."""

    raw_evidence: dict[str, dict[str, Any]] = {}
    for original in evidence_items:
        if not isinstance(original, dict):
            continue
        for authority in ("canonical", "supporting"):
            candidate = deepcopy(original)
            candidate["_packet_authority"] = authority
            evidence_id, _, _ = evidence_identity_for_item(candidate)
            raw_evidence.setdefault(evidence_id, deepcopy(original))
    if packet.get("status") == "insufficient_evidence":
        return project_insufficient(
            kind="patch_context",
            missing=list(packet.get("missing_evidence") or ["Required patch evidence is unavailable."]),
            recommended_next_action=None,
            max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
        ), {}

    snapshot: dict[str, dict[str, Any]] = {}
    sources: list[dict[str, Any]] = []
    for row in packet.get("source_of_truth") or []:
        evidence_id = str(row.get("evidence_id") or "")
        item = raw_evidence.get(evidence_id)
        if not item:
            continue
        digest = _source_digest(item)
        projected = {**deepcopy(row), "content_sha256": digest}
        sources.append(projected)
        snapshot[evidence_id] = {"source": item, **projected}

    payload: dict[str, Any] = {
        "status": packet.get("status"),
        "kind": "patch_context",
        "schema_version": packet.get("schema_version"),
        "objective": deepcopy((packet.get("task_interpretation") or {}).get("objective")),
        "acceptance_conditions": deepcopy((packet.get("task_interpretation") or {}).get("acceptance_conditions") or []),
        "sources": sources,
        "targets": deepcopy(packet.get("target_surface") or {"likely_files": [], "symbols": []}),
        "invariants": deepcopy(packet.get("required_invariants") or []),
        "forbidden_changes": deepcopy(packet.get("forbidden_changes") or []),
        "implementation_guidance": deepcopy(packet.get("implementation_guidance") or []),
        "checks": deepcopy(packet.get("validation") or {"compile": [], "tests": [], "semantic_checks": []}),
        "uncertainties": deepcopy(packet.get("uncertainties") or []),
        "omitted_counts": deepcopy(packet.get("omitted_counts") or {}),
        "estimated_tokens": 0,
    }
    _refresh_estimate(payload)
    limit = min(PATCH_CONTEXT_HARD_TOKENS, max(256, int(max_tokens)))
    if estimate_projection_tokens(payload) > limit:
        return project_insufficient(
            kind="patch_context", missing=["The validated patch context exceeds the model-visible budget."],
            recommended_next_action=None, max_tokens=INSUFFICIENT_EVIDENCE_MAX_TOKENS,
        ), snapshot
    return payload, snapshot


def project_insufficient(
    *, kind: str, missing: Iterable[str], recommended_next_action: Any, max_tokens: int = INSUFFICIENT_EVIDENCE_MAX_TOKENS
) -> dict[str, Any]:
    messages = [str(item).strip() for item in missing if str(item).strip()][:5]
    payload: dict[str, Any] = {
        "status": "insufficient_evidence",
        "kind": kind,
        "missing": messages or ["Required source-backed evidence is unavailable."],
        "estimated_tokens": 0,
    }
    action = _bounded_action(recommended_next_action)
    if action:
        payload["recommended_next_action"] = action
    _refresh_estimate(payload)
    while estimate_projection_tokens(payload) > min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens) and len(payload["missing"]) > 1:
        payload["missing"].pop()
        _refresh_estimate(payload)
    if estimate_projection_tokens(payload) > min(INSUFFICIENT_EVIDENCE_MAX_TOKENS, max_tokens):
        payload.pop("recommended_next_action", None)
        payload["missing"] = ["Required source-backed evidence is unavailable within the response budget."]
        _refresh_estimate(payload)
    return payload


def validate_model_visible_projection(
    payload: Any, *, snapshot: dict[str, dict[str, Any]], max_tokens: int
) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["model-visible projection must be an object"]
    forbidden = sorted(_find_forbidden_keys(payload))
    if forbidden:
        errors.append("forbidden model-visible keys: " + ", ".join(forbidden))
    status, kind = payload.get("status"), payload.get("kind")
    if kind not in {"docs_answer", "patch_context"}:
        errors.append("invalid projection kind")
    if status not in {"ok", "truncated", "insufficient_evidence"}:
        errors.append("invalid projection status")
    limit = INSUFFICIENT_EVIDENCE_MAX_TOKENS if status == "insufficient_evidence" else max_tokens
    actual = estimate_projection_tokens(payload)
    if payload.get("estimated_tokens") != actual or actual > limit:
        errors.append("projection estimate mismatch or budget exceeded")
    if status == "insufficient_evidence":
        if payload.get("implementation_guidance") or payload.get("invariants") or payload.get("targets"):
            errors.append("insufficient evidence must not authorize edits")
        return errors
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("successful projections require sources")
        return errors
    if kind == "docs_answer" and len(sources) > MAX_DOCS_SOURCES:
        errors.append("docs_answer exceeds source limit")
    ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            errors.append("projection source must be an object")
            continue
        evidence_id = str(source.get("evidence_id") or "")
        bound = snapshot.get(evidence_id)
        if not evidence_id or not bound:
            errors.append("projection evidence_id does not resolve to the internal snapshot")
            continue
        if source.get("content_sha256") != bound.get("content_sha256"):
            errors.append("projection source hash does not match the internal snapshot")
        bound_source = bound.get("source")
        if not isinstance(bound_source, dict) or _source_digest(bound_source) != bound.get("content_sha256"):
            errors.append("internal snapshot hash does not match its source content")
        for key in ("path_or_url", "section", "snippet", "version_binding"):
            if key in source and source.get(key) != bound.get(key):
                errors.append(f"projection source {key} does not match the internal snapshot")
        ids.add(evidence_id)
    if kind == "docs_answer":
        answer_refs = payload.get("answer_evidence_ids")
        if not isinstance(answer_refs, list) or not answer_refs or any(ref not in ids for ref in answer_refs):
            errors.append("docs_answer claims require valid evidence IDs")
    if kind == "patch_context":
        for item in _cited_patch_items(payload):
            refs = item.get("evidence_ids")
            if not isinstance(refs, list) or not refs or any(ref not in ids for ref in refs):
                errors.append("factual patch item has missing or unknown evidence_ids")
                break
    return errors


def sanitized_projection_manifest(snapshot: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Return deterministic audit metadata without full source text."""

    allowed = ("evidence_id", "path_or_url", "path", "section", "symbol_or_section", "version_binding", "content_sha256")
    rows = [
        {key: deepcopy(value[key]) for key in allowed if value.get(key) not in (None, "")}
        for _, value in sorted(snapshot.items())
    ]
    return rows


def _docs_candidates(retrieval: dict[str, Any]) -> list[dict[str, Any]]:
    values = [retrieval.get("primary_snippet"), *(retrieval.get("primary_snippets") or []), *(retrieval.get("supporting_snippets") or []), *(retrieval.get("context_pack") or [])]
    return [dict(item) for item in values if isinstance(item, dict)]


def _docs_source(item: dict[str, Any]) -> dict[str, Any] | None:
    path = str(item.get("source_url") or item.get("url") or item.get("path") or item.get("source") or "").strip()
    section = str(item.get("heading_path") or item.get("title") or "document").strip()
    snippet = item.get("code") or item.get("snippet") or item.get("content")
    if isinstance(snippet, dict):
        snippet = snippet.get("code") or snippet.get("text")
    snippet = str(snippet or "").strip()
    version = str(item.get("version_binding") or item.get("version") or item.get("requested_version") or "unversioned")
    if (
        not path or not snippet or len(path) > 500 or len(section) > 300
        or len(snippet) > 3_000 or len(version) > 100
    ):
        return None
    digest = _source_digest(item)
    identity = canonical_projection_bytes({"path": path, "section": section, "sha256": digest})
    return {
        "evidence_id": "ev-" + hashlib.sha256(identity).hexdigest()[:16],
        "path_or_url": path,
        "section": section,
        "snippet": snippet,
        "version_binding": version,
        "content_sha256": digest,
    }


def _source_digest(item: dict[str, Any]) -> str:
    material = {
        "path": item.get("path") or item.get("source") or item.get("url") or item.get("source_url"),
        "section": item.get("heading_path") or item.get("title"),
        "content": item.get("content"),
        "snippet": item.get("snippet") or item.get("code"),
        "version": item.get("version_binding") or item.get("version") or item.get("requested_version"),
    }
    return hashlib.sha256(canonical_projection_bytes(material)).hexdigest()


def _answer_text(
    question: str, retrieval: dict[str, Any], sources: list[dict[str, Any]]
) -> tuple[str, list[str]]:
    """Return only text that is directly present in one or more projected sources."""

    explicit = retrieval.get("answer")
    if isinstance(explicit, str) and explicit.strip():
        normalized = " ".join(explicit.split()).casefold()
        refs = [
            str(source["evidence_id"])
            for source in sources
            if normalized and normalized in " ".join(str(source.get("snippet") or "").split()).casefold()
        ]
        if refs:
            return explicit.strip(), refs
    primary = sources[0]
    return str(primary["snippet"]), [str(primary["evidence_id"])]


def _docs_retrieval_issues(retrieval: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    status = str(retrieval.get("status") or "success").strip().lower()
    if status != "success":
        issues.append(f"Documentation retrieval is incomplete (status={status}).")
    if retrieval.get("answer_available") is False:
        issues.append("The requested documentation evidence is not currently available.")
    if retrieval.get("requires_confirmation"):
        issues.append("Documentation retrieval requires explicit confirmation.")
    if retrieval.get("answer_type") in {"navigation_only", "partial_navigational", "partial", "unavailable"}:
        issues.append("The retrieval result is not a complete source-backed answer.")
    completeness = retrieval.get("answer_completeness")
    if isinstance(completeness, dict):
        if completeness.get("source_search_required"):
            issues.append("Source search is required before answering.")
        completeness_status = str(completeness.get("status") or "").strip().lower()
        if completeness_status and completeness_status not in {"exact", "complete"}:
            issues.append(f"Evidence completeness is {completeness_status}.")
    lanes = retrieval.get("lanes")
    if isinstance(lanes, dict):
        failed = sorted(
            str(name) for name, lane in lanes.items()
            if isinstance(lane, dict)
            and str(lane.get("status") or "").strip().lower() not in {"success", "not_requested"}
        )
        if failed:
            issues.append("Required documentation lanes are incomplete: " + ", ".join(failed[:5]) + ".")
    return issues


def _bounded_action(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    allowed = ("tool", "type", "arguments_patch", "question", "requires_confirmation", "confirmation_reason")
    result = {key: deepcopy(value[key]) for key in allowed if value.get(key) not in (None, {}, [])}
    result["auto_execute"] = False
    return result


def _find_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_MODEL_KEYS:
                found.add(str(key))
            found.update(_find_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_find_forbidden_keys(child))
    return found


def _cited_patch_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    values: list[Any] = [
        payload.get("acceptance_conditions"), payload.get("invariants"), payload.get("forbidden_changes"),
        payload.get("implementation_guidance"), (payload.get("targets") or {}).get("likely_files"),
        (payload.get("targets") or {}).get("symbols"), *((payload.get("checks") or {}).values()),
    ]
    return [item for value in values if isinstance(value, list) for item in value if isinstance(item, dict)]


def _refresh_estimate(payload: dict[str, Any]) -> None:
    payload["estimated_tokens"] = 0
    for _ in range(3):
        actual = estimate_projection_tokens(payload)
        if payload["estimated_tokens"] == actual:
            break
        payload["estimated_tokens"] = actual
