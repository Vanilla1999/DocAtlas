from __future__ import annotations

import re


_FENCED_CODE_RE = re.compile(r"```[\s\S]*?```")
_INDENTED_CODE_RE = re.compile(r"(?:^\s{4,}\S.*\n?){1,}", re.MULTILINE)
_TABLE_RE = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)
_COMMAND_RE = re.compile(
    r"(^|\n)\s*(?:curl|uv|pip|python|pytest|doc-atlas|dart|flutter|npm|pnpm|yarn|git)\s+\S+",
    re.IGNORECASE,
)
_API_SIGNATURE_RE = re.compile(
    r"\b(?:def|async\s+def|class|from\s+\w+\s+import|import\s+\w+|"
    r"[A-Za-z_]\w*\([^\n)]*\)|@[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?\([^\n)]*\))"
)
_CODE_LINE_RE = re.compile(
    r"(^|\n)\s*(?:from\s+\w+\s+import|import\s+\w+|class\s+\w+|def\s+\w+|async\s+def\s+\w+|"
    r"async\s+with\s+|await\s+|return\s+|final\s+\w+|const\s+\w+|var\s+\w+|"
    r"[\w.]+\s*=\s*[^\n]+|[\w.]+\([^\n)]*\)|@[\w.]+\([^\n)]*\))",
    re.MULTILINE,
)
_NOISE_PATTERNS = [
    r"\bTODO:",
    r"\bFIXME:",
    r"\bHACK:",
    r"type:\s*ignore",
    r"incorrect type specification",
    r"remove when discarding",
    r"deprecated internal parameter",
    r"pragma:",
    r"no cover",
]
_CODE_SYMBOL_RE = re.compile(
    r"(?:"
    r"\b[\w./-]+\.(?:py|dart|ts|tsx|js|jsx|go|rs|java|kt|swift|rb|php|cs|c|cc|cpp|h|hpp)\b|"
    r"\b(?:class|def|async\s+def)\s+[A-Za-z_]\w+|"
    r"\b[A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_]\w+)?\([^\n)]*\)|"
    r"`[^`]*(?:\.(?:py|dart|ts|tsx|js|jsx|go|rs|java|kt|swift|rb|php|cs|c|cc|cpp|h|hpp)\b|class\s+|def\s+|[A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_]\w+)?)[^`]*`"
    r")",
    re.IGNORECASE,
)
_CODE_PATH_RE = re.compile(
    r"\b[\w./-]+\.(?:py|dart|ts|tsx|js|jsx|go|rs|java|kt|swift|rb|php|cs|c|cc|cpp|h|hpp)\b",
    re.IGNORECASE,
)
_IMPLEMENTATION_LOCATION_RE = re.compile(
    r"(?:"
    r"\bwhere\b[^?\n]{0,160}\b(?:implemented|defined|located)\b|"
    r"\b(?:implementation|source|code)\s+(?:file|path|location)\b|"
    r"\b(?:which|what)\s+(?:implementation|source|code)\s+file\b|"
    r"\b(?:implemented|defined)\s+in\b|"
    r"\bгде\b[^?\n]{0,160}\b(?:реализован|реализована|реализовано|определен|определена|находится)\b"
    r")",
    re.IGNORECASE,
)
_RELATION_STOPWORDS = frozenset({
    "a", "an", "and", "are", "code", "defined", "defines", "file", "implemented",
    "implementation", "in", "is", "located", "location", "of", "path", "public",
    "repository", "source", "the", "this", "what", "where", "which",
})


def looks_like_code_or_command(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    if _FENCED_CODE_RE.search(value) or _INDENTED_CODE_RE.search(value):
        return True
    if _COMMAND_RE.search(value) or _API_SIGNATURE_RE.search(value):
        return True
    return bool(_CODE_LINE_RE.search(value))


def is_trivial_section(content: str, title: str | None = None, heading_path: str | None = None) -> bool:
    text = (content or "").strip()
    if not text:
        return True
    combined = "\n".join(part for part in [title or "", heading_path or "", text] if part)
    if _FENCED_CODE_RE.search(text) or _TABLE_RE.search(text) or looks_like_code_or_command(combined):
        return False
    token_estimate = len(re.findall(r"\S+", text))
    return token_estimate < 20


def internal_noise_score(content: str) -> float:
    text = content or ""
    if not text.strip():
        return 0.0
    hits = sum(1 for pattern in _NOISE_PATTERNS if re.search(pattern, text, re.IGNORECASE))
    if not hits:
        return 0.0
    lines = [line for line in text.splitlines() if line.strip()]
    noisy_lines = sum(
        1
        for line in lines
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in _NOISE_PATTERNS)
    )
    density = noisy_lines / max(1, len(lines))
    return min(1.0, 0.35 * hits + density)


def has_code_symbol_evidence(content: str, title: str | None = None, heading_path: str | None = None, path: str | None = None) -> bool:
    text = "\n".join(part for part in [path or "", title or "", heading_path or "", content or ""] if part)
    return bool(_CODE_SYMBOL_RE.search(text))


def query_requests_implementation_location(question: str) -> bool:
    """Return whether the question asks for a code/source location relation."""

    return bool(_IMPLEMENTATION_LOCATION_RE.search(str(question or "")))


def _implementation_subject_terms(question: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        token.casefold()
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", str(question or ""))
        if len(token) >= 3 and token.casefold() not in _RELATION_STOPWORDS
    ))


def has_requested_code_evidence(
    question: str,
    content: str,
    title: str | None = None,
    heading_path: str | None = None,
    path: str | None = None,
) -> bool:
    """Require relation-local source evidence only for implementation-location asks.

    The legacy broad helper remains authoritative for ordinary code-symbol asks.
    Location questions are stricter: a programming-language source path must be
    visible in the evidence text and be locally tied to the requested subject.
    The documentation chunk's own source path is deliberately not enough.
    """

    if not query_requests_implementation_location(question):
        return has_code_symbol_evidence(content, title, heading_path, path)

    visible = "\n".join(part for part in [title or "", heading_path or "", content or ""] if part)
    if not _CODE_PATH_RE.search(visible):
        return False

    subject_terms = _implementation_subject_terms(question)
    if not subject_terms:
        return True
    lines = [line for line in visible.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not _CODE_PATH_RE.search(line):
            continue
        local = " ".join(lines[max(0, index - 1): min(len(lines), index + 2)]).casefold()
        matched = sum(1 for term in subject_terms if re.search(rf"\b{re.escape(term)}\b", local))
        exact_identifier = any("_" in term and term in local for term in subject_terms)
        if exact_identifier or matched >= min(2, len(subject_terms)):
            return True
    return False
