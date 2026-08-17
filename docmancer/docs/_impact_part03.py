"""Implementation shard 3 for impact."""
from __future__ import annotations

from ._impact_shared import *  # noqa: F401,F403

from ._impact_part01 import _add_impact, _add_section_impacts, _build_documentation_update_brief, _continuation_command, _fallback_doc_candidates, _impact_candidate_priority, _is_project_authority_candidate, _is_test_path, _module_path, _normalized_paths, _normalized_symbols, _ordered_unique
from ._impact_part02 import _bound_report, _is_changed_doc_path, _matching_section_hints, _recommendation

def analyze_docs_impact(
    project_path: str | Path,
    changed_files: list[str],
    *,
    changed_symbols: list[str] | None = None,
    diff_evidence: dict[str, Any] | None = None,
    section_reader: ProjectSectionIndexReader | None = None,
    candidate_offset: int = 0,
    candidate_limit: int = _MAX_SECTION_CANDIDATES,
    continuation_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map a code diff to maintained project docs without writing repository files."""

    root = Path(project_path).expanduser().resolve()
    if candidate_offset < 0:
        raise ValueError("candidate_offset must be non-negative")
    if candidate_limit < 1 or candidate_limit > _MAX_SECTION_CANDIDATES:
        raise ValueError(f"candidate_limit must be between 1 and {_MAX_SECTION_CANDIDATES}")
    metadata = ProjectMetadataReader(max_docs_hash_bytes=_MAX_DOC_BYTES).read(
        root, docs_candidate_limit=_MAX_DOCS_ANALYZED,
    )
    all_changed = (
        _ordered_unique(changed_files)
        if diff_evidence is not None
        else _normalized_paths(changed_files)
    )
    if len(all_changed) > _MAX_CHANGED_FILES and diff_evidence is None:
        raise ValueError(
            f"At most {_MAX_CHANGED_FILES} explicit changed files are supported; use --base/--head for a bounded Git diff."
        )
    changed_input_truncated = len(all_changed) > _MAX_CHANGED_FILES
    changed = all_changed[:_MAX_CHANGED_FILES]
    automatic_symbol_evidence = list((diff_evidence or {}).get("symbol_evidence") or [])
    if automatic_symbol_evidence:
        automatic_symbols = [
            str(item.get("symbol") or "")
            for item in automatic_symbol_evidence
            if isinstance(item, dict) and not _is_test_path(str(item.get("path") or ""))
        ]
    else:
        automatic_symbols = list((diff_evidence or {}).get("symbols") or [])
    symbols = _normalized_symbols([*automatic_symbols, *(changed_symbols or [])])
    catalog_authoritative = metadata.docs_catalog_present
    catalog_document_paths = {candidate.path for candidate in metadata.docs_candidates if candidate.path}
    ignored_document_paths = {
        candidate.path for candidate in metadata.docs_candidates
        if candidate.path
        and (candidate.lifecycle_status != "active" or candidate.impact_policy != "track")
    }
    all_candidates = [
        candidate for candidate in metadata.docs_candidates
        if candidate.path
        and candidate.lifecycle_status == "active"
        and candidate.impact_policy == "track"
    ]
    candidates_by_path = {candidate.path: candidate for candidate in all_candidates}
    changed_modules = {_module_path(path) for path in changed}
    candidates = sorted(all_candidates, key=lambda candidate: _impact_candidate_priority(candidate, changed_modules))
    docs_discovery_truncated = any("Project docs discovery truncated" in warning for warning in metadata.warnings)
    module_docs: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        if candidate.module_path:
            module_docs[candidate.module_path].append(candidate.path)
    root_readmes = [
        candidate.path
        for candidate in candidates
        if (
            _is_project_authority_candidate(candidate)
            if catalog_authoritative
            else candidate.doc_scope == "project" and candidate.reason == "root_readme"
        )
    ]

    change_records = list((diff_evidence or {}).get("changes") or [])
    documentation_changes: dict[str, dict[str, Any]] = {}
    unchanged_copy_sources: set[str] = set()
    for change in change_records:
        if not isinstance(change, dict):
            continue
        kind = str(change.get("kind") or "modified")
        old_path = str(change.get("old_path") or "")
        new_path = str(change.get("new_path") or "")
        paths = [str(path) for path in change.get("paths") or [] if path]
        if kind == "renamed":
            old_is_doc = _is_changed_doc_path(old_path, catalog_document_paths, catalog_authoritative)
            new_is_doc = _is_changed_doc_path(new_path, catalog_document_paths, catalog_authoritative)
            if old_is_doc and new_is_doc:
                key = new_path or old_path
                documentation_changes[key] = {
                    "path": key, "status": "renamed", "old_path": old_path, "new_path": new_path,
                }
            elif old_is_doc:
                documentation_changes[old_path] = {"path": old_path, "status": "deleted"}
            elif new_is_doc:
                documentation_changes[new_path] = {"path": new_path, "status": "updated"}
        elif kind == "copied":
            if old_path:
                unchanged_copy_sources.add(old_path)
            if new_path and _is_changed_doc_path(new_path, catalog_document_paths, catalog_authoritative):
                documentation_changes[new_path] = {"path": new_path, "status": "updated"}
        elif kind == "deleted" and paths and _is_changed_doc_path(paths[0], catalog_document_paths, catalog_authoritative):
            documentation_changes[paths[0]] = {"path": paths[0], "status": "deleted"}
        else:
            for path in paths:
                if _is_changed_doc_path(path, catalog_document_paths, catalog_authoritative):
                    documentation_changes[path] = {"path": path, "status": "updated"}
    for path in changed:
        if path in unchanged_copy_sources:
            continue
        if path in candidates_by_path:
            documentation_changes.setdefault(path, {"path": path, "status": "updated"})
        elif not change_records and _is_changed_doc_path(path, catalog_document_paths, catalog_authoritative):
            documentation_changes.setdefault(path, {"path": path, "status": "changed_or_deleted"})
    documentation_changes = {
        path: change for path, change in documentation_changes.items()
        if path not in ignored_document_paths
    }
    documentation_change_paths = {
        path
        for item in documentation_changes.values()
        for path in (item.get("path"), item.get("old_path"), item.get("new_path"))
        if path
    } | {path for path in changed if path in ignored_document_paths}
    updated_docs = sorted(documentation_changes)
    code_changes = [
        path for path in changed
        if path not in documentation_change_paths
        and path not in unchanged_copy_sources
        and path not in candidates_by_path
        and not _is_test_path(path)
    ]
    impacts: dict[str, dict[str, Any]] = {}
    missing_modules: set[str] = set()
    missing_root_readme = False
    missing_fallback_root_docs = False
    fallback_values = list(((diff_evidence or {}).get("diagnostics") or {}).get("fallback_paths", []))
    parser_fallback_paths = set(_ordered_unique(fallback_values) if diff_evidence is not None else _normalized_paths(fallback_values))

    for path in code_changes:
        module_path = _module_path(path)
        docs = module_docs.get(module_path or "", [])
        if docs:
            reason = (
                "diff_symbol_parser_fallback"
                if path in parser_fallback_paths
                else "module_dependency_metadata_changed"
                if Path(path).name in _DEPENDENCY_FILES
                else "module_code_changed"
            )
            for doc_path in docs:
                _add_impact(impacts, doc_path, reason=reason, changed_file=path, module_path=module_path)
            continue
        if module_path:
            missing_modules.add(module_path)
            continue
        if Path(path).name in _DEPENDENCY_FILES:
            if root_readmes:
                for doc_path in root_readmes:
                    _add_impact(impacts, doc_path, reason="dependency_metadata_changed", changed_file=path, module_path=None)
            else:
                missing_root_readme = True
            continue
        matched_project_doc = False
        for candidate in candidates:
            if _is_project_authority_candidate(candidate):
                reason = "diff_symbol_parser_fallback" if path in parser_fallback_paths else "project_code_changed"
                _add_impact(impacts, candidate.path, reason=reason, changed_file=path, module_path=None)
                matched_project_doc = True
        if path in parser_fallback_paths and not matched_project_doc:
            if candidates:
                for candidate in _fallback_doc_candidates(candidates):
                    _add_impact(
                        impacts,
                        candidate.path,
                        reason="diff_symbol_parser_fallback",
                        changed_file=path,
                        module_path=None,
                    )
            else:
                missing_fallback_root_docs = True

    for doc_path in updated_docs:
        change = documentation_changes[doc_path]
        status = change["status"]
        lifecycle_module_path = (
            candidates_by_path[doc_path].module_path
            if doc_path in candidates_by_path
            else _module_path(doc_path)
        )
        if (
            status in {"deleted", "changed_or_deleted"}
            and lifecycle_module_path
            and Path(doc_path).stem.lower() in ROOT_DOC_FILES
        ):
            missing_modules.add(lifecycle_module_path)
        item = impacts.setdefault(doc_path, {
            "path": doc_path,
            "status": status,
            "reasons": [],
            "changed_files": [],
            "module_path": lifecycle_module_path,
        })
        item["status"] = status
        reason = {
            "deleted": "documentation_deleted", "renamed": "documentation_renamed",
            "changed_or_deleted": "documentation_changed_or_deleted",
        }.get(status, "documentation_changed")
        item["reasons"] = list(dict.fromkeys([*item["reasons"], reason]))
        item["changed_files"] = list(dict.fromkeys([
            *item["changed_files"],
            *[path for path in (change.get("old_path"), change.get("new_path"), doc_path) if path],
        ]))
        if change.get("old_path"):
            item["old_path"] = change["old_path"]
        if change.get("new_path"):
            item["new_path"] = change["new_path"]

    # Explicit references are stronger evidence than the module/file heuristics
    # above.  They may also identify a maintained project doc outside the
    # affected module.  Unsupported formats simply produce no section hints.
    indexed = (section_reader or ProjectSectionIndexReader()).read(root)
    metadata_diagnostics = {
        "indexed_current": [], "reparsed_missing": [], "reparsed_stale": [],
        "skipped_oversize": [], "truncated": [], "unsupported": [], "read_errors": [],
    }
    refresh_paths: list[str] = []
    section_candidates: list[dict[str, Any]] = []
    sections_by_path: dict[str, list[dict[str, Any]]] = {}
    metadata_source_by_path: dict[str, str] = {}
    section_candidates_omitted_by_work_budget = 0
    for candidate in candidates:
        if int(candidate.size_bytes or 0) > _MAX_DOC_BYTES:
            metadata_diagnostics["skipped_oversize"].append(candidate.path)
            metadata.warnings.append(
                f"Skipped section analysis for oversized project doc: {candidate.path}"
            )
            sections_by_path[candidate.path] = []
            metadata_source_by_path[candidate.path] = "skipped_oversize"
            if changed:
                _add_impact(
                    impacts, candidate.path, reason="section_analysis_skipped_oversize",
                    changed_file=changed[0], module_path=candidate.module_path,
                )
            continue
        indexed_doc = indexed.get(candidate.path)
        if indexed_doc and indexed_doc.get("status") == "current":
            sections = list(indexed_doc.get("sections") or [])
            parse_status = str(indexed_doc.get("parse_status") or "read_error")
            parse_reason = SECTION_PARSE_REASON_CODES[parse_status]
            metadata_diagnostics["indexed_current"].append(candidate.path)
            metadata_source = "index"
        else:
            parse_result = extract_section_metadata_result(root / candidate.path, source_document_path=candidate.path)
            sections = parse_result.sections
            parse_status = parse_result.status
            parse_reason = parse_result.reason_code
            stale = bool(indexed_doc)
            metadata_diagnostics["reparsed_stale" if stale else "reparsed_missing"].append(candidate.path)
            metadata_source = "reparsed_stale" if stale else "reparsed_missing"
            refresh_paths.append(candidate.path)
        parse_failure_relevant = candidate.path in impacts or candidate.path in documentation_changes
        if parse_status == "read_error" or (parse_status == "unsupported" and parse_failure_relevant):
            diagnostic_key = "unsupported" if parse_status == "unsupported" else "read_errors"
            metadata_diagnostics[diagnostic_key].append(candidate.path)
            if changed:
                _add_impact(
                    impacts, candidate.path, reason=parse_reason,
                    changed_file=changed[0], module_path=candidate.module_path,
                )
        sections_by_path[candidate.path] = sections
        metadata_source_by_path[candidate.path] = metadata_source
        section_metadata_truncated = any(
            bool(section.get("paths_truncated"))
            or bool(section.get("symbols_truncated"))
            or bool(section.get("fields_truncated"))
            or bool(section.get("document_sections_truncated"))
            for section in sections
            if isinstance(section, dict)
        )
        if section_metadata_truncated:
            metadata_diagnostics["truncated"].append(candidate.path)
            if changed:
                _add_impact(
                    impacts, candidate.path, reason="section_metadata_truncated",
                    changed_file=changed[0], module_path=candidate.module_path,
                )
        hints = _matching_section_hints(sections, changed, symbols)
        if not hints:
            continue
        remaining = max(0, _MAX_SECTION_CANDIDATES_EVALUATED - len(section_candidates))
        bounded_hints = hints[:remaining]
        section_candidates_omitted_by_work_budget += len(hints) - len(bounded_hints)
        if bounded_hints:
            _add_section_impacts(impacts, candidate.path, hints=bounded_hints, module_path=candidate.module_path)
        for hint in bounded_hints:
            reason_code = "section_reference_changed_path" if hint["reason"] == "references_changed_path" else "section_reference_changed_symbol"
            authority_boost = 5 if _is_project_authority_candidate(candidate) else 0
            score = (100 if hint["reason"] == "references_changed_symbol" else 95) + authority_boost
            section_candidates.append({
                "path": candidate.path,
                "heading_path": hint["heading_path"],
                "impact": "must_update",
                "reason_code": reason_code,
                "evidence": hint["evidence"],
                "confidence": "high",
                "score": score,
                "metadata_source": metadata_source,
                "authority": candidate.authority or candidate.reason,
            })

    missing = [{
        "module_path": module_path,
        "reason": "module_code_changed_without_module_docs",
        "suggested_path": f"{module_path}/README.md",
    } for module_path in sorted(missing_modules)]
    if missing_root_readme:
        missing.append({
            "module_path": ".",
            "reason": "dependency_metadata_changed_without_root_readme",
            "suggested_path": "README.md",
        })
    if missing_fallback_root_docs:
        missing.append({
            "module_path": ".",
            "reason": "unmapped_parser_fallback_without_project_docs",
            "suggested_path": "README.md",
        })
    impact_rows = sorted(impacts.values(), key=lambda item: item["path"])
    section_keys = {(item["path"], tuple(item["heading_path"])) for item in section_candidates}
    for item in impact_rows:
        if item.get("status") in {"updated", "deleted", "renamed", "changed_or_deleted"}:
            continue
        if item.get("sections"):
            conservative_reasons = [
                reason for reason in (item.get("reasons") or [])
                if reason in {
                    "diff_symbol_parser_fallback", "section_metadata_truncated",
                    "section_analysis_skipped_oversize", "section_format_unsupported",
                    "section_document_read_error",
                }
            ]
            if conservative_reasons:
                conservative_reason = conservative_reasons[0]
                fallback_candidate = {
                    "path": item["path"],
                    "heading_path": [],
                    "impact": "review",
                    "reason_code": conservative_reason,
                    "evidence": [
                        path for path in (item.get("changed_files") or []) if path in parser_fallback_paths
                    ][:_MAX_CHANGED_FILES] or list(item.get("changed_files") or [])[:16],
                    "confidence": "low",
                    "score": 35,
                    "metadata_source": "file_level_fallback",
                    "authority": candidates_by_path.get(item["path"]).reason if candidates_by_path.get(item["path"]) else None,
                }
                if len(section_candidates) < _MAX_SECTION_CANDIDATES_EVALUATED:
                    section_candidates.append(fallback_candidate)
                else:
                    section_candidates_omitted_by_work_budget += 1
            continue
        key = (item["path"], ())
        if key in section_keys:
            continue
        reasons = item.get("reasons") or ["project_code_changed"]
        reason = next(
            (
                value for value in reasons
                if value in {
                    "diff_symbol_parser_fallback", "section_metadata_truncated",
                    "section_analysis_skipped_oversize", "section_format_unsupported",
                    "section_document_read_error",
                }
            ),
            reasons[0],
        )
        if reason == "project_code_changed" and symbols:
            sections = sections_by_path.get(item["path"]) or [{}]
            for section in sections:
                candidate_row = {
                    "path": item["path"],
                    "heading_path": list(section.get("heading_path") or []),
                    "impact": "unlikely",
                    "reason_code": "no_explicit_reference_match",
                    "evidence": symbols[:16],
                    "confidence": "medium",
                    "score": 10,
                    "metadata_source": metadata_source_by_path.get(item["path"], "file_level_fallback"),
                    "authority": candidates_by_path.get(item["path"]).reason if candidates_by_path.get(item["path"]) else None,
                }
                if len(section_candidates) < _MAX_SECTION_CANDIDATES_EVALUATED:
                    section_candidates.append(candidate_row)
                else:
                    section_candidates_omitted_by_work_budget += 1
            continue
        candidate_row = {
            "path": item["path"],
            "heading_path": [],
            "impact": "review",
            "reason_code": reason,
            "evidence": list(item.get("changed_files") or []),
            "confidence": "low" if reason in {
                "project_code_changed", "diff_symbol_parser_fallback", "section_metadata_truncated",
                "section_analysis_skipped_oversize", "section_format_unsupported",
                "section_document_read_error",
            } else "medium",
            "score": 65 if "module" in reason else 35 if reason in {
                "diff_symbol_parser_fallback", "section_metadata_truncated", "section_analysis_skipped_oversize",
                "section_format_unsupported", "section_document_read_error",
            } else 45,
            "metadata_source": "file_level_fallback",
            "authority": candidates_by_path.get(item["path"]).reason if candidates_by_path.get(item["path"]) else None,
        }
        if len(section_candidates) < _MAX_SECTION_CANDIDATES_EVALUATED:
            section_candidates.append(candidate_row)
        else:
            section_candidates_omitted_by_work_budget += 1
    section_candidates.sort(key=lambda item: (-int(item["score"]), item["path"], item["heading_path"]))
    total_section_candidates = len(section_candidates) + section_candidates_omitted_by_work_budget
    candidate_window = section_candidates[candidate_offset:candidate_offset + candidate_limit]
    actionable_paths = {
        item["path"] for item in section_candidates if item["impact"] in {"must_update", "review"}
    }
    diff_diagnostics = (diff_evidence or {}).get("diagnostics") or {}
    incomplete_reasons: list[str] = []
    if docs_discovery_truncated:
        incomplete_reasons.append("docs_discovery_truncated")
    if section_candidates_omitted_by_work_budget:
        incomplete_reasons.append("candidate_evaluation_truncated")
    if metadata_diagnostics["skipped_oversize"]:
        incomplete_reasons.append("oversized_docs_skipped")
    if metadata_diagnostics["truncated"]:
        incomplete_reasons.append("section_metadata_truncated")
    if metadata_diagnostics["unsupported"]:
        incomplete_reasons.append("section_formats_unsupported")
    if metadata_diagnostics["read_errors"]:
        incomplete_reasons.append("section_document_read_errors")
    if metadata.docs_catalog_present and not metadata.docs_catalog_valid:
        incomplete_reasons.append("project_docs_catalog_invalid")
    if changed_input_truncated:
        incomplete_reasons.append("changed_paths_truncated")
    for diagnostic_key in (
        "changed_paths_truncated", "patch_truncated", "name_status_truncated",
        "symbols_truncated", "symbol_evidence_truncated",
    ):
        if diff_diagnostics.get(diagnostic_key):
            incomplete_reasons.append(diagnostic_key)
    incomplete_reasons = list(dict.fromkeys(incomplete_reasons))
    has_more_evaluated_candidates = (
        candidate_offset + len(candidate_window) < min(total_section_candidates, len(section_candidates))
    )
    if has_more_evaluated_candidates:
        incomplete_reasons.append("candidate_page_incomplete")
    if candidate_offset:
        incomplete_reasons.append("candidate_page_offset")
    continuation = _continuation_command(
        diff_evidence,
        project_path=str(root),
        changed_paths=changed,
        changed_symbols=list(changed_symbols or []),
        continuation_context=continuation_context,
        next_offset=candidate_offset + len(candidate_window),
        candidate_limit=candidate_limit,
        has_more=has_more_evaluated_candidates,
    )
    authoring_brief = _build_documentation_update_brief(
        root=root,
        changed_paths=changed,
        changed_symbols=symbols,
        section_candidates=candidate_window,
        missing=missing,
        incomplete_reasons=incomplete_reasons,
        documentation_changes=documentation_changes,
        diff_evidence=diff_evidence,
    )
    if any(
        isinstance(item, dict) and item.get("reason_code") == "authoring_brief_limit_exceeded"
        for item in authoring_brief.get("missing_evidence") or []
    ):
        incomplete_reasons.append("authoring_brief_limit_exceeded")
    report = {
        "schema_version": "docs-impact-2",
        "project_path": str(root),
        "changed_files": changed,
        "changed_symbols": symbols,
        "summary": {
            "changed_files": len(changed),
            "code_files": len(code_changes),
            "docs_updated": len(updated_docs),
            "docs_to_review": len(actionable_paths),
            "missing_docs": len(missing),
        },
        "impacts": impact_rows,
        "section_candidates": {
            "must_update": [item for item in candidate_window if item["impact"] == "must_update"],
            "review": [item for item in candidate_window if item["impact"] == "review"],
            "unlikely": [item for item in candidate_window if item["impact"] == "unlikely"],
        },
        "bounds": {
            "section_candidates_total": total_section_candidates,
            "section_candidates_returned": len(candidate_window),
            "candidate_offset": candidate_offset,
            "candidate_limit": candidate_limit,
            "candidate_evaluation_limit": _MAX_SECTION_CANDIDATES_EVALUATED,
            "candidate_evaluation_truncated": section_candidates_omitted_by_work_budget > 0,
            "docs_candidates_total": len(all_candidates),
            "docs_candidates_analyzed": len(candidates),
            "docs_candidates_total_is_lower_bound": docs_discovery_truncated,
            "docs_candidates_truncated": docs_discovery_truncated,
            "truncated": (
                candidate_offset > 0
                or total_section_candidates > candidate_offset + len(candidate_window)
                or docs_discovery_truncated
                or bool(incomplete_reasons)
            ),
            "analysis_complete": not incomplete_reasons,
            "incomplete_reasons": incomplete_reasons,
            "max_section_candidates": _MAX_SECTION_CANDIDATES,
            "max_output_bytes": _MAX_OUTPUT_BYTES,
            "continuation": continuation,
            "continuation_reason": (
                "next_candidate_page" if continuation
                else "invocation_too_large_narrow_diff" if has_more_evaluated_candidates
                else None
            ),
        },
        "section_metadata": metadata_diagnostics,
        "authoring_brief": authoring_brief,
        "next_actions": ([{
            "tool": "prepare_docs",
            "arguments_patch": {"action": "sync_project_docs", "project_path": str(root)},
            "reason_code": "refresh_stale_or_missing_section_metadata",
            "paths": sorted(set(refresh_paths)),
        }] if refresh_paths else []),
        "diff_evidence": (diff_evidence or {}).get("diagnostics") or {
            "symbol_confidence": "manual" if changed_symbols else "none",
            "reason_code": "explicit_paths_without_git_diff",
        },
        "missing": missing,
        "recommendation": _recommendation(
            bool(actionable_paths), missing, incomplete_reasons, docs_changed=bool(documentation_changes)
        ),
        "warnings": metadata.warnings,
    }
    return _bound_report(report)


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br>").replace("`", "\\`")

__all__=['analyze_docs_impact', '_markdown_cell']
