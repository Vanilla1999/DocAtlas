"""Finite source-native patch navigation; no inferred graph neighbors or scores."""
from __future__ import annotations

import hashlib

from ._patch_plan_context_shared import *  # noqa: F401,F403
from ._patch_plan_context_part01 import _read_text, _symbol_definitions, build_implementation_map


def build_patch_plan_context(
    question: str, *, project_path: str | None = None,
    changed_files: list[str] | None = None, symbol_queries: list[str] | None = None,
    design_context: dict[str, Any] | None = None, include_dependency_source: bool = True,
    max_files: int | None = 12, max_snippets: int | None = 16, max_tokens: int | None = 2400,
) -> dict[str, Any]:
    from docmancer.docs.domain.source_boundary import SourceBoundary
    root = Path(project_path).expanduser().resolve() if project_path else None
    boundary = SourceBoundary.from_project(root) if root is not None else None
    available = boundary is not None and boundary.enabled and bool(boundary.code_files)
    relevant_files = discover_relevant_source_files(
        question, project_path=project_path, changed_files=changed_files,
        symbol_queries=symbol_queries, max_files=max_files or 12, max_snippets=max_snippets or 16,
    ) if available else []
    implementation_map = build_implementation_map(
        question, project_path=project_path if available else None,
        relevant_files=relevant_files, existing_apis=[], missing_symbols=[], design_context=design_context,
    )
    warnings = ([_PATCH_PLAN_LIMITED_WARNING,
                 "Dependency source membership unresolved; no dependency metadata read.",
                 *implementation_map["warnings"]] if available else
                ["No finite code membership; no source/dependency scan performed. Read membership is not edit permission."])
    payload = {
        "schema_version": PATCH_PLAN_CONTEXT_SCHEMA_VERSION, "tool": PATCH_PLAN_CONTEXT_TOOL,
        "status": "partial", "reason_code": None if available else "unresolved_local_code_membership",
        "answer_available": bool(relevant_files),
        "answer_completeness": "partial_navigational" if available else "unresolved",
        "task": {"title": question, "project": project_path},
        "current_behavior": implementation_map["current_behavior"], "relevant_files": relevant_files,
        "existing_apis": [], "missing_symbols": [], "design_context": design_context,
        "minimal_patch_path": [], "risks_and_constraints": [], "verification": [],
        "evidence": [], "rejected_sources": [], "warnings": warnings, "next_actions": [],
        "token_estimate": 0,
    }
    payload["token_estimate"] = _estimate_tokens(payload)
    return _enforce_patch_plan_budget(payload, max_tokens=max_tokens or 2400)


class PatchPlanContextService:
    def __init__(self, service: Any | None = None):
        self.service = service

    def get_patch_plan_context(self, question: str, **kwargs: Any) -> dict[str, Any]:
        return build_patch_plan_context(question, **kwargs)


def discover_relevant_source_files(
    question: str, *, project_path: str | None, changed_files: list[str] | None = None,
    symbol_queries: list[str] | None = None, max_files: int = 12, max_snippets: int = 16,
) -> list[dict[str, Any]]:
    """Literal OR search in declaration order within the existing read boundary.

    Explicit paths select members; words and explicit symbol queries are literal
    search terms, never inferred spelling variants, declarations or edit grants.
    """
    from docmancer.docs.domain.source_boundary import SourceBoundary, iter_bounded_source_files
    root = Path(project_path).expanduser().resolve() if project_path else None
    if root is None or not root.is_dir():
        return []
    terms = tuple(dict.fromkeys(value for value in [*(symbol_queries or []), *_WORD_RE.findall(question)]
                                if isinstance(value, str) and value))
    patterns = [(term, re.compile(rf"(?<!\w){re.escape(term)}(?!\w)")) for term in terms]
    requested_paths = set(changed_files or [])
    boundary = SourceBoundary.from_project(root)
    paths = iter_bounded_source_files(
        root, boundary=boundary,
        supported_extensions=frozenset({".py", ".dart", ".ts", ".tsx", ".js", ".go", ".rs", ".kt", ".java"}),
    )
    selected = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        text = _read_text(path, root=root)
        if text is None:
            continue
        lines = text.splitlines()
        definitions = _symbol_definitions(lines)
        refs = []
        matched_symbols = []
        for line_no, line in enumerate(lines, start=1):
            matches = [term for term, pattern in patterns if pattern.search(line)]
            if not matches:
                continue
            symbols = [symbol for symbol, start in definitions.items() if start == line_no and symbol in matches]
            matched_symbols.extend(symbols)
            refs.append({"start_line": line_no, "end_line": line_no,
                         "symbol": symbols[0] if symbols else None,
                         "locate_by_pattern": matches[0], "text": line})
        path_match = any(pattern.search(relative) for _, pattern in patterns)
        if relative not in requested_paths and not path_match and not refs:
            continue
        if not refs and lines:
            # A literal path selects the whole source, not an inferred symbol.
            refs = [{"start_line": 1, "end_line": len(lines), "symbol": None,
                     "locate_by_pattern": lines[0], "text": text}]
        selected.append({
            "file": relative, "action": "read",
            "why": ("Explicit selected source read context; behavior and edit authority unresolved."
                    if relative in requested_paths else "Literal source/path match; relevance and behavior unresolved."),
            "content_hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "symbols": list(dict.fromkeys(matched_symbols)), "refs": refs,
        })
        if len(selected) >= max(1, max_files):
            break
    return _cap_relevant_file_refs(selected, max_snippets=max_snippets)


def _cap_relevant_file_refs(items: list[dict[str, Any]], *, max_snippets: int) -> list[dict[str, Any]]:
    remaining = max(1, max_snippets)
    capped = []
    for item in items:
        refs = item.get("refs") or []
        take = min(len(refs), remaining)
        capped.append({**item, "refs": refs[:take]})
        remaining -= take
    return capped


def _estimate_tokens(payload: dict[str, Any]) -> int:
    return max(1, len(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")) // 4)


def _enforce_patch_plan_budget(payload: dict[str, Any], *, max_tokens: int) -> dict[str, Any]:
    # Remove whole trailing occurrences in acquisition order, with no field/topic
    # preferences. The fixed envelope may exceed an unrealistically small cap.
    max_bytes = max(800, max_tokens * 4)
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) <= max_bytes:
        return payload
    compact = {**payload, "relevant_files": list(payload.get("relevant_files") or []),
               "current_behavior": list(payload.get("current_behavior") or [])}
    compact["warnings"] = [*(payload.get("warnings") or []),
                           "Patch planning output was compacted to stay within the max_tokens budget; narrow the request for more context."]
    while compact["relevant_files"] and len(json.dumps(compact, ensure_ascii=False).encode("utf-8")) > max_bytes:
        removed = compact["relevant_files"].pop()["file"]
        compact["current_behavior"] = [row for row in compact["current_behavior"] if row.get("file") != removed]
    compact["answer_available"] = bool(compact["relevant_files"])
    compact["token_estimate"] = _estimate_tokens(compact)
    return compact


__all__ = ["build_patch_plan_context", "PatchPlanContextService", "discover_relevant_source_files",
           "_cap_relevant_file_refs", "_estimate_tokens", "_enforce_patch_plan_budget"]
