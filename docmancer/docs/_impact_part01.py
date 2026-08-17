"""Implementation shard 1 for impact."""
from __future__ import annotations

from ._impact_shared import *  # noqa: F401,F403

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


def unaccepted_worktree_changes(
    project_path: str | Path,
    head: str,
    paths: list[str],
) -> list[str]:
    """Return affected paths whose working-tree bytes are not the accepted head snapshot."""
    if not paths:
        return []
    root = Path(project_path).expanduser().resolve()
    selected = _ordered_unique(paths)[:_MAX_CHANGED_FILES]
    stdout, stderr, returncode, truncated, timed_out = _run_process_bounded(
        ["git", "-C", str(root), "diff", "--name-only", "-z", head, "--", *selected],
        max_stdout_bytes=_MAX_GIT_STATUS_BYTES,
    )
    if timed_out or truncated:
        raise ValueError("Could not verify accepted documentation snapshot within the bounded Git deadline")
    if returncode != 0:
        message = os.fsdecode(stderr).strip() or "git diff failed"
        raise ValueError(f"Could not verify accepted documentation snapshot: {message}")
    dirty = {_safe_git_text(os.fsdecode(value)) for value in stdout.split(b"\0") if value}

    status_stdout, status_stderr, status_returncode, status_truncated, status_timed_out = _run_process_bounded(
        [
            "git", "-C", str(root), "status", "--porcelain=v1", "-z",
            "--untracked-files=all", "--", *selected,
        ],
        max_stdout_bytes=_MAX_GIT_STATUS_BYTES,
    )
    if status_timed_out or status_truncated:
        raise ValueError("Could not verify uncommitted documentation paths within the bounded Git deadline")
    if status_returncode != 0:
        message = os.fsdecode(status_stderr).strip() or "git status failed"
        raise ValueError(f"Could not verify uncommitted documentation paths: {message}")
    if status_stdout:
        # Porcelain rename records are awkward to parse safely and a dirty result
        # is already a stop condition. Return the bounded affected set instead of
        # pretending an individual path was proven clean.
        dirty.update(selected)
    return sorted(dirty)


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
    follow_up_changed = list(allowed_paths)
    follow_up_deleted: list[str] = []
    follow_up_renamed: list[dict[str, str]] = []
    for change in documentation_changes.values():
        change_status = change.get("status")
        if change_status in {"updated", "changed"} and change.get("path"):
            follow_up_changed.append(str(change["path"]))
        elif change_status == "deleted" and change.get("path"):
            follow_up_deleted.append(str(change["path"]))
        elif change_status == "renamed" and change.get("old_path") and change.get("new_path"):
            follow_up_renamed.append({
                "old_path": str(change["old_path"]),
                "new_path": str(change["new_path"]),
            })
    follow_up_changed = list(dict.fromkeys(follow_up_changed))
    follow_up_deleted = list(dict.fromkeys(follow_up_deleted))
    if any(
        len(values) > 64
        for values in (
            changed_paths,
            changed_symbols,
            symbol_evidence,
            facts_to_verify,
            allowed_edits,
            follow_up_changed,
            follow_up_deleted,
            follow_up_renamed,
        )
    ):
        missing_evidence.append({
            "reason_code": "authoring_brief_limit_exceeded",
            "required_action": "narrow the diff so the complete edit and sync handoff fits in one authoring brief",
        })
    status = (
        "needs_evidence" if missing_evidence
        else "ready_for_host_edit" if allowed_edits
        else "docs_already_changed" if documentation_changes
        else "no_documentation_edit_recommended"
    )
    if missing_evidence:
        # A partial analysis is navigation evidence, never an edit allow-list.
        allowed_edits = []
        follow_up_changed = []
        follow_up_deleted = []
        follow_up_renamed = []
    follow_up_args: dict[str, Any] = {
        "action": "sync_project_docs",
        "project_path": str(root),
    }
    if follow_up_changed:
        follow_up_args["changed_paths"] = follow_up_changed
    if follow_up_deleted:
        follow_up_args["deleted_paths"] = follow_up_deleted
    if follow_up_renamed:
        follow_up_args["renamed_paths"] = follow_up_renamed
    has_follow_up = not missing_evidence and len(follow_up_args) > 2
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
            "arguments_patch": follow_up_args,
            "when": "after the user or host agent reviews and saves the documentation patch",
        } if has_follow_up else {},
    }


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

__all__=['changed_files_from_git', 'changed_evidence_from_git', 'unaccepted_worktree_changes', '_parse_name_status_z', '_bounded_git_patch', '_run_process_bounded', '_symbols_from_patch', '_decode_patch_path', '_ordered_unique', '_safe_git_text', '_safe_git_change', '_impact_candidate_priority', '_fallback_doc_candidates', '_continuation_command', '_bounded_text', '_build_documentation_update_brief', '_add_impact', '_add_section_impacts', '_module_path', '_is_project_authority_candidate', '_is_test_path', '_normalized_paths', '_normalized_symbols']
