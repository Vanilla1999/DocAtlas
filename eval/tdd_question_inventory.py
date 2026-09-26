"""Capture-only inventory validation and source checks; no semantic scoring."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

_KEYS = {"id", "question", "scope", "lookup_queries"}
_FORBIDDEN_ROOTS = {"eval", "experiments", "tests", ".git"}


def _validate_case(row: Any) -> None:
    if not isinstance(row, dict) or set(row) != _KEYS:
        raise ValueError("Runtime cases contain only id, question, scope and lookup_queries")
    if not isinstance(row["id"], str) or not re.fullmatch(r"N(?:0[1-9]|[12][0-9]|30)", row["id"]):
        raise ValueError("Invalid case ID")
    question = row["question"]
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("Invalid original question")
    if row["scope"] not in ("all", "project"):
        raise ValueError("Inventory is restricted to all/project scope")
    lookups = row["lookup_queries"]
    if not isinstance(lookups, list) or len(lookups) > 5:
        raise ValueError("At most five fixed lookup queries are allowed")
    if any(not isinstance(q, str) or not q.strip() or len(q) > 500 for q in lookups):
        raise ValueError("Lookup queries must be nonempty bounded strings")
    if len(set(lookups)) != len(lookups):
        raise ValueError("Duplicate lookups")


def validate_cases(cases: Any) -> list[dict[str, Any]]:
    if not isinstance(cases, list) or len(cases) != 30:
        raise ValueError("Exactly 30 original cases are required")
    for row in cases:
        _validate_case(row)
    if [row["id"] for row in cases] != [f"N{i:02d}" for i in range(1, 31)]:
        raise ValueError("Case IDs or order changed")
    return deepcopy(cases)


def load_cases(path: Path, expected_sha256: str) -> list[dict[str, Any]]:
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Frozen inventory digest mismatch")
    return validate_cases(json.loads(raw))


def request_for(case: dict[str, Any], project_path: str, lane: str) -> dict[str, Any]:
    _validate_case(case)
    if lane not in {"direct", "assisted"}:
        raise ValueError("Unknown capture lane")
    if not isinstance(project_path, str) or not project_path.strip():
        raise ValueError("Explicit project path required")
    request = {"question": case["question"], "project_path": project_path, "scope": case["scope"]}
    if lane == "assisted" and case["lookup_queries"]:
        request["lookup_queries"] = list(case["lookup_queries"])
    return request


def inspect_source(source: dict[str, Any], project: Path) -> dict[str, Any]:
    """Verify visible span, not DocAtlas's internal content-hash derivation.

    Evaluation files, URLs, path escapes and outside symlinks are never read.
    This checks emitted sources, not completeness of the internal index.
    """
    result: dict[str, Any] = {"span_verified": False, "runtime_content_hash_verified": None}
    raw_path = source.get("path_or_url")
    if not isinstance(raw_path, str) or not raw_path or "\x00" in raw_path:
        return {**result, "reason": "invalid_path"}
    path = PurePosixPath(raw_path.replace("\\", "/"))
    if (path.is_absolute() or ".." in path.parts or not path.parts
        or ":" in raw_path or path.parts[0] in _FORBIDDEN_ROOTS):
        return {**result, "reason": "outside_requested_corpus"}
    root = Path(project).resolve()
    file = (root / str(path)).resolve()
    if not file.is_relative_to(root):
        return {**result, "reason": "outside_project"}
    try:
        data = file.read_bytes()
        text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, UnicodeError):
        return {**result, "reason": "source_unavailable"}
    result.update(file_sha256=hashlib.sha256(data).hexdigest(), path=str(path))
    start, end = source.get("line_start"), source.get("line_end")
    if start is None or end is None:
        return {**result, "span_verified": None, "reason": "range_not_provided"}
    lines = text.splitlines()
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        return {**result, "reason": "invalid_range"}
    snippet = source.get("snippet")
    region = "\n".join(lines[start - 1:end])
    found = isinstance(snippet, str) and bool(snippet.strip()) and snippet in region
    return {**result, "span_verified": found, "reason": "verified" if found else "span_mismatch"}
