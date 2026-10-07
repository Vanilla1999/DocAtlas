"""Implementation shard 1 for patch_plan_context."""
from __future__ import annotations

from ._patch_plan_context_shared import *  # noqa: F401,F403
import hashlib
import time
from docmancer.docs.domain.source_boundary import SourceBoundary, finite_local_path, iter_bounded_source_files

# Do not expose the shared, independently scanning package resolver through
# this allocated module. Dependency membership has no contract here.
del resolve_dart_package_roots

def build_implementation_map(
    question: str,
    *,
    project_path: str | None,
    relevant_files: list[dict[str, Any]],
    existing_apis: list[dict[str, Any]],
    missing_symbols: list[dict[str, Any]],
    design_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(project_path).expanduser().resolve() if project_path else None
    selected = []
    if root is not None:
        for item in relevant_files[:5]:
            path = item.get("file")
            if isinstance(path, str):
                candidate = _changed_file_candidate(root, path)
                if candidate is not None:
                    selected.append(candidate)
    current_behavior = _current_behavior_from_files(selected)
    return {
        "current_behavior": current_behavior,
        "minimal_patch_path": [],
        "risks_and_constraints": [],
        "verification": [],
        "warnings": ["Local behavior/policy unresolved; finite read membership does not authorize edits or prove symbol absence."],
        "next_actions": [],
    }


def _current_behavior_from_files(relevant_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    behavior: list[dict[str, Any]] = []
    for item in relevant_files[:5]:
        refs = item.get("refs") or []
        ref = refs[0] if refs else {}
        behavior.append({
            "behavior": "Selected local source context; behavior remains unresolved.",
            "file": item["file"],
            "start_line": ref.get("start_line"),
            "end_line": ref.get("end_line"),
            "symbol": ref.get("symbol"),
            "evidence": ref.get("locate_by_pattern") or item.get("why") or "locate_by_pattern unavailable; read the listed file.",
            "confidence": "unknown",
            "content_hash": item.get("content_hash"),
        })
    return behavior


def _minimal_patch_path(question: str, project_path: str | None, relevant_files: list[dict[str, Any]], *, design_context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    # A caller-supplied source list is not a mutation intent/grant contract.
    return []


def _find_patterns_for_plan(project_path: str | None, relevant_files: list[dict[str, Any]]) -> list[str]:
    patterns: list[str] = []
    root = Path(project_path).expanduser().resolve() if project_path else None
    if root is not None:
        for item in relevant_files[:4]:
            if not isinstance(item.get("file"), str):
                continue
            candidate = _changed_file_candidate(root, item["file"])
            if candidate is not None:
                for ref in candidate["refs"]:
                    _append_unique(patterns, ref["locate_by_pattern"])
    return patterns[:8]


def _risks_and_constraints(question: str, missing_symbols: list[dict[str, Any]], existing_apis: list[dict[str, Any]], design_context: dict[str, Any] | None = None) -> list[dict[str, str]]:
    risks = [
        _risk("generated files must not be edited", "high", "code", "Edit only source files listed in relevant_files; keep generated outputs read-only."),
        _risk("unrelated modules should not be touched", "medium", "code", "Limit changes to the minimal_patch_path files unless new evidence is found."),
        _risk("missing APIs must not be invented", "high", "code", "Use existing_apis or framework APIs with fresh source evidence."),
    ]
    if existing_apis:
        risks.append(_risk("dependency APIs must be evidence-backed", "medium", "dependency", "Use only dependency APIs with file and line evidence in existing_apis."))
    if missing_symbols:
        risks.append(_risk("partial plan only: resolve or replace missing requested symbols before implementing", "medium", "code", "Choose a nearest_alternative or confirm a real API before editing."))
    if design_context:
        risks.append(_risk("design_context is caller-normalized and not parsed from source design files", "low", "design", "Confirm the design artifact manually if visual fidelity matters."))
    return risks


def _risk(risk: str, severity: str, source: str, mitigation: str) -> dict[str, str]:
    return {"risk": risk, "severity": severity, "source": source, "mitigation": mitigation}


def _implementation_warnings(
    project_path: str | None,
    relevant_files: list[dict[str, Any]],
    existing_apis: list[dict[str, Any]],
    missing_symbols: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    if project_path and not relevant_files:
        warnings.append("No selected local source context is available; source membership/behavior remains unresolved.")
    if missing_symbols:
        warnings.append("Requested symbol absence is not certified; caller hints remain unresolved.")
    if existing_apis and any(item.get("kind") == "dependency" for item in existing_apis):
        warnings.append("Dependency API suggestions are limited to resolved local Dart package source evidence.")
    return warnings


def _next_actions(
    relevant_files: list[dict[str, Any]],
    existing_apis: list[dict[str, Any]],
    missing_symbols: list[dict[str, Any]],
) -> list[str]:
    actions: list[str] = []
    if relevant_files:
        actions.append("Open the listed relevant_files and confirm the target symbols/patterns before editing.")
    if existing_apis:
        actions.append("Use only existing_apis entries with file/line evidence when replacing missing APIs.")
    if missing_symbols:
        actions.append("Treat missing_symbols as blockers for direct API calls unless a listed nearest_alternative is selected.")
    return actions


def discover_dart_dependency_apis(
    question: str,
    *,
    project_path: str | None,
    symbol_queries: list[str] | None,
    include_dependency_source: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not include_dependency_source:
        return [], []
    return [], ["Dependency source membership unresolved; no package metadata or imported source read performed."]


def discover_rejected_sources(question: str, *, project_path: str | None, symbol_queries: list[str] | None = None) -> list[dict[str, Any]]:
    # No name-family/topic scan or inferred rejection certificate.
    return []


def _dedupe_dependency_apis(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    for item in items:
        symbol = str(item.get("symbol") or "")
        if symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)
        deduped.append(item)
    return deduped


def discover_missing_symbols(
    question: str,
    *,
    project_path: str | None,
    symbol_queries: list[str] | None,
    searched_dependency: bool = False,
    dependency_apis: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    # A finite/local no-scan result is unknown, never complete symbol absence.
    return []


def _resolved_dart_package_roots(project_root: Path) -> tuple[list[Path], list[str]]:
    return [], ["Dependency source membership unresolved; package metadata was not read."]


def _pubspec_lock_packages(project_root: Path) -> set[str]:
    # Compatibility empty result means unresolved, not no dependencies.
    return set()


def _iter_source_files(root: Path) -> Iterator[Path]:
    root = root.expanduser().resolve()
    yield from iter_bounded_source_files(root, boundary=SourceBoundary.from_project(root),
                                        supported_extensions=frozenset(_SOURCE_SUFFIXES))


def _iter_dependency_source_files(root: Path) -> Iterator[Path]:
    # A package directory is not a finite dependency member declaration.
    yield from ()


def _ordered_terms(question: str, symbol_queries: list[str]) -> list[str]:
    terms: list[str] = []
    for raw in [*symbol_queries, *_WORD_RE.findall(question)]:
        if len(raw) < 3:
            continue
        if "_" not in raw and "." not in raw and not any(char.isupper() for char in raw[1:]):
            continue
        if raw not in terms:
            terms.append(raw)
    return terms


def _probable_symbol_terms(question: str, symbol_queries: list[str]) -> list[str]:
    symbols: list[str] = []
    for raw in [*symbol_queries, *_WORD_RE.findall(question)]:
        raw = raw.strip(".,:;!?()[]{}")
        if not _looks_like_symbol(raw):
            continue
        if raw not in symbols:
            symbols.append(raw)
    return symbols


def _looks_like_symbol(value: str) -> bool:
    if len(value) < 3:
        return False
    lowered = value.lower()
    if lowered.endswith(('.pen', '.fig')):
        return False
    return "." in value or any(char.isupper() for char in value[1:])


def _symbol_found_in_source(symbol: str, source_texts: list[str]) -> bool:
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])")
    return any(pattern.search(text) for text in source_texts)


def _find_dependency_symbol(symbol: str, path: Path, text: str) -> dict[str, Any] | None:
    # Caller text/path is not a finite dependency-source binding. Do not probe
    # that path or manufacture a source-backed API witness from supplied prose.
    return None


def _nearest_dependency_alternatives(symbol: str, dependency_apis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    symbol_tokens = _symbol_tokens(symbol)
    alternatives: list[dict[str, Any]] = []
    for api in dependency_apis:
        api_symbol = str(api.get("symbol") or "")
        api_tokens = _symbol_tokens(api_symbol)
        if not symbol_tokens or not api_tokens:
            continue
        if symbol_tokens & api_tokens:
            alternatives.append({
                "symbol": api_symbol,
                "file": api.get("file"),
                "start_line": api.get("start_line"),
                "end_line": api.get("end_line"),
                "reason": "Similar resolved dependency API found.",
            })
        if len(alternatives) >= 3:
            break
    return alternatives


def _nearest_symbol_alternatives(symbol: str, discovered_symbols: set[str]) -> list[dict[str, Any]]:
    symbol_tokens = _symbol_tokens(symbol)
    alternatives: list[dict[str, Any]] = []
    for candidate in sorted(discovered_symbols):
        candidate_tokens = _symbol_tokens(candidate)
        if not symbol_tokens or not candidate_tokens:
            continue
        if symbol.lower() in candidate.lower() or candidate.lower() in symbol.lower() or symbol_tokens & candidate_tokens:
            alternatives.append({
                "symbol": candidate,
                "file": None,
                "start_line": None,
                "end_line": None,
                "reason": "Similar symbol name found in project source",
            })
        if len(alternatives) >= 3:
            break
    return alternatives


def _symbol_tokens(symbol: str) -> set[str]:
    snake = _to_snake_case(symbol.replace(".", "_"))
    return {part for part in snake.split("_") if len(part) >= 3}


def _term_variants(term: str) -> set[str]:
    snake = _to_snake_case(term)
    pascal = _to_pascal_case(term)
    return {term, snake, pascal, snake.replace("_", "")}


def _to_snake_case(value: str) -> str:
    value = value.replace("-", "_").replace(".", "_")
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return value.lower()


def _to_pascal_case(value: str) -> str:
    if "_" not in value and any(char.isupper() for char in value):
        return value[:1].upper() + value[1:]
    return "".join(part.capitalize() for part in value.replace("-", "_").split("_") if part)


def _should_skip_source(path: Path, root: Path) -> bool:
    if _has_skipped_part(path, root, _SKIPPED_PATH_PARTS):
        return True
    name = path.name
    if name.endswith(_SKIPPED_SUFFIXES):
        return True
    return path.suffix not in _SOURCE_SUFFIXES


def _should_skip_dependency_source(path: Path, root: Path) -> bool:
    if _has_skipped_part(path, root, _DEP_SKIPPED_PATH_PARTS):
        return True
    name = path.name
    if name.endswith(_SKIPPED_SUFFIXES):
        return True
    return path.suffix not in _DART_SOURCE_SUFFIXES


def _has_skipped_part(path: Path, root: Path, skipped_parts: set[str]) -> bool:
    rel = path.relative_to(root)
    return bool(set(rel.parts) & skipped_parts)


def _read_text(path: Path, *, root: Path | None = None) -> str | None:
    # A bare filename has no project-bound membership contract. Do not guess
    # its repository by walking ancestors, reading Git/package metadata, etc.
    if root is None:
        return None
    started = time.monotonic()
    root = root.expanduser().resolve()
    boundary = SourceBoundary.from_project(root)
    if not boundary.enabled or not boundary.code_files or len(boundary.code_files) > boundary.max_scanned_files:
        return None
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return None
    if relative not in boundary.code_files:
        return None
    selected = finite_local_path(root, relative, boundary=boundary,
                                 supported_extensions=frozenset(_SOURCE_SUFFIXES))
    if selected is None or time.monotonic() - started >= boundary.scan_deadline_seconds:
        return None
    try:
        with selected.open("rb") as handle:
            raw = handle.read(min(boundary.max_file_bytes, boundary.max_scanned_bytes) + 1)
        if len(raw) > min(boundary.max_file_bytes, boundary.max_scanned_bytes):
            return None
        if time.monotonic() - started >= boundary.scan_deadline_seconds:
            return None
        return raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _score_source_file(
    rel_path: str,
    text: str,
    ordered_terms: list[str],
    variants_by_term: dict[str, set[str]],
) -> dict[str, Any] | None:
    basename = Path(rel_path).stem
    basename_no_ext = basename.removesuffix(".g").removesuffix(".freezed")
    lowered_text = text.lower()
    lines = text.splitlines()
    definitions = _symbol_definitions(lines)
    imports = _import_export_matches(lines)

    score = 0
    first_term_index = len(ordered_terms)
    why_terms: list[str] = []
    symbols: list[str] = []
    refs: list[dict[str, Any]] = []

    for index, term in enumerate(ordered_terms):
        variants = variants_by_term[term]
        snake = _to_snake_case(term)
        pascal = _to_pascal_case(term)
        matched = False

        if snake == basename_no_ext or pascal.lower() == basename_no_ext.replace("_", ""):
            score += 100
            matched = True
            why_terms.append(f"Exact file basename match: {snake} / {pascal}")

        for symbol, line_no in definitions.items():
            if symbol in variants:
                score += 80
                matched = True
                _append_unique(symbols, symbol)
                refs.append(_ref_for_line(lines, line_no, symbol=symbol, pattern=f"class {symbol}" if _line_contains_class(lines[line_no - 1], symbol) else symbol))
                why_terms.append(f"Exact symbol definition match: {symbol}")

        for import_text, line_no in imports:
            if any(variant.lower() in import_text.lower() for variant in variants):
                score += 50
                matched = True
                refs.append(_ref_for_line(lines, line_no, symbol=None, pattern=import_text.strip()))
                why_terms.append(f"Exact import/export match: {term}")

        for variant in variants:
            if variant and variant.lower() in lowered_text:
                score += 20
                matched = True
                line_no = _first_line_containing(lines, variant)
                if line_no is not None and not any(ref["start_line"] <= line_no <= ref["end_line"] for ref in refs):
                    refs.append(_ref_for_line(lines, line_no, symbol=pascal if variant == pascal else None, pattern=variant))
                why_terms.append(f"Exact usage match: {variant}")
                break

        if matched:
            first_term_index = min(first_term_index, index)
            _append_unique(symbols, pascal)

    if score <= 0:
        return None
    return {
        "file": rel_path,
        "why": "; ".join(_dedupe(why_terms)[:3]),
        "action": "read",
        "symbols": symbols,
        "refs": refs[:3],
        "_score": score,
        "_first_term_index": first_term_index,
    }


def _symbol_definitions(lines: list[str]) -> dict[str, int]:
    definitions: dict[str, int] = {}
    for line_no, line in enumerate(lines, start=1):
        match = _SYMBOL_DEF_RE.search(line)
        if match:
            definitions.setdefault(match.group(1), line_no)
    return definitions


def _import_export_matches(lines: list[str]) -> list[tuple[str, int]]:
    matches: list[tuple[str, int]] = []
    for line_no, line in enumerate(lines, start=1):
        if _IMPORT_EXPORT_RE.search(line):
            matches.append((line, line_no))
    return matches


def _line_contains_class(line: str, symbol: str) -> bool:
    return bool(re.search(rf"\bclass\s+{re.escape(symbol)}\b", line))


def _first_line_containing(lines: list[str], needle: str) -> int | None:
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(needle)}(?![A-Za-z0-9_])")
    for line_no, line in enumerate(lines, start=1):
        if pattern.search(line):
            return line_no
    return None


def _first_line_matching(lines: list[str], pattern: str) -> int | None:
    compiled = re.compile(pattern)
    for line_no, line in enumerate(lines, start=1):
        if compiled.search(line):
            return line_no
    return None


def _ref_for_line(lines: list[str], line_no: int, *, symbol: str | None, pattern: str) -> dict[str, Any]:
    start = max(1, line_no - 2)
    end = min(len(lines), line_no + 4)
    return {
        "start_line": start,
        "end_line": end,
        "symbol": symbol,
        "locate_by_pattern": pattern,
    }


def _changed_file_candidate(root: Path, changed_file: str) -> dict[str, Any] | None:
    from docmancer.docs.project_docs_catalog import _literal_path
    if not isinstance(changed_file, str) or not _literal_path(changed_file):
        return None
    root = root.expanduser().resolve()
    path = root / changed_file
    text = _read_text(path, root=root)
    if text is None:
        return None
    rel_path = path.relative_to(root).as_posix()
    lines = text.splitlines()
    definitions = _symbol_definitions(lines)
    refs = [_ref_for_line(lines, line_no, symbol=symbol, pattern=symbol) for symbol, line_no in list(definitions.items())[:2]]
    return {
        "file": rel_path,
        "why": "Explicit selected source read context; behavior and edit authority unresolved.",
        "action": "read",
        "content_hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "symbols": list(definitions.keys())[:5],
        "refs": refs,
        "_score": 1_000,
        "_first_term_index": -1,
    }


def _merge_duplicate_source_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in candidates:
        current = merged.get(item["file"])
        if current is None:
            merged[item["file"]] = dict(item)
            continue
        if item["_score"] > current["_score"] or item["action"] == "edit":
            replacement = dict(item)
            if current.get("refs") and not replacement.get("refs"):
                replacement["refs"] = current["refs"]
            replacement["symbols"] = _dedupe([*(replacement.get("symbols") or []), *(current.get("symbols") or [])])[:8]
            if item["action"] == "edit" and current.get("why"):
                replacement["why"] = f"{item['why']} Also matched query evidence: {current['why']}"
            merged[item["file"]] = replacement
        else:
            current["symbols"] = _dedupe([*(current.get("symbols") or []), *(item.get("symbols") or [])])[:8]
            current["refs"] = [*(current.get("refs") or []), *(item.get("refs") or [])][:3]
    return list(merged.values())


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

__all__=['build_implementation_map', '_current_behavior_from_files', '_minimal_patch_path', '_find_patterns_for_plan', '_risks_and_constraints', '_risk', '_implementation_warnings', '_next_actions', 'discover_dart_dependency_apis', 'discover_rejected_sources', '_dedupe_dependency_apis', 'discover_missing_symbols', '_resolved_dart_package_roots', '_pubspec_lock_packages', '_iter_source_files', '_iter_dependency_source_files', '_ordered_terms', '_probable_symbol_terms', '_looks_like_symbol', '_symbol_found_in_source', '_find_dependency_symbol', '_nearest_dependency_alternatives', '_nearest_symbol_alternatives', '_symbol_tokens', '_term_variants', '_to_snake_case', '_to_pascal_case', '_should_skip_source', '_should_skip_dependency_source', '_has_skipped_part', '_read_text', '_score_source_file', '_symbol_definitions', '_import_export_matches', '_line_contains_class', '_first_line_containing', '_first_line_matching', '_ref_for_line', '_changed_file_candidate', '_merge_duplicate_source_candidates', '_append_unique', '_dedupe']
