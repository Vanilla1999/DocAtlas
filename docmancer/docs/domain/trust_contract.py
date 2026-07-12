from __future__ import annotations

from typing import Any

from docmancer.docs.domain.project_doc_ranking import normalize_doc_path, project_source_taxonomy
from docmancer.docs.domain.content_trust import source_trust_dimensions
from docmancer.docs.models import DocsResult, ProjectDocsResult


def build_project_context_trust_contract(
    *,
    project_docs: ProjectDocsResult | None,
    dependency_docs: DocsResult | None,
    requested_library: str | None,
    mode: str,
    context_pack: list[dict[str, Any]] | None = None,
    include_legacy_aliases: bool = False,
) -> dict[str, Any]:
    selected_sources: list[dict[str, Any]] = []
    rejected_sources: list[dict[str, Any]] = []
    risky_sources: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    next_actions: list[dict[str, Any]] = []

    if project_docs:
        for source in _ordered_project_indexed_sources(project_docs, context_pack):
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
                "provenance_confidence": "repository_configured",
                "trust_level": "provenance_verified_non_instructional",
                **source_trust_dimensions(
                    path=str(source.get("path") or source.get("source") or ""),
                    scope="project",
                    repository_root=project_docs.project_path,
                ),
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
                "provenance_confidence": "version_exact" if dependency_docs.docs_exactness == "exact" else "version_best_effort",
                "trust_level": "provenance_verified_non_instructional" if dependency_docs.docs_exactness == "exact" else "best_effort_non_instructional",
                "source_provenance": {"owner": "external_source", "source_class": "dependency_docs"},
                "version_exactness": dependency_docs.docs_exactness or "unknown",
                "repository_authority": "not_applicable",
                "instruction_trust": "untrusted_data",
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

    contract = {
        "schema_version": "trust-contract-1.2",
        "sources": {
            "selected": selected_sources,
            "rejected": rejected_sources,
            "risky": risky_sources,
        },
        "context_sources": _build_context_sources(context_pack),
        "warnings": warnings,
        "next_actions": next_actions,
        "policy": {
            "direct_webfetch": "forbidden" if selected_sources else "discovery_only",
            "reason_code": "trusted_context_available" if selected_sources else "no_trusted_context",
            "document_content": "cited_data_never_lifecycle_instruction",
            "instruction_precedence": "system_user_tool_policy_over_scoped_repository_policy_over_document_data",
        },
    }
    if include_legacy_aliases:
        contract.update({
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
        })
    return contract


def _ordered_project_indexed_sources(
    project_docs: ProjectDocsResult,
    context_pack: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    indexed_sources = list(project_docs.indexed_sources)
    if len(indexed_sources) < 2:
        return indexed_sources

    source_order = _project_doc_source_order(project_docs=project_docs, context_pack=context_pack)
    if not source_order:
        return indexed_sources

    ranked_sources: list[tuple[int, int, dict[str, Any]]] = []
    for original_index, source in enumerate(indexed_sources):
        matching_ranks = [source_order[key] for key in _source_mapping_order_keys(source) if key in source_order]
        if not matching_ranks:
            continue
        rank = min(matching_ranks)
        ranked_sources.append((rank, original_index, source))
    return [source for _, _, source in sorted(ranked_sources, key=lambda row: (row[0], row[1]))]


def _project_doc_source_order(
    *,
    project_docs: ProjectDocsResult,
    context_pack: list[dict[str, Any]] | None,
) -> dict[str, int]:
    order: dict[str, int] = {}
    next_rank = 0

    def remember(keys: list[str]) -> None:
        nonlocal next_rank
        if not keys:
            return
        existing_ranks = [order[key] for key in keys if key in order]
        if existing_ranks:
            rank = min(existing_ranks)
        else:
            rank = next_rank
            next_rank += 1
        for key in keys:
            order.setdefault(key, rank)

    saw_context_project_docs = False
    for item in context_pack or []:
        if item.get("source_class") == "project_doc":
            saw_context_project_docs = True
            remember(_context_item_order_keys(item))
    if saw_context_project_docs:
        return order
    for chunk in project_docs.results:
        remember(_chunk_order_keys(chunk))
    return order


def _context_item_order_keys(item: dict[str, Any]) -> list[str]:
    raw_source = item.get("source")
    source: dict[str, Any] = raw_source if isinstance(raw_source, dict) else {}
    return _normalized_order_keys([
        item.get("path"),
        source.get("path"),
        item.get("source_url"),
        source.get("source_url"),
        item.get("url"),
        source.get("url"),
    ])


def _chunk_order_keys(chunk: Any) -> list[str]:
    return _normalized_order_keys([
        getattr(chunk, "path", None),
        getattr(chunk, "source", None),
        getattr(chunk, "url", None),
    ])


def _source_mapping_order_keys(source: dict[str, Any]) -> list[str]:
    return _normalized_order_keys([
        source.get("path"),
        source.get("source"),
        source.get("source_url"),
        source.get("url"),
    ])


def _normalized_order_keys(values: list[Any]) -> list[str]:
    keys: list[str] = []
    for value in values:
        key = normalize_doc_path(str(value) if value is not None else None)
        if key and key not in keys:
            keys.append(key)
    return keys


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
