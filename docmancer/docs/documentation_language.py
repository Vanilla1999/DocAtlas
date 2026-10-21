"""Declared, scope-bound documentation languages and explicit host translations.

No language detector, network, model inference, query rewriting or storage writes.
Language metadata is routing data, never source/answer/edit authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


class DocumentationLanguageError(ValueError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


def language_tags(value: Any) -> tuple[str, ...]:
    """Validate bounded BCP-47-shaped declarations; do not guess from text."""
    if not isinstance(value, list) or len(value) > 16:
        raise ValueError("documentation_languages must contain at most 16 language tags")
    tags = []
    for tag in value:
        if (not isinstance(tag, str) or len(tag) > 63
                or not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", tag)):
            raise ValueError("invalid documentation language tag")
        tags.append(tag.lower())
    if len(set(tags)) != len(tags):
        raise ValueError("duplicate documentation language tag")
    return tuple(sorted(tags))


def catalog_language_declarations(value: Any, entries: list) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict) or len(value) > 500:
        raise ValueError("documentation_languages must map finite catalog paths to language-tag lists")
    members = {entry.path for entry in entries}
    if any(not isinstance(path, str) or path not in members for path in value):
        raise ValueError("documentation_languages may only reference existing literal catalog members")
    return {path: language_tags(tags) for path, tags in value.items()}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def _unknown(reason: str, **binding: Any) -> dict:
    return {"status": "unknown", "languages": [], "basis": "not_declared",
            "reason_code": reason, "hint_only": True, **binding}


def project_language(project_path: str, inspected: dict, module: str | None = None) -> dict:
    from docmancer.docs.domain.project_path_validation import validate_project_path
    from docmancer.docs.project_docs_catalog import CATALOG_FILENAME, read_project_docs_catalog

    root = validate_project_path(project_path).path
    selector = str(module or "").strip()
    scope = {"scope": "module" if selector else "project"}
    if selector:
        scope["module_path"] = selector
    catalog = read_project_docs_catalog(root)
    if not catalog.present or not catalog.valid:
        return _unknown("language_catalog_unavailable", **scope)
    # Only already-authorized, literal current candidate paths from the existing
    # status inspector participate. No root scan, path inference or module aliases.
    candidates = {row.get("path"): row for row in inspected.get("candidate_sources", [])
                  if isinstance(row, dict)}
    entries = [entry for entry in catalog.entries
               if entry.path in candidates and entry.status == "active"
               and entry.authority in {"source_of_truth", "supporting"}
               and ((entry.scope == "module" and entry.module_path == selector) if selector
                    else (entry.scope == "project" and not entry.module_path))]
    if not entries:
        return _unknown("language_scope_unavailable", **scope)
    declarations = catalog.documentation_languages
    known: set[str] = set()
    unknown_count = 0
    identity = []
    for entry in entries:
        tags = declarations.get(entry.path, ())
        # 'und' and 'mul' declare uncertainty/multiplicity, not a language to translate to.
        concrete = [tag for tag in tags if tag not in {"und", "mul"}]
        known.update(concrete)
        unknown_count += int(not concrete or any(tag in {"und", "mul"} for tag in tags))
        identity.append((entry.path, candidates[entry.path].get("content_hash"), tags))
    try:
        # Metadata-only read; reject a final symlink and never read document text here.
        import os
        if not hasattr(os, "O_NOFOLLOW"):
            return _unknown("language_safe_metadata_read_unavailable", **scope)
        fd = os.open(root / CATALOG_FILENAME, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            data = stream.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            return _unknown("language_catalog_unavailable", **scope)
        # Detect changes across the inspector/metadata reads without accepting a
        # new member or a changed declaration into the original finite selection.
        check = read_project_docs_catalog(root)
        if not check.valid or check.entries != catalog.entries or check.documentation_languages != declarations:
            return _unknown("language_catalog_changed", **scope)
    except OSError:
        return _unknown("language_catalog_unavailable", **scope)
    status = ("unknown" if not known else "partial" if unknown_count else
              "mixed" if len(known) > 1 else "declared")
    return {"status": status, "languages": sorted(known), "basis": "catalog_declaration",
            "hint_only": True, **scope,
            "catalog_sha256": hashlib.sha256(data).hexdigest(),
            "snapshot_sha256": _digest({"root": str(root), **scope, "members": sorted(identity)}),
            "source_count": len(entries), "unknown_sources": unknown_count}


def library_language(service: Any, canonical_id: str, inspected: dict) -> dict:
    binding = {"scope": "library", "canonical_id": canonical_id,
               "version": inspected.get("version"),
               "manifest_digest": inspected.get("active_manifest_digest")}
    if inspected.get("status") == "missing":
        return _unknown("language_library_unavailable", **binding)
    record = service.registry.get(canonical_id)
    if record is None:
        return _unknown("language_library_unavailable", **binding)
    manifest = (record.target_spec or {}).get("source_manifest") or {}
    try:
        tags = language_tags(manifest.get("documentation_languages", []))
    except (ValueError, TypeError, AttributeError):
        return _unknown("language_declaration_invalid", **binding)
    concrete = [tag for tag in tags if tag not in {"und", "mul"}]
    if not concrete:
        return _unknown("language_not_declared", **binding)
    if inspected.get("stale") or not binding["manifest_digest"]:
        return _unknown("language_snapshot_unverified", **binding)
    status = "partial" if any(tag in {"und", "mul"} for tag in tags) else "mixed" if len(concrete) > 1 else "declared"
    return {"status": status, "languages": concrete, "basis": "source_manifest_declaration",
            "hint_only": True, **binding, "snapshot_sha256": _digest({**binding, "languages": tags})}


def translated_query(question: str, search_question: Any, lookups: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    """Keep the original authoritative question; spend one existing lookup slot.

    A host-supplied translation is NOT certified semantically equivalent. Source
    validation and scope boundaries do not depend on language or lookup text.
    """
    if search_question is None:
        return question, lookups
    if not isinstance(search_question, str) or not search_question.strip() or len(search_question) > 500:
        raise DocumentationLanguageError("invalid_search_question")
    combined = list(lookups)
    if search_question != question and search_question not in combined:
        combined.append(search_question)
    if len(combined) > 5:
        raise DocumentationLanguageError("search_question_lookup_limit")
    return search_question, tuple(combined)
