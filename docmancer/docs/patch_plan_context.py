from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote, urlparse


PATCH_PLAN_CONTEXT_SCHEMA_VERSION = "patch-plan-context-1"
PATCH_PLAN_CONTEXT_TOOL = "get_patch_plan_context"
_PATCH_PLAN_NOT_IMPLEMENTED_WARNING = "Patch planning source analysis is not implemented yet."
_PATCH_PLAN_LIMITED_WARNING = "Patch planning source discovery is lightweight; dependency analysis is Dart/Flutter package_config only."
_SOURCE_SUFFIXES = {".dart", ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".swift", ".go", ".rs"}
_DART_SOURCE_SUFFIXES = {".dart"}
_SKIPPED_PATH_PARTS = {".dart_tool", ".git", ".gradle", ".idea", ".pub-cache", "fake_pub_cache", "build", "cache", "generated"}
_DEP_SKIPPED_PATH_PARTS = {".dart_tool", ".git", ".gradle", ".idea", "build", "cache", "generated"}
_SKIPPED_SUFFIXES = (".g.dart", ".freezed.dart", ".gr.dart")
_SYMBOL_DEF_RE = re.compile(r"\b(?:class|mixin|enum|extension|typedef|void|Widget|Future<[^>]+>|[A-Z][A-Za-z0-9_<>?]*)\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_IMPORT_EXPORT_RE = re.compile(r"^\s*(?:import|export)\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\.]*")


def build_patch_plan_context(
    question: str,
    *,
    project_path: str | None = None,
    changed_files: list[str] | None = None,
    symbol_queries: list[str] | None = None,
    design_context: dict[str, Any] | None = None,
    include_dependency_source: bool = True,
    max_files: int | None = 12,
    max_snippets: int | None = 16,
    max_tokens: int | None = 2400,
    output_mode: str | None = "compact",
) -> dict[str, Any]:
    """Return patch-planning response shape with lightweight source discovery."""

    mode = output_mode if output_mode in {"compact", "debug", "full"} else "compact"
    relevant_files = discover_relevant_source_files(
        question,
        project_path=project_path,
        changed_files=changed_files,
        symbol_queries=symbol_queries,
        max_files=max_files or 12,
        max_snippets=max_snippets or 16,
    )
    dependency_apis, dependency_warnings = discover_dart_dependency_apis(
        question,
        project_path=project_path,
        symbol_queries=symbol_queries,
        include_dependency_source=include_dependency_source,
    )
    missing_symbols = discover_missing_symbols(
        question,
        project_path=project_path,
        symbol_queries=symbol_queries,
        searched_dependency=bool(dependency_apis),
        dependency_apis=dependency_apis,
    )
    implementation_map = build_implementation_map(
        question,
        project_path=project_path,
        relevant_files=relevant_files,
        existing_apis=dependency_apis,
        missing_symbols=missing_symbols,
        design_context=design_context,
    )
    rejected_sources = discover_rejected_sources(question, project_path=project_path, symbol_queries=symbol_queries)
    warnings = [_PATCH_PLAN_LIMITED_WARNING] if project_path else [_PATCH_PLAN_NOT_IMPLEMENTED_WARNING]
    warnings.extend(dependency_warnings)
    warnings.extend(implementation_map["warnings"])
    payload = {
        "schema_version": PATCH_PLAN_CONTEXT_SCHEMA_VERSION,
        "tool": PATCH_PLAN_CONTEXT_TOOL,
        "status": "partial",
        "reason_code": None,
        "answer_available": bool(relevant_files or dependency_apis or missing_symbols),
        "answer_completeness": "partial_navigational",
        "task": {
            "title": question,
            "project": project_path,
        },
        "current_behavior": implementation_map["current_behavior"],
        "relevant_files": relevant_files,
        "existing_apis": dependency_apis,
        "missing_symbols": missing_symbols,
        "design_context": design_context,
        "minimal_patch_path": implementation_map["minimal_patch_path"],
        "risks_and_constraints": implementation_map["risks_and_constraints"],
        "verification": implementation_map["verification"],
        "evidence": [],
        "rejected_sources": rejected_sources,
        "warnings": warnings,
        "next_actions": implementation_map["next_actions"],
        "token_estimate": 0,
        "output_mode": mode,
    }
    payload["token_estimate"] = _estimate_tokens(payload)
    if mode == "compact":
        payload = _enforce_patch_plan_budget(payload, max_tokens=max_tokens or 2400)
    return payload


class PatchPlanContextService:
    def __init__(self, service: Any | None = None):
        self.service = service

    def get_patch_plan_context(self, question: str, **kwargs: Any) -> dict[str, Any]:
        return build_patch_plan_context(question, **kwargs)


def build_implementation_map(
    question: str,
    *,
    project_path: str | None,
    relevant_files: list[dict[str, Any]],
    existing_apis: list[dict[str, Any]],
    missing_symbols: list[dict[str, Any]],
    design_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current_behavior = _current_behavior_from_files(relevant_files)
    minimal_patch_path = _minimal_patch_path(question, project_path, relevant_files, design_context=design_context)
    risks_and_constraints = _risks_and_constraints(question, missing_symbols, existing_apis, design_context)
    verification = _verification_steps(question, relevant_files, existing_apis)
    warnings = _implementation_warnings(project_path, relevant_files, existing_apis, missing_symbols)
    next_actions = _next_actions(relevant_files, existing_apis, missing_symbols)
    return {
        "current_behavior": current_behavior,
        "minimal_patch_path": minimal_patch_path,
        "risks_and_constraints": risks_and_constraints,
        "verification": verification,
        "warnings": warnings,
        "next_actions": next_actions,
    }


def _current_behavior_from_files(relevant_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    behavior: list[dict[str, Any]] = []
    for item in relevant_files[:5]:
        refs = item.get("refs") or []
        ref = refs[0] if refs else {}
        behavior.append({
            "behavior": item.get("why") or "Relevant source file found by exact project evidence.",
            "file": item["file"],
            "start_line": ref.get("start_line"),
            "end_line": ref.get("end_line"),
            "symbol": ref.get("symbol"),
            "evidence": ref.get("locate_by_pattern") or item.get("why") or "locate_by_pattern unavailable; read the listed file.",
            "confidence": "high" if refs else "medium",
        })
    return behavior


def _minimal_patch_path(question: str, project_path: str | None, relevant_files: list[dict[str, Any]], *, design_context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if not relevant_files:
        return []
    files = [item["file"] for item in relevant_files[:4]]
    find_patterns = _find_patterns_for_plan(project_path, relevant_files)
    patch_level_plan = []
    for item in relevant_files[:3]:
        symbols = item.get("symbols") or []
        patch_level_plan.append({
            "file": item["file"],
            "target_symbol": symbols[0] if symbols else None,
            "operation": _operation_for_question(question),
            "must_preserve": [
                "existing menu actions",
                "capability flags",
                "navigation behavior",
            ],
            "proposed_fragment": None,
            "fragment_status": "omitted_for_safety",
        })
    goal = _goal_for_question(question)
    if design_context:
        artifact = design_context.get("artifact") or "provided design_context"
        goal = f"{goal} Apply normalized design artifact {artifact}."
    return [{
        "step": _step_for_question(question),
        "goal": goal,
        "files": files,
        "find_patterns": find_patterns,
        "change_type": "replace" if _mentions_any(question, {"replace", "bottom", "sheet", "dialog"}) else "modify",
        "patch_level_plan": patch_level_plan,
    }]


def _find_patterns_for_plan(project_path: str | None, relevant_files: list[dict[str, Any]]) -> list[str]:
    patterns: list[str] = []
    for item in relevant_files[:4]:
        for symbol in item.get("symbols") or []:
            _append_unique(patterns, symbol)
        for ref in item.get("refs") or []:
            pattern = ref.get("locate_by_pattern")
            if isinstance(pattern, str):
                _append_unique(patterns, pattern)
    root = Path(project_path).expanduser().resolve() if project_path else None
    if root is not None:
        for item in relevant_files[:4]:
            path = root / item["file"]
            text = _read_text(path) if path.exists() else None
            if text is None:
                continue
            for candidate in ("MenuPageBuilder", "openMenu", "closeMenu", "_showRT40QRDialog", "_showMS300QRDialog"):
                if candidate in text:
                    _append_unique(patterns, candidate)
    return patterns[:8]


def _operation_for_question(question: str) -> str:
    if _mentions_any(question, {"bottom", "sheet", "dialog"}):
        return "Replace open/close inline toggle with call that opens bottom sheet content."
    return "Apply the requested change only at the evidence-backed target symbol."


def _step_for_question(question: str) -> str:
    if _mentions_any(question, {"bottom", "sheet", "dialog"}):
        return "Replace inline menu rendering with bottom sheet opening"
    return "Apply evidence-backed source change"


def _goal_for_question(question: str) -> str:
    if _mentions_any(question, {"bottom", "sheet", "dialog"}):
        return "Move menu presentation from inline row to modal bottom sheet while preserving existing actions."
    return "Make the requested source change using only files and APIs found in this context."


def _risks_and_constraints(question: str, missing_symbols: list[dict[str, Any]], existing_apis: list[dict[str, Any]], design_context: dict[str, Any] | None = None) -> list[dict[str, str]]:
    risks = [
        _risk("generated files must not be edited", "high", "code", "Edit only source files listed in relevant_files; keep generated outputs read-only."),
        _risk("unrelated modules should not be touched", "medium", "code", "Limit changes to the minimal_patch_path files unless new evidence is found."),
        _risk("missing APIs must not be invented", "high", "code", "Use existing_apis or framework APIs with fresh source evidence."),
    ]
    if _mentions_any(question, {"menu", "capability", "bluetooth", "flashlight", "emulator", "needbt", "needflashlight"}):
        risks.extend([
            _risk("capability semantics must be preserved", "high", "code", "Keep existing capability branches and actions while changing presentation."),
            _risk("preserve needFlashLight, needBT, and isEmulator semantics", "high", "code", "Move UI wiring without changing these flag meanings or call sites."),
            _risk("legacy Bluetooth QR helpers _showRT40QRDialog and _showMS300QRDialog should be removal candidates only when backed by file evidence", "medium", "code", "Delete only after confirming the helper definitions/usages in the listed files."),
        ])
    if existing_apis:
        risks.append(_risk("dependency APIs must be evidence-backed", "medium", "dependency", "Use only dependency APIs with file and line evidence in existing_apis."))
    if missing_symbols:
        risks.append(_risk("partial plan only: resolve or replace missing requested symbols before implementing", "medium", "code", "Choose a nearest_alternative or confirm a real API before editing."))
    if design_context:
        risks.append(_risk("design_context is caller-normalized and not parsed from source design files", "low", "design", "Confirm the design artifact manually if visual fidelity matters."))
    return risks


def _risk(risk: str, severity: str, source: str, mitigation: str) -> dict[str, str]:
    return {"risk": risk, "severity": severity, "source": source, "mitigation": mitigation}


def _verification_steps(question: str, relevant_files: list[dict[str, Any]], existing_apis: list[dict[str, Any]]) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    if _is_flutter_like(question, relevant_files, existing_apis):
        steps.append({
            "type": "command",
            "value": "flutter analyze",
            "why": "Static analysis should catch import/type errors after UI refactor.",
        })
    return steps


def _implementation_warnings(
    project_path: str | None,
    relevant_files: list[dict[str, Any]],
    existing_apis: list[dict[str, Any]],
    missing_symbols: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    if project_path and not relevant_files:
        warnings.append("No project source files were found for an evidence-backed patch path.")
    if missing_symbols:
        warnings.append("Some requested symbols were not found; keep status partial and do not invent missing APIs.")
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


def _is_flutter_like(question: str, relevant_files: list[dict[str, Any]], existing_apis: list[dict[str, Any]]) -> bool:
    if _mentions_any(question, {"flutter", "widget", "bottom", "sheet", "menu", "dialog"}):
        return True
    return any(str(item.get("file", "")).endswith(".dart") for item in [*relevant_files, *existing_apis])


def _mentions_any(text: str, needles: set[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def discover_relevant_source_files(
    question: str,
    *,
    project_path: str | None,
    changed_files: list[str] | None = None,
    symbol_queries: list[str] | None = None,
    max_files: int = 12,
    max_snippets: int = 16,
) -> list[dict[str, Any]]:
    root = Path(project_path).expanduser().resolve() if project_path else None
    if root is None or not root.exists() or not root.is_dir():
        return []

    ordered_terms = _ordered_terms(question, symbol_queries or [])
    if not ordered_terms:
        return []
    variants_by_term = {term: _term_variants(term) for term in ordered_terms}

    candidates: list[dict[str, Any]] = []
    for path in _iter_source_files(root):
        rel_path = path.relative_to(root).as_posix()
        text = _read_text(path)
        if text is None:
            continue
        candidate = _score_source_file(rel_path, text, ordered_terms, variants_by_term)
        if candidate is not None:
            candidates.append(candidate)

    for changed_index, changed_file in enumerate(changed_files or []):
        candidate = _changed_file_candidate(root, changed_file)
        if candidate is not None:
            candidate["_changed_file_index"] = changed_index
            candidates.append(candidate)

    candidates = _merge_duplicate_source_candidates(candidates)
    candidates.sort(key=lambda item: (-item["_score"], item.get("_changed_file_index", 10_000), item["_first_term_index"], item["file"]))
    public: list[dict[str, Any]] = []
    seen_files: set[str] = set()
    for item in candidates:
        if item["file"] in seen_files:
            continue
        seen_files.add(item["file"])
        public.append(_public_relevant_file(item))
        if len(public) >= max(1, max_files):
            break
    return _cap_relevant_file_refs(public, max_snippets=max_snippets)


def discover_dart_dependency_apis(
    question: str,
    *,
    project_path: str | None,
    symbol_queries: list[str] | None,
    include_dependency_source: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not include_dependency_source:
        return [], []
    root = Path(project_path).expanduser().resolve() if project_path else None
    if root is None or not root.exists() or not root.is_dir():
        return [], []

    symbols = _probable_symbol_terms(question, symbol_queries or [])
    if not symbols:
        return [], []

    package_roots, warnings = _resolved_dart_package_roots(root)
    if not package_roots:
        if _pubspec_lock_packages(root):
            warnings.append("Dart package metadata found in pubspec.lock, but no dependency source roots were resolved from .dart_tool/package_config.json.")
        return [], warnings

    existing: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for package_root in package_roots:
        for path in _iter_dependency_source_files(package_root):
            text = _read_text(path)
            if text is None:
                continue
            for symbol in symbols:
                found = _find_dependency_symbol(symbol, path, text)
                if found is None:
                    continue
                key = (found["symbol"], found["file"])
                if key in seen:
                    continue
                seen.add(key)
                existing.append(found)
    existing.sort(key=lambda item: (item["symbol"], item["file"]))
    return _dedupe_dependency_apis(existing), warnings


def discover_rejected_sources(question: str, *, project_path: str | None, symbol_queries: list[str] | None = None) -> list[dict[str, Any]]:
    root = Path(project_path).expanduser().resolve() if project_path else None
    if root is None or not root.exists() or not root.is_dir():
        return []
    exact_terms = _ordered_terms(question, symbol_queries or [])
    generic_terms = {term for term in _WORD_RE.findall(question.lower()) if term in {"camera", "dialog", "bottom", "sheet", "plan"}}
    if not generic_terms:
        return []
    rejected: list[dict[str, Any]] = []
    for path in root.rglob("*.md"):
        if not path.is_file() or _has_skipped_part(path, root, _SKIPPED_PATH_PARTS):
            continue
        text = _read_text(path)
        if text is None:
            continue
        lowered = text.lower()
        matched_generic = sorted(term for term in generic_terms if term in lowered)
        if not matched_generic:
            continue
        if any(any(variant.lower() in lowered for variant in _term_variants(term)) for term in exact_terms):
            continue
        rejected.append({
            "file": path.relative_to(root).as_posix(),
            "reason": "Demoted broad docs/source candidate because it matched generic words but none of the exact patch-planning terms.",
            "matched_terms": matched_generic[:5],
            "missing_exact_terms": exact_terms[:8],
        })
        if len(rejected) >= 5:
            break
    return rejected


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
    root = Path(project_path).expanduser().resolve() if project_path else None
    if root is None or not root.exists() or not root.is_dir():
        return []

    source_texts: list[str] = []
    discovered_symbols: set[str] = set()
    for path in _iter_source_files(root):
        text = _read_text(path)
        if text is None:
            continue
        source_texts.append(text)
        discovered_symbols.update(_symbol_definitions(text.splitlines()).keys())

    dependency_symbols = {item["symbol"] for item in dependency_apis or []}
    missing: list[dict[str, Any]] = []
    for symbol in _probable_symbol_terms(question, symbol_queries or []):
        if _symbol_found_in_source(symbol, source_texts) or symbol in dependency_symbols:
            continue
        searched_scopes = ["project", "dependency"] if searched_dependency else ["project"]
        alternatives = _nearest_dependency_alternatives(symbol, dependency_apis or []) or _nearest_symbol_alternatives(symbol, discovered_symbols)
        missing.append({
            "symbol": symbol,
            "searched_scopes": searched_scopes,
            "result": "not_found",
            "nearest_alternatives": alternatives,
            "negative_evidence": "No exact symbol match found in project source.",
        })
    return missing


def _resolved_dart_package_roots(project_root: Path) -> tuple[list[Path], list[str]]:
    config_path = project_root / ".dart_tool/package_config.json"
    warnings: list[str] = []
    if not config_path.exists():
        return [], warnings
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [], [f"Could not read Dart package_config.json: {exc}"]

    roots: list[Path] = []
    seen: set[Path] = set()
    for package in config.get("packages", []):
        root_uri = package.get("rootUri")
        if not isinstance(root_uri, str):
            continue
        package_root = _resolve_package_root_uri(root_uri, config_path.parent)
        if package_root is None or not package_root.exists() or not package_root.is_dir():
            name = package.get("name") or "<unknown>"
            warnings.append(f"Dart package root for {name} was listed but not found: {root_uri}")
            continue
        resolved = package_root.resolve()
        if resolved == project_root.resolve():
            continue
        if resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)
    return roots, warnings


def _resolve_package_root_uri(root_uri: str, config_dir: Path) -> Path | None:
    parsed = urlparse(root_uri)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme:
        return None
    return (config_dir / root_uri).resolve()


def _pubspec_lock_packages(project_root: Path) -> set[str]:
    lock_path = project_root / "pubspec.lock"
    if not lock_path.exists():
        return set()
    text = _read_text(lock_path) or ""
    return {match.group(1) for match in re.finditer(r"^\s{2}([A-Za-z0-9_]+):\s*$", text, re.MULTILINE)}


def _iter_source_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if path.is_file() and not _should_skip_source(path, root):
            yield path


def _iter_dependency_source_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if path.is_file() and not _should_skip_dependency_source(path, root):
            yield path


def _ordered_terms(question: str, symbol_queries: list[str]) -> list[str]:
    terms: list[str] = []
    for raw in [*symbol_queries, *_WORD_RE.findall(question)]:
        if len(raw) < 3:
            continue
        if raw.lower() in {"plan", "change", "changing", "changes", "with", "and", "the", "for", "from", "into"}:
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
    if lowered in {"plan", "use", "using", "change", "changing", "changes", "with", "and", "the", "for", "from", "into", "find", "semantics"}:
        return False
    return "." in value or any(char.isupper() for char in value[1:])


def _symbol_found_in_source(symbol: str, source_texts: list[str]) -> bool:
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])")
    return any(pattern.search(text) for text in source_texts)


def _find_dependency_symbol(symbol: str, path: Path, text: str) -> dict[str, Any] | None:
    lines = text.splitlines()
    if "." in symbol:
        owner, member = symbol.split(".", 1)
        owner_line = _first_line_matching(lines, rf"\bclass\s+{re.escape(owner)}\b") or _first_line_containing(lines, owner)
        member_line = _first_line_matching(lines, rf"\b{re.escape(member)}\s*\(") or _first_line_containing(lines, member)
        if owner_line is None or member_line is None:
            return None
        start_line = max(1, min(owner_line, member_line) - 2)
        end_line = min(len(lines), max(owner_line, member_line) + 4)
    else:
        line_no = _first_line_matching(lines, rf"\b(?:class|mixin|enum|extension|typedef)\s+{re.escape(symbol)}\b") or _first_line_containing(lines, symbol)
        if line_no is None:
            return None
        start_line = max(1, line_no - 2)
        end_line = min(len(lines), line_no + 4)
    return {
        "symbol": symbol,
        "kind": "dependency",
        "file": str(path.resolve()),
        "start_line": start_line,
        "end_line": end_line,
        "usage_example_file": None,
        "usage_example_lines": None,
        "why_relevant": "Requested bottom sheet API found in resolved Dart package source." if "bottom" in _to_snake_case(symbol) else "Requested API found in resolved Dart package source.",
    }


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
                "reason": "Closest resolved dependency API for bottom sheet behavior." if "bottom" in symbol_tokens & api_tokens else "Similar resolved dependency API found.",
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


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
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
    path = (root / changed_file).resolve()
    try:
        rel_path = path.relative_to(root).as_posix()
    except ValueError:
        return None
    if not path.exists() or not path.is_file() or _should_skip_source(path, root):
        return None
    text = _read_text(path)
    if text is None:
        return None
    lines = text.splitlines()
    definitions = _symbol_definitions(lines)
    refs = [_ref_for_line(lines, line_no, symbol=symbol, pattern=symbol) for symbol, line_no in list(definitions.items())[:2]]
    return {
        "file": rel_path,
        "why": "Caller-provided changed file; include as patch-planning evidence even without an exact query-term hit.",
        "action": "edit",
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


def _cap_relevant_file_refs(items: list[dict[str, Any]], *, max_snippets: int) -> list[dict[str, Any]]:
    remaining = max(1, max_snippets)
    capped: list[dict[str, Any]] = []
    for item in items:
        refs = item.get("refs") or []
        take = min(len(refs), max(1, remaining)) if remaining > 0 else 0
        capped_item = dict(item)
        capped_item["refs"] = refs[:take]
        capped.append(capped_item)
        remaining -= take
    return capped


def _estimate_tokens(payload: dict[str, Any]) -> int:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return max(1, len(encoded) // 4)


def _enforce_patch_plan_budget(payload: dict[str, Any], *, max_tokens: int) -> dict[str, Any]:
    max_bytes = max(800, max_tokens * 4)
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) <= max_bytes:
        return payload
    compact = dict(payload)
    for key, limit in (("relevant_files", 8), ("current_behavior", 5), ("existing_apis", 8), ("minimal_patch_path", 3), ("rejected_sources", 3)):
        value = compact.get(key)
        if isinstance(value, list):
            compact[key] = value[:limit]
    warnings = list(compact.get("warnings") or [])
    warnings.append("Patch planning output was compacted to stay within max_tokens budget; retry with output_mode='debug' or higher max_tokens for more context.")
    compact["warnings"] = warnings
    compact["token_estimate"] = _estimate_tokens(compact)
    return compact


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


def _public_relevant_file(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "file": item["file"],
        "why": item["why"],
        "action": item["action"],
        "symbols": item["symbols"],
        "refs": item["refs"],
    }
