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
_GENERATED_MARKERS = (
    ".g.dart",
    ".freezed.dart",
    ".pb.go",
    ".generated.",
    ".gen.",
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

    root = Path(project_root).expanduser().resolve()
    if max_files <= 0 or token_budget <= 0 or not root.exists() or not root.is_dir():
        return []

    query_terms = _query_terms(question)
    candidates: list[dict[str, Any]] = []
    for path in _iter_source_files(root):
        item = _map_source_file(root, path)
        if item is None:
            continue
        item["matched_terms"] = _matched_terms(item, query_terms)
        item["selection_score"] = _selection_score(item, query_terms)
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


def source_map_diagnostics(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "selected_files": len(items),
        "token_estimate": sum(int(item.get("token_estimate") or 0) for item in items),
        "paths": [item.get("path") for item in items],
    }


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
    symbols = _normalize(" ".join(str(symbol.get("name") or "") for symbol in item.get("symbols") or []))
    strings = _normalize(" ".join(str(value) for value in item.get("string_literals") or []))
    imports = _normalize(" ".join(str(value) for value in item.get("imports") or []))
    if not query_terms:
        return 0.0
    for term in query_terms:
        normalized = _normalize(term)
        if not normalized:
            continue
        if normalized in normalized_path:
            score += 5.0
        if normalized in symbols:
            score += 4.0
        if normalized in strings:
            score += 4.0
        if normalized in imports:
            score += 1.0
        if normalized in _map_search_text(item):
            score += 0.5
    return score


def _query_terms(question: str) -> list[str]:
    terms: list[str] = []
    for quoted in re.findall(r"[\"'`“”‘’«»„]+([^\"'`“”‘’«»„]{2,120})[\"'`“”‘’«»„]+", question or ""):
        _append_unique(terms, quoted.strip())
    for word in _WORD_RE.findall(question or ""):
        normalized = _normalize(word)
        if len(normalized) < 3:
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


def _normalize(value: str) -> str:
    normalized = str(value or "").casefold().replace("ё", "е").replace("_", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)
