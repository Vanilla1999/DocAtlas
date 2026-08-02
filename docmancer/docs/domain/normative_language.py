"""Deterministic classification of source-backed normative language."""
from __future__ import annotations

import ast
import codeop
import re
from typing import Literal

NormativeModality = Literal["forbidden", "required"]

_FORBIDDEN_RE = re.compile(
    r"\b(?:must\s+not|may\s+not|cannot|do\s+not|don't|never|forbidden|prohibited)\b",
    re.IGNORECASE,
)
_REQUIRED_RE = re.compile(
    r"\b(?:must|required|requires|shall|invariant|is\s+reserved\s+for|"
    r"only\s+(?:after|before|when|if)|is\s+allowed\s+only)\b",
    re.IGNORECASE,
)
_DEFINITION_RE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+|"
    r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)\s+means\b",
    re.IGNORECASE,
)
_NOT_REQUIRED_RE = re.compile(
    r"\b(?:not|required\s+not\s+to)\s+required\b", re.IGNORECASE
)
_PYTHON_DECLARATION_PREFIX_RE = re.compile(
    r"^\s*(?:(?:async\s+)?def|class|import|from)\b",
)
_PYTHON_DECLARATION_NODES = (
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.FunctionDef,
    ast.Import,
    ast.ImportFrom,
)
_MAX_PYTHON_DECLARATION_LINES = 16
_MAX_PYTHON_DECLARATION_BYTES = 4096


def python_declaration_line_indexes(value: str) -> frozenset[int]:
    """Return lines belonging to bounded, syntactically valid Python declarations."""

    lines = str(value or "").splitlines()
    declaration_lines: set[int] = set()
    line_index = 0
    while line_index < len(lines):
        if not _PYTHON_DECLARATION_PREFIX_RE.match(lines[line_index]):
            line_index += 1
            continue

        statement_lines: list[str] = []
        for end_index in range(
            line_index,
            min(len(lines), line_index + _MAX_PYTHON_DECLARATION_LINES),
        ):
            statement_lines.append(lines[end_index])
            statement = "\n".join(statement_lines)
            if len(statement.encode("utf-8")) > _MAX_PYTHON_DECLARATION_BYTES:
                break
            try:
                compiled = codeop.compile_command(statement, symbol="exec")
            except (OverflowError, SyntaxError, ValueError):
                break
            if compiled is None:
                continue
            try:
                parsed = ast.parse(statement, mode="exec")
            except SyntaxError:
                break
            if len(parsed.body) == 1 and isinstance(parsed.body[0], _PYTHON_DECLARATION_NODES):
                declaration_lines.update(range(line_index, end_index + 1))
                line_index = end_index + 1
            break
        else:
            line_index += 1
            continue
        if line_index <= end_index:
            line_index += 1
    return frozenset(declaration_lines)


def is_python_declaration(value: str) -> bool:
    """Return whether all non-empty input lines form one Python declaration."""

    text = str(value or "")
    non_empty_lines = {
        index for index, line in enumerate(text.splitlines()) if line.strip()
    }
    return bool(non_empty_lines) and non_empty_lines.issubset(
        python_declaration_line_indexes(text)
    )


def classify_normative_modality(value: str) -> NormativeModality | None:
    """Return a bounded domain modality without interpreting or paraphrasing text."""

    text = str(value or "")
    if is_python_declaration(text):
        return None
    if _FORBIDDEN_RE.search(text):
        return "forbidden"
    if (_REQUIRED_RE.search(text) and not _NOT_REQUIRED_RE.search(text)) or _DEFINITION_RE.search(text):
        return "required"
    return None


def has_normative_language(value: str) -> bool:
    return classify_normative_modality(value) is not None
