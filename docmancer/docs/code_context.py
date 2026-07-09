from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from docmancer.docs.domain.source_map import collect_project_source_facts

CODE_CONTEXT_SCHEMA_VERSION = "code-context-1"
CODE_CONTEXT_TOOL = "get_code_context"
_SOURCE_SUFFIXES = {".dart", ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".swift", ".go", ".rs"}
_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]{2,}")
_LOW_SIGNAL_TERMS = {
    "and", "does", "how", "the", "this", "that", "where", "work", "used",
    "как", "где", "для", "или", "что", "это", "работает", "используется",
}


def build_code_context(
    question: str,
    *,
    project_path: str | None,
    changed_files: list[str] | None = None,
    entry_symbols: list[str] | None = None,
    max_hops: int | None = 2,
    max_files: int | None = 12,
    max_snippets: int | None = 20,
    max_lines_per_snippet: int | None = 80,
    output_mode: str | None = "answer",
) -> dict[str, Any]:
    """Build an answer-ready, source-snippet context pack for local project code.

    This is deliberately language-agnostic and heuristic. It reads real source files,
    extracts bounded snippets, and follows name-based references for a small number of
    hops. It does not claim AST/LSP/call-graph precision.
    """

    mode = output_mode if output_mode in {"answer", "compact", "debug", "full"} else "answer"
    max_hops_value = _clamp(max_hops, default=2, minimum=0, maximum=4)
    max_files_value = _clamp(max_files, default=12, minimum=1, maximum=50)
    max_snippets_value = _clamp(max_snippets, default=20, minimum=1, maximum=40)
    max_lines_value = _clamp(max_lines_per_snippet, default=80, minimum=10, maximum=200)
    root = Path(project_path).expanduser().resolve() if project_path else None
    query_terms = _query_terms(question, entry_symbols=entry_symbols, changed_files=changed_files)

    if root is None or not root.exists() or not root.is_dir():
        return _navigation_only_payload(
            question=question,
            project_path=project_path,
            query_terms=query_terms,
            mode=mode,
            reason="project_path is missing or is not a directory",
        )

    facts = collect_project_source_facts(
        root,
        question=" ".join(query_terms),
        max_files=max(max_files_value * 3, max_files_value),
        token_budget=max(4000, max_files_value * 800),
    )
    if changed_files:
        facts = _prioritize_changed_files(facts, changed_files)
    selected_facts = _expand_references(facts, query_terms=query_terms, max_hops=max_hops_value, max_files=max_files_value)
    snippets = _snippets_for_facts(root, selected_facts, query_terms=query_terms, max_snippets=max_snippets_value, max_lines_per_snippet=max_lines_value)

    if not snippets:
        return _navigation_only_payload(
            question=question,
            project_path=str(root),
            query_terms=query_terms,
            mode=mode,
            reason="No concrete source snippets matched the query terms.",
            facts=selected_facts,
        )

    snippet_paths = {snippet["path"] for snippet in snippets}
    source_chain = [_source_chain_item(fact, snippets) for fact in selected_facts if fact.get("path") in snippet_paths]
    references = _reference_items(selected_facts, query_terms=query_terms, selected_paths=snippet_paths)
    unresolved = _unresolved_symbols(selected_facts, query_terms=query_terms)
    payload = {
        "schema_version": CODE_CONTEXT_SCHEMA_VERSION,
        "tool": CODE_CONTEXT_TOOL,
        "status": "success",
        "reason_code": None,
        "question": question,
        "project_path": str(root),
        "answer_available": True,
        "answer_type": "source_context",
        "safe_to_answer": True,
        "agent_instruction": "You may answer from returned source snippets. Use file paths and line ranges. Do not infer behavior not present in snippets; read files_to_read if context is insufficient.",
        "summary": _summary_for_snippets(question, snippets, references),
        "source_chain": source_chain[:max_snippets_value],
        "snippets": snippets,
        "source_snippets": snippets,
        "references": references,
        "unresolved": unresolved,
        "files_to_read": _files_to_read(selected_facts, snippets, limit=max_files_value),
        "search_queries": query_terms[:12],
        "required_next_step": None,
        "output_mode": mode,
    }
    if mode in {"debug", "full"}:
        payload["diagnostics"] = {
            "max_hops": max_hops_value,
            "facts_considered": len(facts),
            "facts_selected": len(selected_facts),
            "query_terms": query_terms,
            "limitations": ["heuristic_symbol_index", "name_based_reference_expansion", "not_lsp_or_call_graph"],
        }
    return payload


def _navigation_only_payload(
    *,
    question: str,
    project_path: str | None,
    query_terms: list[str],
    mode: str,
    reason: str,
    facts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    facts = facts or []
    files_to_read = [
        {
            "path": str(item.get("path")),
            "reason": item.get("why_selected") or "Selected by source-map ranking; read this file before answering.",
            "suggested_symbols": [str(symbol.get("name")) for symbol in item.get("symbols") or [] if symbol.get("name")][:6],
            "line_hints": [line for line in (item.get("line_start"), item.get("line_end")) if isinstance(line, int)],
        }
        for item in facts[:8]
        if item.get("path")
    ]
    return {
        "schema_version": CODE_CONTEXT_SCHEMA_VERSION,
        "tool": CODE_CONTEXT_TOOL,
        "status": "partial",
        "reason_code": "navigation_only",
        "question": question,
        "project_path": project_path,
        "answer_available": False,
        "answer_type": "navigation_only",
        "safe_to_answer": False,
        "agent_instruction": "Do not answer from this response alone. Read/search files_to_read or search_queries first.",
        "summary": reason,
        "source_chain": [],
        "snippets": [],
        "source_snippets": [],
        "unresolved": [],
        "files_to_read": files_to_read,
        "search_queries": query_terms[:12],
        "required_next_step": "read_or_search_suggested_sources",
        "output_mode": mode,
    }


def _query_terms(question: str, *, entry_symbols: list[str] | None, changed_files: list[str] | None) -> list[str]:
    terms: list[str] = []
    for value in entry_symbols or []:
        _append_unique(terms, str(value).strip())
    for path in changed_files or []:
        stem = Path(str(path)).stem
        if len(stem) >= 3:
            _append_unique(terms, stem)
    for quoted in re.findall(r"[\"'`“”‘’«»„]+([^\"'`“”‘’«»„]{2,120})[\"'`“”‘’«»„]+", question or ""):
        _append_unique(terms, quoted.strip())
    for word in _WORD_RE.findall(question or ""):
        normalized = _normalize(word)
        if len(normalized) < 3 or normalized in _LOW_SIGNAL_TERMS:
            continue
        _append_unique(terms, word)
    return terms[:24]


def _prioritize_changed_files(facts: list[dict[str, Any]], changed_files: list[str]) -> list[dict[str, Any]]:
    changed = {_normalize_path(path) for path in changed_files}
    return sorted(facts, key=lambda item: (0 if _normalize_path(str(item.get("path") or "")) in changed else 1, str(item.get("path") or "")))


def _expand_references(
    facts: list[dict[str, Any]],
    *,
    query_terms: list[str],
    max_hops: int,
    max_files: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_paths: set[str] = set()
    frontier = set(_normalized_terms(query_terms))
    if not frontier:
        frontier = {""}

    for hop in range(max_hops + 1):
        matches: list[dict[str, Any]] = []
        for item in facts:
            path = str(item.get("path") or "")
            if not path or path in selected_paths:
                continue
            if _fact_matches_any(item, frontier):
                item = dict(item)
                item["why_selected"] = _why_selected(item, frontier, hop=hop)
                matches.append(item)
        matches.sort(key=lambda item: (-float(item.get("selection_score") or 0), str(item.get("path") or "")))
        for item in matches:
            if len(selected) >= max_files:
                return selected
            selected.append(item)
            selected_paths.add(str(item.get("path")))
        if not matches:
            break
        next_terms = set(frontier)
        for item in matches:
            for symbol in item.get("symbols") or []:
                name = str(symbol.get("name") or "")
                if name:
                    next_terms.add(_normalize_identifier(name))
            for reference in item.get("references") or []:
                next_terms.add(_normalize_identifier(str(reference)))
        if next_terms == frontier:
            break
        frontier = {term for term in next_terms if term}
    return selected[:max_files]


def _fact_matches_any(item: dict[str, Any], normalized_terms: set[str]) -> bool:
    searchable = _normalize_identifier(" ".join([
        str(item.get("path") or ""),
        " ".join(str(symbol.get("name") or "") for symbol in item.get("symbols") or []),
        " ".join(str(value) for value in item.get("references") or []),
        " ".join(str(value) for value in item.get("imports") or []),
        " ".join(str(value) for value in item.get("matched_terms") or []),
    ]))
    return any(term and term in searchable for term in normalized_terms)


def _snippets_for_facts(
    root: Path,
    facts: list[dict[str, Any]],
    *,
    query_terms: list[str],
    max_snippets: int,
    max_lines_per_snippet: int,
) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    normalized_terms = set(_normalized_terms(query_terms))
    for fact in facts:
        path_value = str(fact.get("path") or "")
        path = root / path_value
        if not path.is_file() or path.suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        ranges = _snippet_ranges_for_fact(fact, lines, normalized_terms=normalized_terms, max_lines_per_snippet=max_lines_per_snippet)
        for start_line, end_line, symbol in ranges:
            key = (path_value, start_line, end_line)
            if key in seen:
                continue
            seen.add(key)
            code = "\n".join(lines[start_line - 1:end_line])
            snippets.append({
                "path": path_value,
                "start_line": start_line,
                "end_line": end_line,
                "language": str(fact.get("language") or path.suffix.lstrip(".")),
                "symbol": symbol,
                "code": _sanitize_code(code),
                "why_selected": fact.get("why_selected") or "Selected by source context retrieval.",
            })
            if len(snippets) >= max_snippets:
                return snippets
    return snippets


def _snippet_ranges_for_fact(
    fact: dict[str, Any],
    lines: list[str],
    *,
    normalized_terms: set[str],
    max_lines_per_snippet: int,
) -> list[tuple[int, int, str | None]]:
    ranges: list[tuple[int, int, str | None]] = []
    for symbol in fact.get("symbols") or []:
        name = str(symbol.get("name") or "")
        if normalized_terms and not any(term in _normalize_identifier(name) for term in normalized_terms):
            continue
        start = int(symbol.get("line_start") or 1)
        end = max(int(symbol.get("line_end") or start), _body_end_line(lines, start, max_lines_per_snippet=max_lines_per_snippet))
        ranges.append((start, min(end, start + max_lines_per_snippet - 1, len(lines)), name or None))
    if ranges:
        return ranges[:3]

    for index, line in enumerate(lines, start=1):
        normalized_line = _normalize_identifier(line)
        if any(term and term in normalized_line for term in normalized_terms):
            start = max(1, index - 4)
            end = min(len(lines), index + 12, start + max_lines_per_snippet - 1)
            ranges.append((start, end, None))
            if len(ranges) >= 2:
                break
    if ranges:
        return ranges
    if lines:
        return [(1, min(len(lines), max_lines_per_snippet), None)]
    return []


def _body_end_line(lines: list[str], start_line: int, *, max_lines_per_snippet: int) -> int:
    start_index = max(0, start_line - 1)
    first = lines[start_index] if start_index < len(lines) else ""
    if "{" in first:
        depth = 0
        for index in range(start_index, min(len(lines), start_index + max_lines_per_snippet)):
            depth += lines[index].count("{")
            depth -= lines[index].count("}")
            if index > start_index and depth <= 0:
                return index + 1
    start_indent = len(first) - len(first.lstrip())
    for index in range(start_index + 1, min(len(lines), start_index + max_lines_per_snippet)):
        stripped = lines[index].strip()
        indent = len(lines[index]) - len(lines[index].lstrip())
        if stripped and indent <= start_indent and re.match(r"(?:class|def|function|enum|interface|struct|trait|void|final|const|[A-Z])", stripped):
            return index
    return min(len(lines), start_line + 8)


def _source_chain_item(fact: dict[str, Any], snippets: list[dict[str, Any]]) -> dict[str, Any]:
    path = str(fact.get("path") or "")
    snippet = next((item for item in snippets if item.get("path") == path), {})
    return {
        "path": path,
        "symbol": snippet.get("symbol") or _first_symbol(fact),
        "start_line": snippet.get("start_line") or fact.get("line_start"),
        "end_line": snippet.get("end_line") or fact.get("line_end"),
        "why_selected": snippet.get("why_selected") or fact.get("why_selected") or "Selected by source context retrieval.",
    }


def _reference_items(facts: list[dict[str, Any]], *, query_terms: list[str], selected_paths: set[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    normalized_terms = set(_normalized_terms(query_terms))
    for fact in facts:
        path = str(fact.get("path") or "")
        if path not in selected_paths:
            continue
        for reference in fact.get("references") or []:
            normalized = _normalize_identifier(str(reference))
            if not any(term and (term in normalized or normalized in term) for term in normalized_terms):
                continue
            items.append({"path": path, "symbol": str(reference), "kind": "reference", "confidence": "heuristic"})
    return items[:20]


def _unresolved_symbols(facts: list[dict[str, Any]], *, query_terms: list[str]) -> list[dict[str, str]]:
    defined = {_normalize_identifier(str(symbol.get("name") or "")) for fact in facts for symbol in fact.get("symbols") or []}
    unresolved: list[dict[str, str]] = []
    for term in query_terms:
        normalized = _normalize_identifier(term)
        if not normalized or normalized in defined:
            continue
        if any(normalized in _normalize_identifier(str(ref)) for fact in facts for ref in fact.get("references") or []):
            continue
        unresolved.append({"symbol": term, "reason": "Referenced by query but not found as a definition in selected source files."})
    return unresolved[:12]


def _files_to_read(facts: list[dict[str, Any]], snippets: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    snippet_paths = {str(snippet.get("path") or "") for snippet in snippets}
    files: list[dict[str, Any]] = []
    for fact in facts:
        path = str(fact.get("path") or "")
        if not path:
            continue
        files.append({
            "path": path,
            "reason": fact.get("why_selected") or "Read if returned snippets are insufficient.",
            "suggested_symbols": [str(symbol.get("name")) for symbol in fact.get("symbols") or [] if symbol.get("name")][:6],
            "line_hints": [snippet["start_line"] for snippet in snippets if snippet.get("path") == path][:3],
            "already_snippeted": path in snippet_paths,
        })
    return files[:limit]


def _summary_for_snippets(question: str, snippets: list[dict[str, Any]], references: list[dict[str, Any]]) -> str:
    first_paths = ", ".join(f"{item['path']}:{item['start_line']}-{item['end_line']}" for item in snippets[:3])
    ref_count = len(references)
    return f"Found answer-ready source context for: {question}. Primary snippets: {first_paths}. Reference matches: {ref_count}."


def _why_selected(item: dict[str, Any], frontier: set[str], *, hop: int) -> str:
    symbols = [str(symbol.get("name") or "") for symbol in item.get("symbols") or []]
    references = [str(value) for value in item.get("references") or []]
    for value in [*symbols, *references, str(item.get("path") or "")]:
        normalized = _normalize_identifier(value)
        if any(term and term in normalized for term in frontier):
            if hop == 0:
                return f"Matched query/entry symbol '{value}'."
            return f"Reference expansion hop {hop} matched '{value}'."
    return "Selected by source-map ranking."


def _first_symbol(fact: dict[str, Any]) -> str | None:
    symbols = fact.get("symbols") or []
    if not symbols:
        return None
    return str(symbols[0].get("name") or "") or None


def _normalized_terms(values: Iterable[str]) -> list[str]:
    terms: list[str] = []
    for value in values:
        normalized = _normalize_identifier(str(value))
        if normalized:
            terms.append(normalized)
    return terms


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold().replace("ё", "е").replace("_", " ")).strip()


def _normalize_identifier(value: str) -> str:
    spaced = re.sub(r"(?<=[a-zа-яё0-9])(?=[A-ZА-ЯЁ])", " ", str(value or ""))
    return _normalize(spaced.replace("/", " ").replace(".", " ").replace("-", " "))


def _normalize_path(value: str) -> str:
    return str(value or "").replace("\\", "/").strip("/")


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _clamp(value: int | None, *, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default
    return max(minimum, min(maximum, int(value)))


def _sanitize_code(code: str) -> str:
    return re.sub(r"(?i)\b(api[_-]?key|auth[_-]?token|password|passwd|secret|token)(\s*[:=]\s*)(['\"]?)[^'\"\s,;)]+", r"\1\2\3[REDACTED]", code)
