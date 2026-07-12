from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from docmancer.docs.project import EXCLUDED_DIR_NAMES

SOURCE_FILE_LANGUAGES = {
    ".py": "python",
    ".dart": "dart",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
}
MAX_SOURCE_FILE_BYTES = 256_000
_DEFAULT_MAX_FILES = 8
_DEFAULT_TOKEN_BUDGET = 900
_DEFAULT_SOURCE_EVIDENCE_MAX_ITEMS = 12
_DEFAULT_SOURCE_EVIDENCE_TOKEN_BUDGET = 700

_IMPORT_RE = re.compile(r"^\s*import\s+(?:[^'\"]+\s+from\s+)?['\"]([^'\"]+)['\"]|^\s*export\s+(?:[^'\"]+\s+from\s+)?['\"]([^'\"]+)['\"]", re.MULTILINE)
_GENERIC_SYMBOL_RE = re.compile(
    r"\b(?P<class_kind>class|interface|enum|mixin|extension|struct|trait)\s+(?P<class_name>[A-Za-z_][A-Za-z0-9_]*)"
    r"|\bfunction\s+(?P<function_name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
    r"|^\s*(?:async\s+)?(?:static\s+)?(?:[A-Za-z_][A-Za-z0-9_<>,?\[\]]+\s+)+(?P<method_name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_STRING_RE = re.compile(r"(['\"])((?:\\.|(?!\1).){2,120})\1")
_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_\-]{2,}")
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")
_STATUS_TOKEN_RE = re.compile(r"\b(?:active|inactive|closed|open|pending|success|error|failed|done|reopen|status|created|updated|deleted)\b", re.IGNORECASE)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|auth[_-]?token|password|passwd|secret|token)(\s*[:=]\s*)(['\"]?)[^'\"\s,;)]+"
)
_GENERATED_MARKERS = (
    ".g.dart",
    ".freezed.dart",
    ".pb.go",
    ".generated.",
    ".gen.",
    "generatedpluginregistrant.",
)
_KEYWORDS = {
    "abstract",
    "async",
    "await",
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "def",
    "else",
    "enum",
    "export",
    "extends",
    "false",
    "final",
    "for",
    "from",
    "function",
    "if",
    "import",
    "interface",
    "new",
    "none",
    "null",
    "return",
    "static",
    "struct",
    "super",
    "switch",
    "this",
    "trait",
    "true",
    "try",
    "var",
    "void",
    "while",
}


def build_project_repo_map(
    project_root: str | Path,
    *,
    question: str = "",
    max_files: int = _DEFAULT_MAX_FILES,
    token_budget: int = _DEFAULT_TOKEN_BUDGET,
) -> list[dict[str, Any]]:
    """Build a deterministic, compact source-file map for project context.

    This is intentionally static and cheap: it favors path/language/import/symbol/string
    facts with line numbers over whole-file content. Later source-evidence stages can use
    this map to decide where concrete snippets are needed.
    """

    return collect_project_source_facts(
        project_root,
        question=question,
        max_files=max_files,
        token_budget=token_budget,
    )


def collect_project_source_facts(
    project_root: str | Path,
    *,
    question: str = "",
    max_files: int = 24,
    token_budget: int = 4000,
    include_unmatched: bool = False,
) -> list[dict[str, Any]]:
    """Collect deterministic source facts for repo_map and future graph layers.

    The returned items intentionally use the same factual shape as
    build_project_repo_map(). This gives downstream callers a stable seam without
    duplicating source traversal or extraction logic.
    """

    root = Path(project_root).expanduser().resolve()
    if max_files <= 0 or token_budget <= 0 or not root.exists() or not root.is_dir():
        return []

    return _select_project_source_facts(
        root,
        question=question,
        max_files=max_files,
        token_budget=token_budget,
        include_unmatched=include_unmatched,
    )


def _select_project_source_facts(
    root: Path,
    *,
    question: str,
    max_files: int,
    token_budget: int,
    include_unmatched: bool = False,
) -> list[dict[str, Any]]:
    query_terms = _query_terms(question)
    candidates: list[dict[str, Any]] = []
    for path in _iter_source_files(root):
        item = _map_source_file(root, path)
        if item is None:
            continue
        item["matched_terms"] = _matched_terms(item, query_terms)
        item["selection_score"] = _selection_score(item, query_terms)
        if item["selection_score"] <= 0 and not include_unmatched:
            continue
        candidates.append(item)

    selected: list[dict[str, Any]] = []
    spent = 0
    for item in sorted(candidates, key=lambda value: (-float(value.get("selection_score") or 0), value["path"])):
        if len(selected) >= max_files:
            break
        estimate = int(item.get("token_estimate") or 1)
        if selected and spent + estimate > token_budget:
            continue
        selected.append(item)
        spent += estimate
    return selected


def build_project_source_evidence(
    project_root: str | Path,
    *,
    question: str = "",
    requirements: list[str] | None = None,
    max_items: int = _DEFAULT_SOURCE_EVIDENCE_MAX_ITEMS,
    token_budget: int = _DEFAULT_SOURCE_EVIDENCE_TOKEN_BUDGET,
) -> list[dict[str, Any]]:
    """Return concrete source snippets and explicit absent facts for requirement terms.

    Positive evidence always includes a source path and line number. Missing terms are
    exposed as absent_in_source facts so callers can report uncertainty without treating
    absence as proof.
    """

    root = Path(project_root).expanduser().resolve()
    if max_items <= 0 or token_budget <= 0 or not root.exists() or not root.is_dir():
        return []

    terms = _source_evidence_terms(question=question, requirements=requirements)
    if not terms:
        return []

    term_keys = {term: _normalize(term) for term in terms}
    matches: list[dict[str, Any]] = []
    match_counts: dict[str, int] = {}
    for path in _iter_source_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        relative = path.relative_to(root).as_posix()
        language = SOURCE_FILE_LANGUAGES[path.suffix.lower()]
        for line_number, line in enumerate(text.splitlines(), start=1):
            normalized_line = _normalize(line)
            if not normalized_line:
                continue
            for term in terms:
                if match_counts.get(term, 0) >= 2:
                    continue
                normalized_term = term_keys.get(term) or ""
                if not normalized_term:
                    continue
                match_type, confidence_score = _find_symbol_match(term, line)
                if match_type is None:
                    continue
                confidence_label = _confidence_for_line(line, match_type)
                matches.append(_source_snippet_evidence_item(
                    path=relative,
                    language=language,
                    line_number=line_number,
                    line=line,
                    term=term,
                    match_type=match_type,
                    confidence=confidence_label,
                    confidence_score=confidence_score,
                ))
                match_counts[term] = match_counts.get(term, 0) + 1

    selected: list[dict[str, Any]] = []
    spent = 0
    term_order = {term: index for index, term in enumerate(terms)}
    for item in sorted(
        matches,
        key=lambda value: (
            term_order.get((value.get("matched_terms") or [""])[0], 999),
            value.get("path") or "",
            int(value.get("line_start") or 0),
        ),
    ):
        if len(selected) >= max_items:
            break
        estimate = int(item.get("token_estimate") or 1)
        if selected and spent + estimate > token_budget:
            continue
        selected.append(item)
        spent += estimate

    for term in terms:
        if match_counts.get(term):
            continue
        if len(selected) >= max_items:
            break
        item = _absent_source_evidence_item(term)
        estimate = int(item.get("token_estimate") or 1)
        if selected and spent + estimate > token_budget:
            continue
        selected.append(item)
        spent += estimate

    return selected


def source_map_diagnostics(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "selected_files": len(items),
        "token_estimate": sum(int(item.get("token_estimate") or 0) for item in items),
        "paths": [item.get("path") for item in items],
    }


def source_facts_diagnostics(items: list[dict[str, Any]]) -> dict[str, Any]:
    languages: list[str] = []
    for item in items:
        language = item.get("language")
        if language:
            _append_unique(languages, str(language))
    return {
        "selected_files": len(items),
        "token_estimate": sum(int(item.get("token_estimate") or 0) for item in items),
        "paths": [item.get("path") for item in items],
        "languages": languages,
        "symbol_count": sum(len(item.get("symbols") or []) for item in items),
        "import_count": sum(len(item.get("imports") or []) for item in items),
        "reference_count": sum(len(item.get("references") or []) for item in items),
    }


def source_evidence_diagnostics(items: list[dict[str, Any]]) -> dict[str, Any]:
    matched_terms: list[str] = []
    absent_terms: list[str] = []
    paths: list[str] = []
    for item in items:
        if item.get("evidence_class") == "source_snippet":
            for term in item.get("matched_terms") or []:
                _append_unique(matched_terms, str(term))
            path = item.get("path")
            if path:
                _append_unique(paths, str(path))
        elif item.get("evidence_class") == "absent_in_source":
            for term in item.get("missing_terms") or []:
                _append_unique(absent_terms, str(term))
    return {
        "selected_items": len(items),
        "matched_terms": matched_terms,
        "absent_terms": absent_terms,
        "paths": paths,
    }


def _source_evidence_terms(*, question: str, requirements: list[str] | None) -> list[str]:
    raw_terms = requirements if requirements is not None else _query_terms(question)
    return _dedupe_normalized_terms(str(term) for term in raw_terms if str(term or "").strip())[:16]


def _source_snippet_evidence_item(
    *,
    path: str,
    language: str,
    line_number: int,
    line: str,
    term: str,
    match_type: str = "exact_substring",
    confidence: str = "high",
    confidence_score: float = 1.0,
) -> dict[str, Any]:
    snippet = _sanitize_source_line(line.strip())
    content = f"{path}:{line_number}: {snippet}"
    title = f"Source evidence: {path}:{line_number}"
    return {
        "source_class": "source_evidence",
        "evidence_class": "source_snippet",
        "match_type": match_type,
        "confidence": confidence,
        "confidence_score": round(confidence_score, 2),
        "matched": True,
        "matched_terms": [term],
        "missing_terms": [],
        "path": path,
        "title": title,
        "language": language,
        "freshness": "current",
        "line_start": line_number,
        "line_end": line_number,
        "snippet": snippet,
        "why_selected": "requirement term matched a concrete project source line",
        "content": content,
        "token_estimate": max(1, len(content) // 4),
        "source": {
            "source_class": "source_evidence",
            "evidence_class": "source_snippet",
            "match_type": match_type,
            "confidence": confidence,
            "path": path,
            "line_start": line_number,
            "line_end": line_number,
            "title": title,
        },
        "section": {"title": title, "heading_path": "source_evidence", "freshness": "current"},
    }


def _absent_source_evidence_item(term: str) -> dict[str, Any]:
    content = "absent_in_source: no concrete project source snippet matched this requirement term"
    return {
        "source_class": "source_evidence",
        "evidence_class": "absent_in_source",
        "match_type": None,
        "confidence": "unknown",
        "matched": False,
        "matched_terms": [],
        "missing_terms": [term],
        "path": None,
        "title": "Source evidence absent",
        "freshness": "current",
        "line_start": None,
        "line_end": None,
        "why_selected": "requirement term was searched in project source; absence is a search result, not proof of nonexistence",
        "content": content,
        "token_estimate": max(1, len(content) // 4),
        "source": {"source_class": "source_evidence", "evidence_class": "absent_in_source", "confidence": "unknown"},
        "section": {"title": "Source evidence absent", "heading_path": "source_evidence", "freshness": "current"},
    }


def _sanitize_source_line(line: str) -> str:
    return _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}{match.group(3)}[REDACTED]", line)


def _dedupe_normalized_terms(terms: Any) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        value = str(term or "").strip()
        key = _normalize(value)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _iter_source_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        parts = relative.parts
        if any(part in EXCLUDED_DIR_NAMES for part in parts):
            continue
        if _is_generated_path(relative.as_posix()):
            continue
        if path.suffix.lower() not in SOURCE_FILE_LANGUAGES:
            continue
        try:
            if path.stat().st_size > MAX_SOURCE_FILE_BYTES:
                continue
        except OSError:
            continue
        paths.append(path)
    return sorted(paths, key=lambda item: item.relative_to(root).as_posix().lower())


def _map_source_file(root: Path, path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    relative = path.relative_to(root).as_posix()
    language = SOURCE_FILE_LANGUAGES[path.suffix.lower()]
    lines = text.splitlines()
    imports = _extract_imports(text, language)
    symbols = _extract_python_symbols(text) if language == "python" else _extract_generic_symbols(text)
    string_literals = _extract_string_literals(text)
    references = _extract_references(text, imports=imports, symbols=symbols)
    status_like_tokens = _extract_status_like_tokens(text, string_literals)
    content = _render_source_map_content(
        path=relative,
        language=language,
        line_count=len(lines),
        imports=imports,
        symbols=symbols,
        string_literals=string_literals,
        status_like_tokens=status_like_tokens,
        references=references,
    )
    token_estimate = max(1, len(content) // 4)
    title = f"Source map: {relative}"
    return {
        "source_class": "repo_map",
        "path": relative,
        "title": title,
        "language": language,
        "freshness": "current",
        "line_start": 1 if lines else 0,
        "line_end": len(lines),
        "line_count": len(lines),
        "char_count": len(text),
        "imports": imports,
        "references": references,
        "symbols": symbols,
        "string_literals": string_literals,
        "status_like_tokens": status_like_tokens,
        "why_selected": "compact static source map selected by deterministic query/path/symbol ranking",
        "content": content,
        "token_estimate": token_estimate,
        "source": {"source_class": "repo_map", "path": relative, "title": title},
        "section": {"title": title, "heading_path": "repo_map", "freshness": "current"},
    }


def _extract_imports(text: str, language: str) -> list[str]:
    if language == "python":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _append_unique(imports, alias.name)
            elif isinstance(node, ast.ImportFrom):
                prefix = "." * int(node.level or 0) + (node.module or "")
                for alias in node.names:
                    name = f"{prefix}.{alias.name}" if prefix else alias.name
                    _append_unique(imports, name.strip("."))
        return imports[:20]

    imports: list[str] = []
    for match in _IMPORT_RE.finditer(text):
        value = match.group(1) or match.group(2)
        if value:
            _append_unique(imports, value)
    return imports[:20]


def _extract_python_symbols(text: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _extract_generic_symbols(text)
    symbols: list[dict[str, Any]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append(_symbol("class", node.name, node.lineno, getattr(node, "end_lineno", node.lineno)))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(_symbol("method", child.name, child.lineno, getattr(child, "end_lineno", child.lineno), parent=node.name))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(_symbol("function", node.name, node.lineno, getattr(node, "end_lineno", node.lineno)))
    return symbols[:40]


def _extract_generic_symbols(text: str) -> list[dict[str, Any]]:
    line_starts = _line_starts(text)
    symbols: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _GENERIC_SYMBOL_RE.finditer(text):
        kind = "class"
        name = match.group("class_name")
        if match.group("function_name"):
            kind = "function"
            name = match.group("function_name")
        elif match.group("method_name"):
            kind = "method"
            name = match.group("method_name")
        if not name or name.casefold() in _KEYWORDS:
            continue
        line = _line_for_offset(line_starts, match.start())
        key = (kind, name, line)
        if key in seen:
            continue
        seen.add(key)
        symbols.append(_symbol(kind, name, line, line))
    return symbols[:40]


def _extract_string_literals(text: str) -> list[str]:
    literals: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "export ", "from ")):
            continue
        for match in _STRING_RE.finditer(line):
            value = match.group(2).strip()
            if not _looks_like_useful_literal(value):
                continue
            _append_unique(literals, value)
            if len(literals) >= 24:
                return literals
    return literals


def _extract_references(text: str, *, imports: list[str], symbols: list[dict[str, Any]]) -> list[str]:
    declared = {str(symbol.get("name") or "") for symbol in symbols}
    references: list[str] = []
    for value in imports:
        tail = value.rstrip("/").replace("\\", "/").split("/")[-1].split(".")[-1]
        if tail:
            _append_unique(references, tail)
    for match in _IDENTIFIER_RE.findall(text):
        if match in declared or match.casefold() in _KEYWORDS:
            continue
        if match.startswith("_"):
            continue
        if match[0].isupper() or "_" in match:
            _append_unique(references, match)
        if len(references) >= 20:
            break
    return references


def _extract_status_like_tokens(text: str, string_literals: list[str]) -> list[str]:
    tokens: list[str] = []
    for literal in string_literals:
        if _STATUS_TOKEN_RE.search(literal) or re.search(r"[А-Яа-яЁё]", literal):
            _append_unique(tokens, literal)
    for match in _STATUS_TOKEN_RE.findall(text):
        _append_unique(tokens, match)
    return tokens[:16]


def _render_source_map_content(
    *,
    path: str,
    language: str,
    line_count: int,
    imports: list[str],
    symbols: list[dict[str, Any]],
    string_literals: list[str],
    status_like_tokens: list[str],
    references: list[str],
) -> str:
    symbol_bits = [f"{item['kind']} {item['name']}:{item['line_start']}" for item in symbols[:12]]
    parts = [f"repo_map {path} ({language}, lines 1-{line_count})"]
    if imports:
        parts.append("imports: " + ", ".join(imports[:8]))
    if symbol_bits:
        parts.append("symbols: " + ", ".join(symbol_bits))
    if references:
        parts.append("references: " + ", ".join(references[:10]))
    if string_literals:
        parts.append("strings: " + ", ".join(f'"{value}"' for value in string_literals[:8]))
    if status_like_tokens:
        parts.append("status_like_tokens: " + ", ".join(status_like_tokens[:8]))
    return "\n".join(parts)


def _matched_terms(item: dict[str, Any], query_terms: list[str]) -> list[str]:
    haystack = _map_search_text(item)
    return [term for term in query_terms if _normalize(term) in haystack]


def _selection_score(item: dict[str, Any], query_terms: list[str]) -> float:
    score = 0.0
    normalized_path = _normalize(str(item.get("path") or ""))
    raw_symbols = " ".join(str(symbol.get("name") or "") for symbol in item.get("symbols") or [])
    symbols = _normalize(raw_symbols)
    split_symbols = _split_identifier(raw_symbols)
    strings = _normalize(" ".join(str(value) for value in item.get("string_literals") or []))
    imports = _normalize(" ".join(str(value) for value in item.get("imports") or []))
    if not query_terms:
        return 0.0
    for term in query_terms:
        normalized = _normalize(term)
        split_term = _split_identifier(term)
        if not normalized:
            continue
        if normalized in normalized_path:
            score += 5.0
        if normalized in symbols or (split_term != normalized and split_term in split_symbols):
            score += 4.0
        if normalized in strings:
            score += 4.0
        if normalized in imports:
            score += 1.0
        if normalized in _map_search_text(item):
            score += 0.5
    return score


_QUERY_STOPWORDS = {
    "and", "are", "for", "from", "how", "the", "this", "that", "where", "with",
    "как", "где", "для", "или", "что", "это", "этой",
}


def _query_terms(question: str) -> list[str]:
    terms: list[str] = []
    for quoted in re.findall(r"[\"'`“”‘’«»„]+([^\"'`“”‘’«»„]{2,120})[\"'`“”‘’«»„]+", question or ""):
        _append_unique(terms, quoted.strip())
    for word in _WORD_RE.findall(question or ""):
        normalized = _normalize(word)
        if len(normalized) < 3 or normalized in _QUERY_STOPWORDS:
            continue
        _append_unique(terms, word)
    return terms[:24]


def _map_search_text(item: dict[str, Any]) -> str:
    symbol_names = " ".join(str(symbol.get("name") or "") for symbol in item.get("symbols") or [])
    parts = [
        item.get("path"),
        item.get("language"),
        item.get("content"),
        " ".join(str(value) for value in item.get("imports") or []),
        " ".join(str(value) for value in item.get("references") or []),
        " ".join(str(value) for value in item.get("string_literals") or []),
        symbol_names,
    ]
    return _normalize("\n".join(str(part) for part in parts if part))


def _symbol(kind: str, name: str, line_start: int, line_end: int, *, parent: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"kind": kind, "name": name, "line_start": line_start, "line_end": line_end}
    if parent:
        result["parent"] = parent
    return result


def _line_starts(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer("\n", text):
        starts.append(match.end())
    return starts


def _line_for_offset(line_starts: list[int], offset: int) -> int:
    low = 0
    high = len(line_starts)
    while low < high:
        mid = (low + high) // 2
        if line_starts[mid] <= offset:
            low = mid + 1
        else:
            high = mid
    return max(1, low)


def _looks_like_useful_literal(value: str) -> bool:
    if not value or len(value) > 120:
        return False
    if value.startswith(("package:", "dart:", "../", "./", "/")):
        return False
    if re.fullmatch(r"[{}()[\],.;:]+", value):
        return False
    return bool(re.search(r"[A-Za-zА-Яа-яЁё0-9]", value))


def _is_generated_path(path: str) -> bool:
    lowered = path.lower()
    return any(marker in lowered for marker in _GENERATED_MARKERS) or "/generated/" in lowered or lowered.startswith("generated/")


_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-zа-яё])(?=[A-ZА-ЯЁ])|(?<=[A-ZА-ЯЁ]{2})(?=[A-ZА-ЯЁ][a-zа-яё])")
_SYMBOL_CLEAN_RE = re.compile(r"^[_\s]+|[_\s]+$")


def _split_identifier(name: str) -> str:
    """Split camelCase/PascalCase/snake_case into space-separated words."""
    cleaned = _SYMBOL_CLEAN_RE.sub("", name.replace("-", " "))
    cleaned = _CAMEL_SPLIT_RE.sub(" ", cleaned)
    return _normalize(cleaned)


def _fuzzy_match(normalized_term: str, normalized_text: str) -> bool:
    """Check if term approximately matches text using token similarity."""
    if normalized_term in normalized_text:
        return True
    term_tokens = normalized_term.split()
    text_tokens = normalized_text.split()
    if len(term_tokens) <= 1:
        return False
    for size in range(len(term_tokens), 1, -1):
        for start in range(len(term_tokens) - size + 1):
            phrase = " ".join(term_tokens[start:start + size])
            if phrase in normalized_text:
                return True
    joined_term = normalized_term.replace(" ", "")
    if joined_term in normalized_text.replace(" ", ""):
        return True
    return False


def _token_overlap_ratio(term_tokens: set[str], text_tokens: set[str]) -> float:
    if not term_tokens:
        return 0.0
    intersection = term_tokens & text_tokens
    return len(intersection) / len(term_tokens)


def _find_symbol_match(term: str, line: str) -> tuple[str | None, float]:
    """Try to match a natural-language query term against a source line.
    Returns (match_type, confidence) where match_type is one of:
    exact_substring, symbol, fuzzy, proximity, string_literal, import, none.
    """
    normalized_term = _normalize(term)
    normalized_line = _normalize(line)
    if not normalized_term or not normalized_line:
        return None, 0.0
    if normalized_term in normalized_line:
        return "exact_substring", 1.0

    split_term = _split_identifier(term)
    split_line = _split_identifier(line)
    term_tokens = set(split_term.split())
    line_tokens = set(split_line.split())

    overlap_ratio = _token_overlap_ratio(term_tokens, line_tokens)

    if overlap_ratio >= 0.75:
        return "symbol", 0.95

    if _fuzzy_match(normalized_term, normalized_line):
        return "fuzzy", 0.7

    if len(term_tokens) > 1:
        overlap = term_tokens & line_tokens
        if len(overlap) >= 2 or (len(overlap) >= 1 and overlap_ratio >= 0.5):
            return "proximity", 0.6

    return None, 0.0


def _is_comment_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("#", "//", "/*", "*", "///", "//!"))


def _is_string_literal_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("'", '"', "f'", 'f"', "r'", 'r"')) and stripped.endswith(("'", '"'))


def _confidence_for_line(line: str, match_type: str | None) -> str:
    if match_type in ("import",):
        return "high"
    if match_type in ("symbol", "exact_substring"):
        if _is_comment_line(line):
            return "medium"
        return "high"
    if match_type == "fuzzy":
        return "medium" if not _is_comment_line(line) else "low"
    if match_type == "proximity":
        return "medium"
    if match_type == "string_literal":
        return "medium"
    return "low"


def _normalize(value: str) -> str:
    normalized = str(value or "").casefold().replace("ё", "е").replace("_", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)
