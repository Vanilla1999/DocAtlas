from __future__ import annotations

import ast
import json
import os
import re
import shlex
import subprocess
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any

from docmancer.docs.project import DOC_DIRECTORIES, DOC_FILE_EXTENSIONS, ROOT_DOC_FILES, ProjectMetadataReader
from docmancer.docs.application.project_section_index import ProjectSectionIndexReader
from docmancer.docs.section_metadata import SECTION_PARSE_REASON_CODES, extract_section_metadata_result


_MODULE_ROOTS = {"packages", "apps", "services", "modules", "libs", "crates", "plugins", "components"}
_LIB_MODULE_ROOTS = {"modules", "features"}
_DEPENDENCY_FILES = {
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "pubspec.yaml", "pubspec.lock", "Cargo.toml", "Cargo.lock",
    "pyproject.toml", "poetry.lock", "uv.lock", "requirements.txt",
}
_MAX_CHANGED_FILES = 500
_MAX_SECTION_CANDIDATES = 200
_MAX_SECTION_CANDIDATES_EVALUATED = 2000
_MAX_DOCS_ANALYZED = 500
_MAX_FALLBACK_DOCS = 5
_MAX_OUTPUT_BYTES = 32 * 1024
_MAX_PATCH_BYTES = 2 * 1024 * 1024
_MAX_GIT_STATUS_BYTES = 4 * 1024 * 1024
_MAX_GIT_STDERR_BYTES = 64 * 1024
_MAX_GIT_PATHSPEC_BYTES = 256 * 1024
_GIT_DEADLINE_SECONDS = 15.0
_MAX_SYMBOLS = 256
_MAX_SYMBOL_EVIDENCE = 1000
_MAX_DOC_BYTES = 16 * 1024 * 1024
_SYMBOL_PATTERNS = {
    ".py": re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)"),
    ".js": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)|^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
    ".jsx": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)|^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
    ".ts": re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(?:async\s+)?(?:function|class|interface|type|enum)\s+([A-Za-z_$][A-Za-z0-9_$]*)|^(?:export\s+)?(?:declare\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
    ".tsx": re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(?:async\s+)?(?:function|class|interface|type|enum)\s+([A-Za-z_$][A-Za-z0-9_$]*)|^(?:export\s+)?(?:declare\s+)?(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
    ".dart": re.compile(r"^\s*(?:abstract\s+)?(?:class|enum|mixin|extension|typedef)\s+([A-Za-z_][A-Za-z0-9_]*)|^\s*(?!(?:return|await|throw|yield|if|for|while|switch|new)\b)(?:[A-Za-z_][A-Za-z0-9_<>,?\[\] ]+\s+)+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
}


def changed_files_from_git(project_path: str | Path, base: str, head: str = "HEAD") -> list[str]:
    """Return bounded, NUL-safe changed paths for two git refs."""
    root = Path(project_path).expanduser().resolve()
    stdout, stderr, returncode, truncated, timed_out = _run_process_bounded(
        ["git", "-C", str(root), "diff", "--name-only", "-z", "--diff-filter=ACDMR", base, head],
        max_stdout_bytes=_MAX_GIT_STATUS_BYTES,
    )
    if timed_out:
        raise ValueError(f"Could not read changed files for {base}..{head}: git diff exceeded the execution deadline")
    if returncode != 0 and not truncated:
        message = os.fsdecode(stderr).strip() or "git diff failed"
        raise ValueError(f"Could not read changed files for {base}..{head}: {message}")
    values = [os.fsdecode(value) for value in stdout.split(b"\0") if value]
    if truncated or len(values) > _MAX_CHANGED_FILES:
        raise ValueError(
            f"Could not return a complete changed-file list for {base}..{head}: bounded Git status was truncated"
        )
    return [_safe_git_text(path) for path in _ordered_unique(values)[:_MAX_CHANGED_FILES]]


def changed_evidence_from_git(project_path: str | Path, base: str, head: str = "HEAD") -> dict[str, Any]:
    """Return changed paths and bounded symbol evidence from an actual git diff."""
    root = Path(project_path).expanduser().resolve()
    names_stdout, names_stderr, names_returncode, names_truncated, names_timed_out = _run_process_bounded(
        ["git", "-C", str(root), "diff", "--name-status", "-z", "--find-renames", "--diff-filter=ACDMRT", base, head],
        max_stdout_bytes=_MAX_GIT_STATUS_BYTES,
    )
    if names_timed_out:
        raise ValueError(f"Could not read changed evidence for {base}..{head}: git name-status exceeded the execution deadline")
    if names_returncode != 0 and not names_truncated:
        message = os.fsdecode(names_stderr).strip() or "git diff failed"
        raise ValueError(f"Could not read changed evidence for {base}..{head}: {message}")
    changes = _parse_name_status_z(names_stdout)
    all_paths = _ordered_unique(path for change in changes for path in change["paths"])
    selected_changes: list[dict[str, Any]] = []
    paths: list[str] = []
    pathspec_bytes = 0
    path_selection_truncated = False
    for change in changes:
        new_paths = [path for path in change["paths"] if path not in paths]
        new_pathspec_bytes = sum(len(os.fsencode(path)) + 1 for path in new_paths)
        if (
            len(paths) + len(new_paths) > _MAX_CHANGED_FILES
            or pathspec_bytes + new_pathspec_bytes > _MAX_GIT_PATHSPEC_BYTES
        ):
            path_selection_truncated = True
            break
        selected_changes.append(change)
        paths.extend(new_paths)
        pathspec_bytes += new_pathspec_bytes
    patch_bytes, patch_truncated, patch_error = _bounded_git_patch(
        root, base=base, head=head, paths=paths,
    )
    if patch_error:
        raise ValueError(f"Could not read changed evidence for {base}..{head}: {patch_error}")
    patch_text = patch_bytes.decode("utf-8", errors="surrogateescape")
    symbols, diagnostics = _symbols_from_patch(patch_text)
    symbol_evidence = list(diagnostics.pop("symbol_evidence", []) or [])
    supported_paths = set(diagnostics.get("supported_paths") or [])
    fallback_paths = set(diagnostics.get("fallback_paths") or [])
    diagnostics.pop("symbol_paths", None)
    # Pure renames have no ---/+++ hunk headers. Quoted or unusual paths may
    # also be absent from textual patch headers. Name-status is the canonical
    # source of changed paths, so anything not proven parsed remains fallback.
    fallback_paths.update(path for path in paths if path not in supported_paths and path not in fallback_paths)
    if patch_truncated:
        fallback_paths.update(paths)
    diagnostics["supported_paths"] = [_safe_git_text(path) for path in sorted(supported_paths)[:_MAX_CHANGED_FILES]]
    diagnostics["fallback_paths"] = [_safe_git_text(path) for path in sorted(fallback_paths)[:_MAX_CHANGED_FILES]]
    diagnostics["symbol_confidence"] = (
        "high" if symbols and not fallback_paths and not patch_truncated else "low" if paths else "none"
    )
    diagnostics["reason_code"] = (
        "diff_symbols_parsed"
        if diagnostics["symbol_confidence"] == "high"
        else "diff_symbol_parser_partial"
        if symbols
        else "diff_symbol_parser_fallback"
    )
    return {
        "paths": [_safe_git_text(path) for path in paths],
        "symbols": symbols,
        "symbol_evidence": [
            {"symbol": _safe_git_text(str(item["symbol"])), "path": _safe_git_text(str(item["path"]))}
            for item in symbol_evidence[:_MAX_SYMBOL_EVIDENCE]
        ],
        "changes": [_safe_git_change(change) for change in selected_changes],
        "diagnostics": {
            **diagnostics,
            "base": base,
            "head": head,
            "patch_bytes_read": len(patch_bytes),
            "patch_truncated": patch_truncated,
            "name_status_truncated": names_truncated,
            "pathspec_truncated": path_selection_truncated,
            "changed_paths_total": len(all_paths),
            "changed_paths_total_is_lower_bound": names_truncated,
            "changed_paths_truncated": names_truncated or path_selection_truncated or len(paths) < len(all_paths),
        },
    }


def _parse_name_status_z(output: bytes) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    fields = output.split(b"\0")
    index = 0
    while index < len(fields) and fields[index]:
        status = fields[index].decode("ascii", errors="replace")
        index += 1
        path_count = 2 if status.startswith(("R", "C")) else 1
        if index + path_count > len(fields):
            break
        paths = [os.fsdecode(value) for value in fields[index:index + path_count]]
        index += path_count
        if len(paths) == 2:
            kind = "renamed" if status.startswith("R") else "copied"
            changes.append({"kind": kind, "old_path": paths[0], "new_path": paths[1], "paths": paths})
        else:
            kind = {"A": "added", "D": "deleted", "M": "modified", "T": "type_changed"}.get(status[:1], "modified")
            changes.append({"kind": kind, "path": paths[0], "paths": paths})
    return changes


def _bounded_git_patch(root: Path, *, base: str, head: str, paths: list[str]) -> tuple[bytes, bool, str | None]:
    if not paths:
        return b"", False, None
    command = [
        "git", "-C", str(root), "-c", "core.quotePath=false", "diff", "--unified=0",
        "--find-renames", "--no-ext-diff", base, head, "--", *paths,
    ]
    payload, stderr, returncode, truncated, timed_out = _run_process_bounded(
        command, max_stdout_bytes=_MAX_PATCH_BYTES,
    )
    if timed_out:
        return payload, True, "git diff exceeded the bounded execution deadline"
    if returncode != 0 and not truncated:
        return payload, truncated, os.fsdecode(stderr).strip() or "git diff failed"
    return payload, truncated, None


def _run_process_bounded(
    command: list[str],
    *,
    max_stdout_bytes: int,
    timeout_seconds: float = _GIT_DEADLINE_SECONDS,
) -> tuple[bytes, bytes, int, bool, bool]:
    """Drain a subprocess concurrently while enforcing byte and wall-clock limits."""
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        return b"", str(exc).encode("utf-8", errors="replace"), 1, False, False
    assert process.stdout is not None and process.stderr is not None
    stdout = bytearray()
    stderr = bytearray()
    stdout_truncated = threading.Event()

    def _read_stdout() -> None:
        while True:
            chunk = process.stdout.read(64 * 1024)
            if not chunk:
                return
            remaining = max_stdout_bytes - len(stdout)
            if remaining > 0:
                stdout.extend(chunk[:remaining])
            if len(chunk) > remaining:
                stdout_truncated.set()
                try:
                    process.terminate()
                except OSError:
                    pass
                return

    def _read_stderr() -> None:
        while True:
            chunk = process.stderr.read(16 * 1024)
            if not chunk:
                return
            remaining = _MAX_GIT_STDERR_BYTES - len(stderr)
            if remaining > 0:
                stderr.extend(chunk[:remaining])

    threads = [threading.Thread(target=_read_stdout, daemon=True), threading.Thread(target=_read_stderr, daemon=True)]
    for thread in threads:
        thread.start()
    timed_out = False
    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        returncode = process.wait()
    for thread in threads:
        thread.join(timeout=1)
    return bytes(stdout), bytes(stderr), returncode, stdout_truncated.is_set(), timed_out


def _symbols_from_patch(patch: str) -> tuple[list[str], dict[str, Any]]:
    symbols: list[str] = []
    current_path: str | None = None
    fallback_paths: set[str] = set()
    supported_paths: set[str] = set()
    symbol_paths: set[str] = set()
    symbol_paths_by_symbol: dict[str, set[str]] = defaultdict(set)
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            current_path = None
            continue
        if line.startswith("+++ "):
            raw = _decode_patch_path(line[4:].strip())
            if raw != "/dev/null":
                current_path = raw[2:] if raw.startswith("b/") else None
            continue
        if line.startswith("--- ") and current_path is None:
            raw = _decode_patch_path(line[4:].strip())
            current_path = raw[2:] if raw.startswith("a/") and raw != "/dev/null" else None
            continue
        if not current_path:
            continue
        pattern = _SYMBOL_PATTERNS.get(Path(current_path).suffix.lower())
        if pattern is None:
            fallback_paths.add(current_path)
            continue
        supported_paths.add(current_path)
        candidate = ""
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            candidate = line[1:]
        elif line.startswith("@@") and "@@" in line[2:]:
            candidate = line.rsplit("@@", 1)[-1]
        if not candidate:
            continue
        match = pattern.match(candidate)
        if match:
            symbol = next((group for group in match.groups() if group), "")
            if symbol and symbol not in symbols:
                symbols.append(symbol)
            if symbol:
                symbol_paths.add(current_path)
                symbol_paths_by_symbol[symbol].add(current_path)
        elif line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            # A recognized extension with an unrecognized changed line is only
            # partially covered. Hunk context may still yield useful symbols,
            # but it must not upgrade the whole file to high confidence.
            fallback_paths.add(current_path)
    # A symbol found in one file is not evidence that every other supported
    # file in the same diff was parsed successfully. Keep those uncovered
    # paths on the conservative fallback path.
    symbols_total = len(symbols)
    returned_symbols = symbols[:_MAX_SYMBOLS]
    omitted_symbols = symbols[_MAX_SYMBOLS:]
    fallback_paths.update(supported_paths - symbol_paths)
    fallback_paths.update(
        path for symbol in omitted_symbols for path in symbol_paths_by_symbol.get(symbol, set())
    )
    symbols_truncated = bool(omitted_symbols)
    confidence = (
        "high" if returned_symbols and supported_paths and not fallback_paths and not symbols_truncated
        else "low" if patch.strip() else "none"
    )
    all_evidence = [
        {"symbol": symbol, "path": path}
        for symbol in returned_symbols
        for path in sorted(symbol_paths_by_symbol.get(symbol, set()))
    ]
    symbol_evidence_truncated = len(all_evidence) > _MAX_SYMBOL_EVIDENCE
    if symbol_evidence_truncated:
        fallback_paths.update(supported_paths)
        confidence = "low"
    evidence = all_evidence[:_MAX_SYMBOL_EVIDENCE]
    return returned_symbols, {
        "symbol_confidence": confidence,
        "symbols_total": symbols_total,
        "symbols_returned": len(returned_symbols),
        "symbols_truncated": symbols_truncated,
        "symbol_evidence_truncated": symbol_evidence_truncated,
        "supported_paths": sorted(supported_paths)[:_MAX_CHANGED_FILES],
        "fallback_paths": sorted(fallback_paths)[:_MAX_CHANGED_FILES],
        "symbol_paths": sorted(symbol_paths)[:_MAX_CHANGED_FILES],
        "symbol_evidence": evidence,
        "reason_code": (
            "diff_symbols_parsed"
            if returned_symbols and not fallback_paths and not symbols_truncated
            else "diff_symbol_parser_partial"
            if returned_symbols
            else "diff_symbol_parser_fallback"
        ),
    }


def _decode_patch_path(value: str) -> str:
    if value.startswith('"') and value.endswith('"'):
        try:
            decoded = ast.literal_eval(value)
            if isinstance(decoded, str):
                return decoded
        except (SyntaxError, ValueError):
            return value
    return value


def _ordered_unique(values: Any) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _safe_git_text(value: str) -> str:
    return value.encode("utf-8", errors="backslashreplace").decode("utf-8")


def _safe_git_change(change: dict[str, Any]) -> dict[str, Any]:
    return {
        key: [_safe_git_text(item) for item in value] if key == "paths" else _safe_git_text(value) if key.endswith("path") else value
        for key, value in change.items()
    }


def _impact_candidate_priority(candidate: Any, changed_modules: set[str | None]) -> tuple[int, str]:
    if candidate.module_path and candidate.module_path in changed_modules:
        tier = 0
    elif _is_project_authority_candidate(candidate):
        tier = 1
    else:
        tier = 2
    return tier, candidate.path


def _fallback_doc_candidates(candidates: list[Any]) -> list[Any]:
    return sorted(
        candidates,
        key=lambda candidate: (
            0 if _is_project_authority_candidate(candidate) else 1,
            candidate.path,
        ),
    )[:_MAX_FALLBACK_DOCS]


def _continuation_command(
    diff_evidence: dict[str, Any] | None,
    *,
    project_path: str,
    changed_paths: list[str],
    changed_symbols: list[str],
    continuation_context: dict[str, Any] | None,
    next_offset: int,
    candidate_limit: int,
    has_more: bool,
) -> str | None:
    if not has_more:
        return None
    context = continuation_context or {}
    diagnostics = (diff_evidence or {}).get("diagnostics") or {}
    if diff_evidence is not None:
        base = str(diagnostics.get("base") or "BASE_REF")
        head = str(diagnostics.get("head") or "HEAD_REF")
        source_args = f"--base {shlex.quote(base)} --head {shlex.quote(head)}"
    elif len(changed_paths) <= 20:
        source_args = " ".join(f"--changed-file {shlex.quote(path)}" for path in changed_paths)
    else:
        source_args = "CHANGED_FILE_ARGS"
    common_args = ["--project-path", shlex.quote(str(context.get("project_path") or project_path))]
    config_path = context.get("config_path")
    if config_path:
        common_args.extend(["--config", shlex.quote(str(config_path))])
    for symbol in changed_symbols:
        common_args.extend(["--changed-symbol", shlex.quote(str(symbol))])
    if context.get("fail_on_missing"):
        common_args.append("--fail-on-missing")
    command = (
        f"doc-atlas docs-impact {' '.join(common_args)} {source_args} --candidate-offset {next_offset} "
        f"--candidate-limit {candidate_limit} --format json"
    )
    if len(command.encode("utf-8")) > 1024:
        return None
    return command


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


def format_docs_impact_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "## DocAtlas documentation impact",
        "",
        f"Changed files: **{summary['changed_files']}** · docs updated: **{summary['docs_updated']}** · docs to review: **{summary['docs_to_review']}** · missing docs: **{summary['missing_docs']}**.",
        "",
    ]
    updated = [
        item for item in (report.get("impacts") or [])
        if item.get("status") in {"updated", "deleted", "renamed", "changed_or_deleted"}
    ]
    if updated:
        lines.extend(["### Documentation changed in this diff", ""])
        lines.extend(
            f"- `{_markdown_cell(item['path'])}` ({_markdown_cell(item.get('status', 'updated'))})"
            for item in updated
        )
        lines.append("")
    labels = {
        "must_update": "Must update",
        "review": "Review",
        "unlikely": "Unlikely to require an update",
    }
    for bucket in ("must_update", "review", "unlikely"):
        candidates = (report.get("section_candidates") or {}).get(bucket) or []
        if not candidates:
            continue
        lines.extend([f"### {labels[bucket]}", "", "| Document section | Confidence | Reason | Evidence |", "|---|---|---|---|"])
        for item in candidates:
            path = _markdown_cell(item["path"])
            heading = _markdown_cell(" > ".join(item.get("heading_path") or []) or "(document)")
            evidence = _markdown_cell(", ".join(str(value) for value in item.get("evidence") or []))
            lines.append(
                f"| `{path}` — `{heading}` | {_markdown_cell(item.get('confidence', 'unknown'))} | "
                f"{_markdown_cell(item.get('reason_code', 'unknown'))} | {evidence} |"
            )
        lines.append("")
    missing = report.get("missing") or []
    if missing:
        lines.extend(["### Documentation gaps", ""])
        for item in missing:
            lines.append(
                f"- `{_markdown_cell(item['module_path'])}` changed without module docs; "
                f"consider `{_markdown_cell(item['suggested_path'])}`."
            )
        lines.append("")
    brief = report.get("authoring_brief") or {}
    if brief:
        lines.extend(["### Host-model documentation update brief", ""])
        lines.append(f"Status: `{_markdown_cell(brief.get('status', 'unknown'))}`.")
        lines.append("")
        allowed_edits = brief.get("allowed_edits") or []
        if allowed_edits:
            lines.append("Allowed edits:")
            lines.extend(
                f"- `{_markdown_cell(item.get('path'))}` — `{_markdown_cell(' > '.join(item.get('heading_path') or []) or '(document)')}`"
                for item in allowed_edits
            )
            lines.append("")
        for value in brief.get("must_not_invent") or []:
            lines.append(f"- Do not invent: {_markdown_cell(value)}")
        if brief.get("must_not_invent"):
            lines.append("")
        follow_up = brief.get("follow_up") or {}
        if follow_up:
            lines.append(
                f"After review, call `{follow_up.get('tool')}` with "
                f"`{_markdown_cell(json.dumps(follow_up.get('arguments_patch') or {}, ensure_ascii=False, sort_keys=True))}`."
            )
            lines.append("")
    bounds = report.get("bounds") or {}
    if bounds.get("truncated"):
        lines.extend([
            "### Truncation notice",
            "",
            (
                f"Returned **{bounds.get('section_candidates_returned', 0)}** of "
                f"**{bounds.get('section_candidates_total', 0)}** candidate sections. "
                f"Analyzed **{bounds.get('docs_candidates_analyzed', 0)}** of "
                f"**{bounds.get('docs_candidates_total', 0)}** discovered docs."
            ),
            "",
        ])
        if bounds.get("continuation"):
            lines.extend([f"Continue with: `{bounds['continuation']}`", ""])
        elif bounds.get("continuation_reason"):
            lines.extend([f"Continuation unavailable: `{bounds['continuation_reason']}`.", ""])
        if bounds.get("incomplete_reasons"):
            reasons = ", ".join(str(value) for value in bounds["incomplete_reasons"])
            lines.extend([f"Incomplete analysis reasons: `{_markdown_cell(reasons)}`.", ""])
        if report.get("omitted"):
            omitted = ", ".join(f"{key}={value}" for key, value in sorted(report["omitted"].items()))
            lines.extend([f"Omitted: {omitted}", ""])
    evidence = report.get("diff_evidence") or {}
    if evidence:
        lines.extend([
            f"Diff evidence: confidence=`{evidence.get('symbol_confidence', 'unknown')}`, "
            f"reason=`{evidence.get('reason_code', 'unknown')}`.",
            "",
        ])
    actions = report.get("next_actions") or []
    if actions:
        lines.extend(["### Next actions", ""])
        for action in actions:
            lines.append(f"- `{action.get('tool', 'unknown')}` — `{action.get('reason_code', 'unknown')}`")
        lines.append("")
    lines.append(f"**Recommendation:** {report['recommendation']}")
    return "\n".join(lines)


def _bound_report(report: dict[str, Any]) -> dict[str, Any]:
    """Enforce the public serialized-output bound while retaining strongest evidence."""
    buckets = report.get("section_candidates") or {}
    report["bounds"]["serialized_bytes"] = 0
    omitted = report.setdefault("omitted", {})
    # Reserve space for final counters (`serialized_bytes`, omitted counts) so
    # adding the accounting itself cannot push the public payload over 32 KiB.
    target_bytes = _MAX_OUTPUT_BYTES - 512
    while len(json.dumps(report, ensure_ascii=False).encode("utf-8")) > target_bytes:
        removed = False
        impacts = report.get("impacts") or []
        if impacts:
            count = max(1, len(impacts) // 2)
            del impacts[-count:]
            omitted["impacts"] = omitted.get("impacts", 0) + count
            removed = True
            report["bounds"]["truncated"] = True
            report["bounds"]["output_truncated"] = True
        if removed:
            continue
        for bucket in ("unlikely", "review", "must_update"):
            values = buckets.get(bucket) or []
            if values:
                count = max(1, len(values) // 2)
                del values[-count:]
                omitted[f"section_candidates.{bucket}"] = omitted.get(f"section_candidates.{bucket}", 0) + count
                removed = True
                report["bounds"]["truncated"] = True
                report["bounds"]["output_truncated"] = True
                break
        if removed:
            continue
        changed = report.get("changed_files") or []
        if len(changed) > 20:
            count = max(1, (len(changed) - 20) // 2)
            del changed[-count:]
            omitted["changed_files"] = omitted.get("changed_files", 0) + count
            report["bounds"]["truncated"] = True
            report["bounds"]["output_truncated"] = True
            continue
        if _trim_auxiliary_report_list(report, omitted):
            report["bounds"]["truncated"] = True
            report["bounds"]["output_truncated"] = True
            continue
        report = _minimal_bounded_report(report, omitted)
        buckets = report["section_candidates"]
        break
    report["bounds"]["section_candidates_returned"] = sum(len(value or []) for value in buckets.values())
    for _ in range(2):
        report["bounds"]["serialized_bytes"] = len(json.dumps(report, ensure_ascii=False).encode("utf-8"))
    if report["bounds"]["serialized_bytes"] > _MAX_OUTPUT_BYTES:
        report = _minimal_bounded_report(report, omitted)
        report["bounds"]["section_candidates_returned"] = 0
        while _serialized_size(report) > _MAX_OUTPUT_BYTES:
            if report["changed_symbols"]:
                report["changed_symbols"].pop()
                omitted["changed_symbols"] = omitted.get("changed_symbols", 0) + 1
            elif report["changed_files"]:
                report["changed_files"].pop()
                omitted["changed_files"] = omitted.get("changed_files", 0) + 1
            else:
                # All remaining fields have fixed, bounded shapes. This branch
                # is a final guard against unusual JSON escaping behavior.
                report["project_path"] = ""
                report["summary"] = {}
                report["omitted"] = {"output_fields": 1}
                break
        for _ in range(2):
            report["bounds"]["serialized_bytes"] = _serialized_size(report)
    _refresh_continuation(report)
    for _ in range(2):
        report["bounds"]["serialized_bytes"] = _serialized_size(report)
    return report


def _trim_auxiliary_report_list(report: dict[str, Any], omitted: dict[str, int]) -> bool:
    locations: list[tuple[str, list[Any]]] = []
    metadata = report.get("section_metadata") or {}
    for key in (
        "reparsed_missing", "reparsed_stale", "indexed_current", "skipped_oversize", "truncated",
        "unsupported", "read_errors",
    ):
        locations.append((f"section_metadata.{key}", metadata.get(key) or []))
    for index, action in enumerate(report.get("next_actions") or []):
        locations.append((f"next_actions.{index}.paths", action.get("paths") or []))
    locations.extend([
        ("missing", report.get("missing") or []),
        ("warnings", report.get("warnings") or []),
        ("changed_symbols", report.get("changed_symbols") or []),
        ("diff_evidence.supported_paths", (report.get("diff_evidence") or {}).get("supported_paths") or []),
        ("diff_evidence.fallback_paths", (report.get("diff_evidence") or {}).get("fallback_paths") or []),
        ("authoring_brief.allowed_edits", (report.get("authoring_brief") or {}).get("allowed_edits") or []),
        ("authoring_brief.facts_to_verify", (report.get("authoring_brief") or {}).get("facts_to_verify") or []),
        ("authoring_brief.missing_evidence", (report.get("authoring_brief") or {}).get("missing_evidence") or []),
    ])
    for name, values in locations:
        if values:
            count = max(1, len(values) // 2)
            del values[-count:]
            omitted[name] = omitted.get(name, 0) + count
            return True
    return False


def _minimal_bounded_report(report: dict[str, Any], omitted: dict[str, int]) -> dict[str, Any]:
    """Last-resort shape for adversarially long individual fields."""
    raw_bounds = report.get("bounds") or {}
    bounds = {
        key: value
        for key, value in raw_bounds.items()
        if key in {
            "section_candidates_total", "section_candidates_returned", "candidate_offset", "candidate_limit",
            "candidate_evaluation_limit", "candidate_evaluation_truncated", "docs_candidates_total",
            "docs_candidates_analyzed", "docs_candidates_total_is_lower_bound", "docs_candidates_truncated",
            "truncated", "output_truncated", "max_section_candidates", "max_output_bytes", "serialized_bytes",
            "analysis_complete",
        }
        and isinstance(value, (int, float, bool))
    }
    if raw_bounds.get("continuation"):
        bounds["continuation"] = _bounded_text(raw_bounds["continuation"], 1024)
    if raw_bounds.get("continuation_reason"):
        bounds["continuation_reason"] = _bounded_text(raw_bounds["continuation_reason"], 128)
    if raw_bounds.get("incomplete_reasons"):
        bounds["incomplete_reasons"] = [
            _bounded_text(value, 128) for value in list(raw_bounds["incomplete_reasons"])[:16]
        ]
    bounds.update({"truncated": True, "output_truncated": True})
    compact = {
        "schema_version": report.get("schema_version"),
        "project_path": _bounded_text(report.get("project_path"), 256),
        "summary": {
            key: value
            for key, value in (report.get("summary") or {}).items()
            if key in {"changed_files", "code_files", "docs_updated", "docs_to_review", "missing_docs"}
            and isinstance(value, (int, float, bool))
        },
        "changed_files": [_bounded_text(value, 128) for value in list(report.get("changed_files") or [])[:20]],
        "changed_symbols": [_bounded_text(value, 128) for value in list(report.get("changed_symbols") or [])[:20]],
        "impacts": [],
        "section_candidates": {"must_update": [], "review": [], "unlikely": []},
        "bounds": bounds,
        "section_metadata": {
            "indexed_current": [], "reparsed_missing": [], "reparsed_stale": [],
            "skipped_oversize": [], "truncated": [],
        },
        "authoring_brief": {
            "schema_version": "documentation-update-brief-1",
            "status": "output_truncated",
            "allowed_edits": [],
            "facts_to_verify": [],
            "missing_evidence": ["output_truncated"],
            "must_not_invent": ["Do not edit documentation until the impact report is rerun with a narrower diff."],
            "follow_up": {},
        },
        "next_actions": [],
        "diff_evidence": {"reason_code": "output_truncated"},
        "missing": [],
        "recommendation": "Output exceeded the safe bound; continue with the next candidate offset or narrow the diff.",
        "warnings": [],
        "omitted": omitted,
    }
    return compact


def _bounded_text(value: object, max_characters: int) -> str:
    return str(value or "")[:max_characters]


def _build_documentation_update_brief(
    *,
    root: Path,
    changed_paths: list[str],
    changed_symbols: list[str],
    section_candidates: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    incomplete_reasons: list[str],
    documentation_changes: dict[str, dict[str, Any]],
    diff_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    actionable = [
        item for item in section_candidates
        if item.get("impact") in {"must_update", "review"}
    ]
    allowed_edits: list[dict[str, Any]] = []
    seen_edit_targets: set[tuple[str, tuple[str, ...]]] = set()
    for item in actionable:
        if not item.get("path"):
            continue
        target = (
            str(item.get("path") or ""),
            tuple(str(value) for value in item.get("heading_path") or []),
        )
        if target in seen_edit_targets:
            continue
        seen_edit_targets.add(target)
        allowed_edits.append({
            "path": str(item.get("path") or ""),
            "heading_path": list(item.get("heading_path") or []),
            "reason_code": str(item.get("reason_code") or "unknown"),
            "confidence": str(item.get("confidence") or "unknown"),
        })
    allowed_paths = list(dict.fromkeys(item["path"] for item in allowed_edits))
    facts_to_verify: list[dict[str, Any]] = []
    symbol_evidence = list((diff_evidence or {}).get("symbol_evidence") or [])
    for item in symbol_evidence[:64]:
        if not isinstance(item, dict) or not item.get("symbol") or not item.get("path"):
            continue
        facts_to_verify.append({
            "kind": "changed_symbol",
            "symbol": str(item["symbol"]),
            "source_path": str(item["path"]),
            "verification_sources": [str(item["path"]), "tests", "runtime configuration"],
        })
    if not facts_to_verify:
        facts_to_verify.extend({
            "kind": "changed_path",
            "source_path": path,
            "verification_sources": [path, "tests", "runtime configuration"],
        } for path in changed_paths[:64])
    missing_evidence = [
        {"reason_code": reason, "required_action": "narrow the diff or collect the missing repository evidence"}
        for reason in incomplete_reasons
    ]
    missing_evidence.extend({
        "reason_code": "missing_module_documentation",
        "module_path": item.get("module_path"),
        "suggested_path": item.get("suggested_path"),
        "required_action": "inspect module code, configuration, and tests before proposing a new reviewable document",
    } for item in missing)
    status = (
        "needs_evidence" if missing_evidence
        else "ready_for_host_edit" if allowed_edits
        else "docs_already_changed" if documentation_changes
        else "no_documentation_edit_recommended"
    )
    follow_up_paths = list(dict.fromkeys([
        *allowed_paths,
        *[str(path) for path in documentation_changes if path],
    ]))
    return {
        "schema_version": "documentation-update-brief-1",
        "status": status,
        "changed_paths": changed_paths[:64],
        "changed_symbols": changed_symbols[:64],
        "facts_to_verify": facts_to_verify,
        "allowed_edits": allowed_edits,
        "missing_evidence": missing_evidence,
        "must_not_invent": [
            "Do not claim behavior that is not verified in repository code, configuration, or tests.",
            "Do not edit files or sections outside allowed_edits without rerunning impact analysis.",
            "Do not treat an uncommitted or rejected documentation proposal as accepted project truth.",
        ],
        "follow_up": {
            "tool": "prepare_docs",
            "arguments_patch": {
                "action": "sync_project_docs",
                "project_path": str(root),
                "changed_paths": follow_up_paths[:64],
            },
            "when": "after the user or host agent reviews and saves the documentation patch",
        } if follow_up_paths else {},
    }


def _serialized_size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br>").replace("`", "\\`")


def _refresh_continuation(report: dict[str, Any]) -> None:
    bounds = report.get("bounds") or {}
    offset = int(bounds.get("candidate_offset") or 0)
    returned = int(bounds.get("section_candidates_returned") or 0)
    total = int(bounds.get("section_candidates_total") or 0)
    evaluation_limit = int(bounds.get("candidate_evaluation_limit") or _MAX_SECTION_CANDIDATES_EVALUATED)
    evaluated_end = min(total, evaluation_limit)
    if offset + returned >= evaluated_end:
        bounds["continuation"] = None
        bounds["continuation_reason"] = (
            "evaluation_budget_exhausted_narrow_diff"
            if total > evaluated_end or bounds.get("candidate_evaluation_truncated")
            else "analysis_incomplete_narrow_diff"
            if not bounds.get("analysis_complete", True)
            else None
        )
        return
    next_offset = offset + returned
    limit = int(bounds.get("candidate_limit") or _MAX_SECTION_CANDIDATES)
    if returned == 0:
        limit = max(1, limit // 2)
    command = str(bounds.get("continuation") or "")
    if command:
        command = re.sub(r"--candidate-offset\s+\d+", f"--candidate-offset {next_offset}", command)
        command = re.sub(r"--candidate-limit\s+\d+", f"--candidate-limit {limit}", command)
    else:
        bounds["continuation"] = None
        bounds["continuation_reason"] = bounds.get("continuation_reason") or "output_truncated_rerun_narrower_page"
        return
    bounds["continuation"] = command
    bounds["continuation_reason"] = "next_candidate_page"


def _add_impact(impacts: dict[str, dict[str, Any]], path: str, *, reason: str, changed_file: str, module_path: str | None) -> None:
    item = impacts.setdefault(path, {
        "path": path,
        "status": "review_required",
        "reasons": [],
        "changed_files": [],
        "module_path": module_path,
    })
    item["reasons"] = list(dict.fromkeys([*item["reasons"], reason]))
    item["changed_files"] = list(dict.fromkeys([*item["changed_files"], changed_file]))


def _add_section_impacts(
    impacts: dict[str, dict[str, Any]],
    path: str,
    *,
    hints: list[dict[str, Any]],
    module_path: str | None,
) -> None:
    item = impacts.setdefault(path, {
        "path": path,
        "status": "review_required",
        "reasons": [],
        "changed_files": [],
        "module_path": module_path,
    })
    for hint in hints:
        is_path = hint["reason"] == "references_changed_path"
        reason = "section_reference_changed_path" if is_path else "section_reference_changed_symbol"
        item["reasons"] = list(dict.fromkeys([*item["reasons"], reason]))
        if is_path:
            item["changed_files"] = list(dict.fromkeys([*item["changed_files"], *hint["evidence"]]))
    item["sections"] = hints


def _module_path(path: str) -> str | None:
    parts = Path(path).parts
    if len(parts) >= 2 and parts[0] in _MODULE_ROOTS:
        return "/".join(parts[:2])
    if len(parts) >= 3 and parts[0] == "lib" and parts[1] in _LIB_MODULE_ROOTS:
        return "/".join(parts[:3])
    return None


def _looks_like_doc_path(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").strip("/")
    if not normalized:
        return False
    file_path = Path(normalized)
    directory_parts = {part.lower() for part in file_path.parts[:-1]}
    if file_path.name in _DEPENDENCY_FILES and not directory_parts.intersection(DOC_DIRECTORIES):
        return False
    if file_path.suffix.lower() in DOC_FILE_EXTENSIONS:
        return True
    return file_path.name.lower() in ROOT_DOC_FILES


def _is_changed_doc_path(path: str, catalog_paths: set[str], catalog_authoritative: bool) -> bool:
    normalized = str(path or "").replace("\\", "/").strip("/")
    return normalized in catalog_paths if catalog_authoritative else _looks_like_doc_path(normalized)


def _is_project_authority_candidate(candidate: Any) -> bool:
    if getattr(candidate, "doc_scope", "project") != "project":
        return False
    role = str(getattr(candidate, "reason", "") or "")
    authority = str(getattr(candidate, "authority", "") or "")
    return (
        role in {"architecture", "root_readme", "overview", "project_architecture"}
        or getattr(candidate, "path", "") == "docs/INDEX.md"
        or authority == "source_of_truth"
    )


def _is_test_path(path: str) -> bool:
    parts = {part.lower() for part in Path(path).parts}
    name = Path(path).name.lower()
    test_suffixes = (
        "_test.py", "_test.go", ".test.js", ".spec.js", ".test.jsx", ".spec.jsx",
        ".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx",
    )
    return bool(parts & {"tests", "test", "__tests__"}) or name.startswith("test_") or name.endswith(test_suffixes)


def _normalized_paths(paths: list[str]) -> list[str]:
    return sorted({str(path).replace("\\", "/").strip("/") for path in paths if str(path).strip()})


def _normalized_symbols(symbols: list[str]) -> list[str]:
    return sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})


def _matching_section_hints(
    sections: list[dict[str, object]], changed_paths: list[str], changed_symbols: list[str]
) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for section in sections:
        paths = set(str(item) for item in section.get("mentioned_paths", []))
        symbols = set(str(item) for item in section.get("mentioned_symbols", []))
        path_evidence = [path for path in changed_paths if path in paths]
        symbol_evidence = [symbol for symbol in changed_symbols if symbol in symbols]
        if path_evidence:
            hints.append({
                "heading_path": list(section.get("heading_path", [])),
                "reason": "references_changed_path",
                "evidence": path_evidence,
            })
        if symbol_evidence:
            hints.append({
                "heading_path": list(section.get("heading_path", [])),
                "reason": "references_changed_symbol",
                "evidence": symbol_evidence,
            })
    return hints


def _recommendation(
    review_required: bool,
    missing: list[dict[str, Any]],
    incomplete_reasons: list[str] | None = None,
    *,
    docs_changed: bool = False,
) -> str:
    if incomplete_reasons:
        return "Analysis is incomplete; narrow the diff or documentation scope before concluding that no update is required."
    if missing:
        return "Create or link the missing module documentation, then review the affected docs before merge."
    if review_required:
        return "Review the listed docs for accuracy; no repository write is performed automatically."
    if docs_changed:
        return "Documentation changes were detected; verify deleted, renamed, or updated docs before merge."
    return "No maintained documentation changes are suggested by this diff."


def evaluate_labeled_section_impact(project_path: str | Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure must-update precision/recall for a deterministic labeled corpus."""
    true_positive = false_positive = false_negative = fallback_cases = 0
    automatic_symbol_cases = 0
    fallback_review_expected = fallback_review_matched = 0
    fallback_review_true_positive = fallback_review_false_positive = fallback_review_false_negative = 0
    for case in cases:
        patch = _labeled_case_patch(case)
        symbols, diagnostics = _symbols_from_patch(patch)
        if symbols:
            automatic_symbol_cases += 1
        if diagnostics.get("symbol_confidence") == "low":
            fallback_cases += 1
        report = analyze_docs_impact(
            project_path,
            [str(case["changed_file"])],
            diff_evidence={"symbols": symbols, "diagnostics": diagnostics},
        )
        predicted = {
            (item["path"], " > ".join(item.get("heading_path") or []))
            for item in report["section_candidates"]["must_update"]
        }
        expected = (
            {(str(case["expected_path"]), str(case["expected_heading"]))}
            if case.get("expected_impact") == "must_update"
            else set()
        )
        if case.get("expected_impact") == "review":
            fallback_review_expected += 1
            reviewed_paths = {item["path"] for item in report["section_candidates"]["review"]}
            expected_reviewed_paths = {str(case["expected_path"])}
            matched = reviewed_paths & expected_reviewed_paths
            if matched:
                fallback_review_matched += 1
            fallback_review_true_positive += len(matched)
            fallback_review_false_positive += len(reviewed_paths - expected_reviewed_paths)
            fallback_review_false_negative += len(expected_reviewed_paths - reviewed_paths)
        true_positive += len(predicted & expected)
        false_positive += len(predicted - expected)
        false_negative += len(expected - predicted)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    fallback_precision = (
        fallback_review_true_positive / (fallback_review_true_positive + fallback_review_false_positive)
        if fallback_review_true_positive + fallback_review_false_positive else 0.0
    )
    fallback_recall = (
        fallback_review_true_positive / (fallback_review_true_positive + fallback_review_false_negative)
        if fallback_review_true_positive + fallback_review_false_negative else 0.0
    )
    return {
        "schema_version": "docs-impact-quality-1",
        "cases": len(cases),
        "must_update_precision": round(precision, 4),
        "must_update_recall": round(recall, 4),
        "minimum_precision": 0.75,
        "minimum_recall": 0.90,
        "passed": (
            precision >= 0.75
            and recall >= 0.90
            and (not fallback_review_expected or fallback_precision >= 0.75)
            and (not fallback_review_expected or fallback_recall >= 0.90)
        ),
        "conservative_fallback_cases": fallback_cases,
        "automatic_symbol_cases": automatic_symbol_cases,
        "fallback_review_expected": fallback_review_expected,
        "fallback_review_matched": fallback_review_matched,
        "fallback_review_precision": round(fallback_precision, 4),
        "fallback_review_recall": round(fallback_recall, 4),
        "counts": {"true_positive": true_positive, "false_positive": false_positive, "false_negative": false_negative},
    }


def _labeled_case_patch(case: dict[str, Any]) -> str:
    path = str(case["changed_file"])
    language = str(case.get("language") or "")
    old = str(case["old_symbol"])
    new = str(case["new_symbol"])
    if language == "python":
        old_line, new_line = f"def {old}():", f"def {new}():"
    elif language == "typescript":
        old_line, new_line = f"export class {old} {{}}", f"export class {new} {{}}"
    elif language == "dart":
        old_line, new_line = f"class {old} {{}}", f"class {new} {{}}"
    else:
        old_line, new_line = f"func {old}() {{}}", f"func {new}() {{}}"
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -1 +1 @@\n"
        f"-{old_line}\n"
        f"+{new_line}\n"
    )
