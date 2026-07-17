from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from docmancer.docs.domain.source_map import build_project_repo_map


PROJECT_DOCS_HANDOFF_MAX_BYTES = 12 * 1024


def _serialized_bytes(value: Any) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _bounded_strings(
    values: Any,
    *,
    limit: int,
    max_characters: int,
) -> tuple[list[str], int, int]:
    if not isinstance(values, list):
        return [], 0, 0
    strings = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    bounded = [value[:max_characters] for value in strings[:limit]]
    omitted_characters = sum(max(0, len(value) - max_characters) for value in strings[:limit])
    return bounded, max(0, len(strings) - len(bounded)), omitted_characters


def bound_project_docs_handoff(
    action: dict[str, Any],
    *,
    max_bytes: int = PROJECT_DOCS_HANDOFF_MAX_BYTES,
) -> dict[str, Any]:
    """Return a deterministic compact handoff while retaining gaps and follow-up actions."""
    bounded = deepcopy(action)
    gap = dict(bounded.get("documentation_gap") or {})
    existing_bounds = gap.get("bounds") if isinstance(gap.get("bounds"), dict) else {}
    existing_omitted = existing_bounds.get("omitted_counts") if isinstance(existing_bounds, dict) else {}
    omitted: dict[str, int] = {
        key: value
        for key, value in (existing_omitted.items() if isinstance(existing_omitted, dict) else [])
        if isinstance(key, str) and isinstance(value, int) and value > 0
    }

    def record(key: str, count: int) -> None:
        if count > 0:
            omitted[key] = omitted.get(key, 0) + count

    sections: list[dict[str, Any]] = []
    raw_sections = gap.get("required_sections")
    if isinstance(raw_sections, list):
        for index, raw in enumerate(raw_sections):
            if not isinstance(raw, dict):
                record("required_sections.invalid", 1)
                continue
            section = {
                key: raw[key]
                for key in (
                    "name", "state", "evidence", "evidence_paths", "facts",
                    "missing_evidence", "discovery_suggestions",
                )
                if key in raw
            }
            record("required_sections.unknown_fields", len(set(raw) - set(section)))
            for key, limit, characters in (
                ("evidence", 12, 160),
                ("evidence_paths", 12, 320),
                ("facts", 6, 320),
                ("missing_evidence", 16, 160),
                ("discovery_suggestions", 4, 320),
            ):
                values, count, character_count = _bounded_strings(
                    section.get(key), limit=limit, max_characters=characters
                )
                section[key] = values
                record(f"required_sections.{key}", count)
                record(f"required_sections.{key}_characters", character_count)
            if isinstance(section.get("name"), str):
                original = section["name"]
                section["name"] = original[:160]
                record("required_sections.name_characters", max(0, len(original) - 160))
            sections.append(section)
    gap["required_sections"] = sections
    gap["missing_evidence"] = list(dict.fromkeys(
        item
        for section in sections
        for item in section.get("missing_evidence") or []
        if isinstance(item, str) and item
    ))

    evidence_rows: list[dict[str, Any]] = []
    raw_evidence = gap.get("evidence_to_collect")
    if isinstance(raw_evidence, list):
        for raw in raw_evidence[:24]:
            if not isinstance(raw, dict):
                record("evidence_to_collect.invalid", 1)
                continue
            row = {
                key: raw[key]
                for key in ("category", "paths", "facts")
                if key in raw
            }
            record("evidence_to_collect.unknown_fields", len(set(raw) - set(row)))
            if isinstance(row.get("category"), str):
                original = row["category"]
                row["category"] = original[:160]
                record("evidence_to_collect.category_characters", max(0, len(original) - 160))
            for key, limit, characters in (("paths", 12, 320), ("facts", 6, 320)):
                values, count, character_count = _bounded_strings(
                    row.get(key), limit=limit, max_characters=characters
                )
                row[key] = values
                record(f"evidence_to_collect.{key}", count)
                record(f"evidence_to_collect.{key}_characters", character_count)
            evidence_rows.append(row)
        record("evidence_to_collect.rows", max(0, len(raw_evidence) - 24))
    gap["evidence_to_collect"] = evidence_rows
    gap["bounds"] = {
        "max_serialized_bytes": max_bytes,
        "serialized_bytes": 0,
        "truncated": bool(omitted),
        "omitted_counts": omitted,
    }
    bounded["documentation_gap"] = gap

    argument_holders = [
        *(bounded.get("after") or []),
        bounded.get("after_file_change"),
    ]
    for follow_up in argument_holders:
        if not isinstance(follow_up, dict):
            continue
        arguments = follow_up.get("arguments_patch")
        if not isinstance(arguments, dict):
            continue
        for key, value in list(arguments.items()):
            if not isinstance(value, str):
                continue
            max_characters = 512 if key == "question" else 1024
            if len(value) > max_characters:
                arguments[key] = value[:max_characters]
                record(
                    f"action.arguments_patch.{key}_characters",
                    len(value) - max_characters,
                )
    for key, max_characters in (("reason", 1024), ("agent_guidance", 1024)):
        value = bounded.get(key)
        if isinstance(value, str) and len(value) > max_characters:
            bounded[key] = value[:max_characters]
            record(f"action.{key}_characters", len(value) - max_characters)

    def over_budget() -> bool:
        return _serialized_bytes(bounded) > max_bytes

    removable_lists: list[tuple[str, list[Any], int]] = []
    for row in reversed(evidence_rows):
        removable_lists.extend([
            ("evidence_to_collect.facts", row.get("facts") or [], 0),
            ("evidence_to_collect.paths", row.get("paths") or [], 0),
        ])
    for section in reversed(sections):
        removable_lists.extend([
            ("required_sections.facts", section.get("facts") or [], 0),
            ("required_sections.evidence_paths", section.get("evidence_paths") or [], 0),
            ("required_sections.discovery_suggestions", section.get("discovery_suggestions") or [], 1),
        ])
    for key, values, minimum in removable_lists:
        while over_budget() and len(values) > minimum:
            values.pop()
            record(key, 1)

    while over_budget() and evidence_rows:
        evidence_rows.pop()
        record("evidence_to_collect.rows", 1)

    for key in ("reason", "agent_guidance", "suggested_paths"):
        if over_budget() and key in bounded:
            bounded.pop(key)
            record(f"action.{key}", 1)

    while over_budget() and sections:
        sections.pop()
        record("required_sections.rows", 1)

    bounds = gap["bounds"]
    bounds["truncated"] = bool(omitted)
    bounds["omitted_counts"] = dict(sorted(omitted.items()))
    for _ in range(3):
        bounds["serialized_bytes"] = _serialized_bytes(bounded)
    if bounds["serialized_bytes"] > max_bytes:
        raise ValueError("project docs handoff cannot fit the configured byte limit")
    return bounded


def partition_project_doc_state(
    candidates: list[dict[str, Any]],
    indexed_sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_by_path = {item.get("path"): item for item in candidates if item.get("path")}
    indexed_by_path = {item.get("path"): item for item in indexed_sources if item.get("path")}
    current: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    for path, indexed in indexed_by_path.items():
        candidate = candidate_by_path.get(path)
        if not candidate:
            ignored.append({
                **indexed,
                "stale": True,
                "reason": "indexed_source_not_discovered",
                "meaning": "This source exists in the index, but current project-doc discovery did not select it as a candidate.",
                "recommended_next_action": "Add or correct its entry in docatlas.project-docs.yaml, or refresh/remove the obsolete indexed source.",
            })
            continue
        stale_reasons: list[str] = []
        metadata_drift_reasons: list[str] = []
        if candidate.get("content_hash") != indexed.get("content_hash"):
            stale_reasons.append("content_hash_changed")
        if candidate.get("catalog_entry_hash") != indexed.get("catalog_entry_hash"):
            stale_reasons.append("catalog_metadata_changed")
        if candidate.get("mtime_ns") != indexed.get("mtime_ns"):
            metadata_drift_reasons.append("mtime_changed")
        merged = {**indexed, "candidate": candidate, "stale": bool(stale_reasons)}
        if metadata_drift_reasons:
            merged["metadata_drift_reasons"] = metadata_drift_reasons
            merged["current_mtime_ns"] = candidate.get("mtime_ns")
        if stale_reasons:
            merged["stale_reasons"] = stale_reasons
            merged["current_content_hash"] = candidate.get("content_hash")
            stale.append(merged)
        else:
            current.append(merged)
    return current, stale, ignored


def has_high_level_project_overview(candidates: list[dict[str, Any]]) -> bool:
    for candidate in candidates:
        reason = str(candidate.get("reason") or "")
        path = Path(str(candidate.get("path") or ""))
        stem = path.stem.lower()
        parts = {part.lower() for part in path.parts}
        if reason in {"root_readme", "architecture", "overview", "project_architecture"}:
            return True
        if stem in {"overview", "introduction", "intro", "index", "readme"}:
            return True
        if "overview" in parts or "architecture" in parts:
            return True
    return False


def _documentation_gap_evidence(root: Path, query: str | None) -> list[dict[str, Any]]:
    manifests = [
        name for name in ("pyproject.toml", "package.json", "Cargo.toml", "pubspec.yaml")
        if (root / name).exists()
    ]
    source_paths = [
        str(item.get("path"))
        for item in build_project_repo_map(root, question=query or "architecture", max_files=6, token_budget=800)
        if item.get("path")
    ]
    evidence = []
    if manifests:
        evidence.append({"category": "manifests", "paths": manifests})
    if source_paths:
        evidence.append({"category": "source map", "paths": list(dict.fromkeys(source_paths))})
    return evidence


def evaluate_documentation_sections(
    required_sections: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """Evaluate claim support conservatively for each requested document section."""
    evidence_by_category: dict[str, dict[str, list[str]]] = {}
    for item in evidence:
        raw_category = item.get("category")
        if not isinstance(raw_category, str) or not (category := raw_category.strip()):
            continue
        raw_paths = item.get("paths")
        raw_facts = item.get("facts")
        paths = [value.strip() for value in raw_paths if isinstance(value, str) and value.strip()] if isinstance(raw_paths, list) else []
        facts = [value.strip() for value in raw_facts if isinstance(value, str) and value.strip()] if isinstance(raw_facts, list) else []
        if not paths and not facts:
            continue
        combined = evidence_by_category.setdefault(category, {"paths": [], "facts": []})
        combined["paths"] = list(dict.fromkeys([*combined["paths"], *paths]))
        combined["facts"] = list(dict.fromkeys([*combined["facts"], *facts]))
    sections: list[dict[str, Any]] = []
    for required in required_sections:
        categories = [
            category.strip()
            for category in required.get("evidence") or []
            if isinstance(category, str) and category.strip()
        ]
        matched = [evidence_by_category[category] for category in categories if category in evidence_by_category]
        missing = [category for category in categories if category not in evidence_by_category]
        if not categories:
            missing = ["required evidence categories"]
        state = "complete" if not missing else ("partial" if matched else "missing")
        paths = list(dict.fromkeys(path for item in matched for path in item["paths"]))
        facts = list(dict.fromkeys(fact for item in matched for fact in item["facts"]))
        sections.append({
            **required,
            "state": state,
            "evidence_paths": paths,
            "facts": facts,
            "missing_evidence": missing,
            "discovery_suggestions": [
                f"Inspect repository files for {category}; keep the claim unknown if no evidence is found."
                for category in missing
            ],
        })
    return sections, bool(sections) and all(section["state"] == "complete" for section in sections)


def create_project_docs_next_action(root: Path, query: str | None = None, *, reason: str | None = None) -> dict[str, Any]:
    get_docs_context_args = {"project_path": str(root)}
    if query:
        get_docs_context_args["question"] = query
    evidence_to_collect = _documentation_gap_evidence(root, query)
    required_sections = [
        {"name": "purpose", "evidence": ["manifests", "root entrypoints"]},
        {"name": "entrypoints", "evidence": ["root entrypoints", "runtime configuration"]},
        {"name": "modules", "evidence": ["module directories", "module imports"]},
        {"name": "runtime flow", "evidence": ["entrypoints", "module imports", "runtime configuration"]},
        {"name": "development commands", "evidence": ["manifests", "test and build configuration"]},
    ]
    required_sections, evidence_complete = evaluate_documentation_sections(required_sections, evidence_to_collect)
    action = {
        "action": "create_reviewable_project_doc",
        "requires_confirmation": True,
        "preferred_path": "ARCHITECTURE.md",
        "suggested_paths": ["ARCHITECTURE.md", "README.md", "docs/architecture.md"],
        "reason": reason or "No official project docs files were discovered. Ask the user before creating a reviewable architecture doc in the repository.",
        "agent_guidance": "If the user approves, inspect the listed evidence, create ARCHITECTURE.md as a normal reviewable file, then use the returned public prepare_docs action before retrying get_docs_context.",
        "documentation_gap": {
            "suggested_path": "ARCHITECTURE.md",
            "required_sections": required_sections,
            "evidence_to_collect": evidence_to_collect,
            "evidence_complete": evidence_complete,
            "rules": [
                "do not invent unsupported facts",
                "cite repository paths for factual claims",
                "mark uncertain claims as unknown",
            ],
        },
        "after_file_change": {
            "tool": "prepare_docs",
            "arguments_patch": {"action": "sync_project_docs", "project_path": str(root)},
        },
        "after": [
            {
                "tool": "prepare_docs",
                "requires_confirmation": False,
                "arguments_patch": {"action": "sync_project_docs", "project_path": str(root)},
            },
            {"tool": "get_docs_context", "requires_confirmation": False, "arguments_patch": get_docs_context_args},
        ],
    }
    return bound_project_docs_handoff(action)


def project_docs_structured_next_action(
    *,
    reason_code: str,
    root: Path,
    query: str | None = None,
) -> tuple[dict[str, Any], bool, str | None, dict[str, Any], str, str | None]:
    project_args = {"project_path": str(root)}
    sync_args = {"project_path": str(root), "with_vectors": True}
    if reason_code in {"project_docs_stale", "project_docs_found_not_indexed", "project_docs_needs_sync"}:
        if reason_code == "project_docs_stale":
            message = "Indexed project documentation is stale. Call sync_project_docs before answering project-level questions."
        elif reason_code == "project_docs_found_not_indexed":
            message = "Project documentation files were found but are not indexed. Call sync_project_docs before answering project-level questions."
        else:
            message = "Project documentation index is out of sync. Call sync_project_docs before answering project-level questions."
        return ({"type": "sync_project_docs", "tool": "sync_project_docs"}, False, None, sync_args, message, None)
    if reason_code in {"no_project_docs", "architecture_doc_creation_recommended"}:
        handoff = create_project_docs_next_action(root, query)
        agent_message = "No reviewable project docs were found. Ask the user whether to create ARCHITECTURE.md as a repository file, then inspect and sync it after creation."
        user_message = "Project documentation was not found. Create ARCHITECTURE.md as a reviewable file?"
        if reason_code == "architecture_doc_creation_recommended":
            agent_message = "Project docs exist, but no high-level architecture or overview document was found. Ask the user before creating ARCHITECTURE.md as a repository file, then inspect and sync it after creation."
            user_message = "I could not find a high-level project architecture document. Do you want me to inspect the repository and create ARCHITECTURE.md as a reviewable file?"
        structured_handoff = bound_project_docs_handoff({
                "action": "create_reviewable_project_doc",
                "type": "ask_user_to_create_project_doc",
                "suggested_file": "ARCHITECTURE.md",
                "handled_by": "coding_agent",
                "documentation_gap": handoff["documentation_gap"],
                "after_file_change": handoff["after_file_change"],
                "after": handoff["after"],
            })
        return (
            structured_handoff,
            True,
            "repo_write",
            project_args,
            agent_message,
            user_message,
        )
    get_context_args = {"project_path": str(root)}
    if query:
        get_context_args["question"] = query
    return ({"type": "get_project_context", "tool": "get_project_context"}, False, None, get_context_args, "Project documentation is indexed and ready. Use get_project_context or get_project_docs for repo-specific questions.", None)
