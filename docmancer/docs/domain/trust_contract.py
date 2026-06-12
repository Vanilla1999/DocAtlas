from __future__ import annotations

from typing import Any

from docmancer.docs.models import DocsResult, ProjectDocsResult


def build_project_context_trust_contract(
    *,
    project_docs: ProjectDocsResult | None,
    dependency_docs: DocsResult | None,
    requested_library: str | None,
    mode: str,
) -> dict[str, Any]:
    selected_sources: list[dict[str, Any]] = []
    rejected_sources: list[dict[str, Any]] = []
    risky_sources: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    next_actions: list[dict[str, Any]] = []

    if project_docs:
        for source in project_docs.indexed_sources:
            selected_sources.append({
                "source_class": "project_file",
                "path": source.get("path"),
                "source": source.get("source"),
                "freshness": "current",
                "reason": "repo-owned project docs matched the question",
                "why_selected": "repo-owned project docs matched the question",
                "trust_level": "trusted",
            })
        for source in project_docs.stale_sources:
            risky = {
                "source_class": "project_file",
                "path": source.get("path"),
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
        "warnings": warnings,
        "next_actions": next_actions,
        "policy": {
            "direct_webfetch": "forbidden" if selected_sources else "discovery_only",
            "reason_code": "trusted_context_available" if selected_sources else "no_trusted_context",
        },
    }
