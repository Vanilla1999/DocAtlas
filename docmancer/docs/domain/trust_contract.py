from __future__ import annotations

from typing import Any

from docmancer.docs.domain.project_doc_ranking import project_source_taxonomy
from docmancer.docs.models import DocsResult, ProjectDocsResult


def build_project_context_trust_contract(
    *,
    project_docs: ProjectDocsResult | None,
    dependency_docs: DocsResult | None,
    requested_library: str | None,
    mode: str,
    context_pack: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected_sources: list[dict[str, Any]] = []
    rejected_sources: list[dict[str, Any]] = []
    risky_sources: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    next_actions: list[dict[str, Any]] = []

    if project_docs:
        for source in project_docs.indexed_sources:
            source_taxonomy = project_source_taxonomy(
                source.get("path"),
                doc_scope=source.get("doc_scope") or "project",
                module_path=source.get("module_path"),
            )
            selected_sources.append({
                "source_class": "project_file",
                "source_type": source_taxonomy["source_type"],
                "source_kind": source_taxonomy["source_kind"],
                "authority": source_taxonomy["authority"],
                "risk_flags": source_taxonomy["risk_flags"],
                "path": source.get("path"),
                "source": source.get("source"),
                "doc_scope": source.get("doc_scope") or "project",
                "module_id": source.get("module_id"),
                "module_name": source.get("module_name"),
                "module_path": source.get("module_path"),
                "module_type": source.get("module_type"),
                "freshness": "current",
                "reason": "repo-owned project docs matched the question",
                "why_selected": "repo-owned project docs matched the question",
                "trust_level": "trusted",
            })
        for source in project_docs.stale_sources:
            risky = {
                "source_class": "project_file",
                "path": source.get("path"),
                "doc_scope": source.get("doc_scope") or (source.get("candidate") or {}).get("doc_scope") or "project",
                "module_id": source.get("module_id") or (source.get("candidate") or {}).get("module_id"),
                "module_name": source.get("module_name") or (source.get("candidate") or {}).get("module_name"),
                "module_path": source.get("module_path") or (source.get("candidate") or {}).get("module_path"),
                "module_type": source.get("module_type") or (source.get("candidate") or {}).get("module_type"),
                "reason_code": "project_docs_stale",
                "reason": "Indexed project docs differ from current repo files.",
                "risk_level": "medium",
            }
            risky_sources.append(risky)
            warnings.append(risky)
        next_actions.extend(project_docs.next_actions)
    elif mode in {"deps-only", "public-docs"}:
        risky_sources.append({
            "source_class": "project_file",
            "reason_code": "project_docs_skipped",
            "reason": f"Project docs were skipped because mode={mode}.",
            "risk_level": "low",
        })

    if dependency_docs:
        if dependency_docs.results:
            selected_sources.append({
                "source_class": "dependency_docs",
                "library": dependency_docs.library,
                "requested_version": dependency_docs.requested_version,
                "version": dependency_docs.resolved_version or dependency_docs.version,
                "resolved_version": dependency_docs.resolved_version or dependency_docs.version,
                "version_source": dependency_docs.version_source,
                "docs_exactness": dependency_docs.docs_exactness,
                "docs_binding_source": dependency_docs.docs_binding_source,
                "confidence": dependency_docs.confidence,
                "freshness": "stale" if dependency_docs.stale_before_refresh else "current",
                "reason": "dependency docs resolved through Docmancer registry/project metadata",
                "why_selected": "dependency docs resolved through Docmancer registry/project metadata",
                "trust_level": "trusted" if dependency_docs.docs_exactness == "exact" else "best_effort",
            })
        for warning in dependency_docs.warnings:
            risky = {
                "source_class": "dependency_docs",
                "library": dependency_docs.library,
                "reason_code": warning,
                "reason": warning,
                "risk_level": "medium",
            }
            risky_sources.append(risky)
            warnings.append(risky)
        if dependency_docs.status in {"needs_input", "ambiguous", "error"}:
            rejected_sources.append({
                "source_class": "dependency_docs",
                "library": dependency_docs.library,
                "reason_code": dependency_docs.status,
                "reason": dependency_docs.warning or "Dependency docs were not safe to use.",
                "risk_level": "high",
            })
        next_actions.extend({"tool": dependency_docs.tool, "reason": action} for action in dependency_docs.next_actions)
    elif requested_library:
        rejected_sources.append({
            "source_class": "dependency_docs",
            "library": requested_library,
            "reason_code": "not_resolved",
            "reason": "Requested dependency docs were not resolved.",
            "risk_level": "high",
        })
        next_actions.append({
            "tool": "prefetch_project_docs",
            "requires_confirmation": True,
            "reason": "Fetch dependency docs before retrying project context.",
        })

    return {
        "schema_version": "trust-contract-1.0-mvp",
        "selected_sources": selected_sources,
        "trusted_sources": selected_sources,
        "rejected_sources": rejected_sources,
        "risky_sources": risky_sources,
        "rejected_or_risky_sources": [*rejected_sources, *risky_sources],
        "selected": selected_sources,
        "trusted": selected_sources,
        "rejected": rejected_sources,
        "risky": risky_sources,
        "rejected_or_risky": [*rejected_sources, *risky_sources],
        "context_sources": _build_context_sources(context_pack),
        "warnings": warnings,
        "next_actions": next_actions,
        "policy": {
            "direct_webfetch": "forbidden" if selected_sources else "discovery_only",
            "reason_code": "trusted_context_available" if selected_sources else "no_trusted_context",
        },
    }


def _build_context_sources(context_pack: list[dict[str, Any]] | None) -> dict[str, Any]:
    repo_map: list[dict[str, Any]] = []
    source_evidence: list[dict[str, Any]] = []
    for item in context_pack or []:
        source_class = item.get("source_class")
        if source_class == "source_evidence":
            source_evidence.append(_source_evidence_contract_item(item))
        elif source_class == "repo_map":
            repo_map.append(_repo_map_contract_item(item))

    return {
        "schema_version": "context-sources-1.0",
        "source_evidence": source_evidence,
        "repo_map": repo_map,
        "policy": {
            "source_evidence": "source_snippet entries are path-line backed; absent_in_source entries are uncertainty signals",
            "repo_map": "navigation_only_not_story_claim_proof",
        },
    }


def _source_evidence_contract_item(item: dict[str, Any]) -> dict[str, Any]:
    evidence_class = str(item.get("evidence_class") or "source_evidence")
    result: dict[str, Any] = {
        "source_class": "source_evidence",
        "evidence_class": evidence_class,
        "role": "source_backed_evidence" if evidence_class == "source_snippet" else "uncertainty_signal",
        "proof_role": "path_line_evidence" if evidence_class == "source_snippet" else "not_proof_absence_signal",
        "path": item.get("path"),
        "line_start": item.get("line_start"),
        "line_end": item.get("line_end"),
        "matched_terms": _string_list(item.get("matched_terms")),
        "missing_terms": _string_list(item.get("missing_terms")),
    }
    _copy_optional(result, item, "title")
    _copy_optional(result, item, "snippet")
    _copy_optional(result, item, "freshness")
    _copy_reason(result, item)
    return result


def _repo_map_contract_item(item: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_class": "repo_map",
        "evidence_class": "navigation_map",
        "role": "navigation_context",
        "proof_role": "navigation_only",
        "path": item.get("path"),
        "line_start": item.get("line_start"),
        "line_end": item.get("line_end"),
        "matched_terms": _string_list(item.get("matched_terms")),
        "missing_terms": [],
    }
    _copy_optional(result, item, "title")
    _copy_optional(result, item, "language")
    _copy_optional(result, item, "freshness")
    _copy_reason(result, item)
    return result


def _copy_reason(result: dict[str, Any], item: dict[str, Any]) -> None:
    reason = item.get("why_selected") or item.get("reason")
    if not reason:
        return
    result["reason"] = str(reason)
    result["why_selected"] = str(reason)


def _copy_optional(result: dict[str, Any], item: dict[str, Any], key: str) -> None:
    if item.get(key) is not None:
        result[key] = item.get(key)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]
