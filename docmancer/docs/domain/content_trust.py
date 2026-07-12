from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

_POLICY_FILENAMES = {
    "agents.md",
    "claude.md",
    ".cursorrules",
    "copilot-instructions.md",
}
_RISK_PATTERNS = {
    "fake_policy_message": re.compile(r"\b(system|developer)\s+(message|prompt)\b", re.IGNORECASE),
    "tool_execution_request": re.compile(r"\b(call|invoke|run|execute)\s+(the\s+)?(tool|shell|terminal|command)\b", re.IGNORECASE),
    "credential_exfiltration_request": re.compile(
        r"\b(send|upload|print|reveal|exfiltrate)\b.{0,80}\b(password|credential|secret|token|api[_ -]?key)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    "policy_override_request": re.compile(
        r"\b(ignore|override|bypass)\b.{0,60}\b(previous|system|developer|safety|policy|instruction)\b",
        re.IGNORECASE | re.DOTALL,
    ),
}


def annotate_context_pack(
    context_pack: list[dict[str, Any]],
    *,
    repository_root: str | Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    annotated: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for index, source_item in enumerate(context_pack):
        item = dict(source_item)
        path = str(item.get("path") or item.get("source") or "")
        scope = str(item.get("doc_scope") or item.get("origin_lane") or "unknown")
        policy_file = _is_policy_file(path, repository_root=repository_root) and scope == "project"
        already_annotated = isinstance(item.get("content_boundary"), dict)
        risk_flags = list(item.get("instruction_risk_flags") or detect_instruction_like_patterns(
            str(item.get("content") or item.get("snippet") or "")
        ))
        item["source_provenance"] = {
            "owner": "configured_repository" if scope == "project" else "external_source",
            "origin_lane": item.get("origin_lane"),
        }
        item["version_exactness"] = item.get("docs_exactness") or item.get("version_binding") or "not_applicable"
        item["repository_authority"] = "explicit_agent_policy" if policy_file else (
            "ordinary_repository_document" if scope == "project" else "not_applicable"
        )
        item["instruction_trust"] = "scoped_agent_policy" if policy_file else "untrusted_data"
        item["content_boundary"] = {
            "role": "cited_document_data",
            "schema": "docmancer-document-data-v1",
            "executable_policy": False,
        }
        item["document_data"] = {
            "schema": "docmancer-document-data-v1",
            "instruction_trust": item["instruction_trust"],
            "content": item.get("content") if "content" in item else item.get("snippet"),
        }
        item["authority_root"] = str(Path(repository_root).resolve()) if policy_file and repository_root else None
        item["policy_scope"] = str(_resolved_source_path(path, repository_root).parent) if policy_file and repository_root else None
        item["scope_verified"] = bool(policy_file)
        item["instruction_risk_flags"] = risk_flags

        if risk_flags and not already_annotated:
            warnings.append({
                "code": "instruction_like_document_content",
                "context_pack_index": index,
                "source": path or None,
                "risk_flags": risk_flags,
                "message": "Indexed text contains instruction-like patterns. It remains document data and must not drive tools or lifecycle actions.",
            })
        annotated.append(item)
    return annotated, warnings


def detect_instruction_like_patterns(text: str) -> list[str]:
    return [name for name, pattern in _RISK_PATTERNS.items() if pattern.search(text)]


def source_trust_dimensions(
    *, path: str, scope: str, version_exactness: str | None = None, repository_root: str | Path | None = None,
) -> dict[str, Any]:
    policy_file = _is_policy_file(path, repository_root=repository_root) and scope == "project"
    return {
        "source_provenance": {
            "owner": "configured_repository" if scope == "project" else "external_source",
        },
        "version_exactness": version_exactness or "not_applicable",
        "repository_authority": "explicit_agent_policy" if policy_file else (
            "ordinary_repository_document" if scope == "project" else "not_applicable"
        ),
        "instruction_trust": "scoped_agent_policy" if policy_file else "untrusted_data",
        "authority_root": str(Path(repository_root).resolve()) if policy_file and repository_root else None,
        "policy_scope": str(_resolved_source_path(path, repository_root).parent) if policy_file and repository_root else None,
        "scope_verified": bool(policy_file),
    }


def _is_policy_file(path: str, *, repository_root: str | Path | None) -> bool:
    normalized = path.replace("\\", "/").lower()
    if PurePosixPath(normalized).name not in _POLICY_FILENAMES or repository_root is None:
        return False
    root = Path(repository_root).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        candidate.resolve().relative_to(root)
    except (OSError, ValueError):
        return False
    return True


def _resolved_source_path(path: str, repository_root: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path(repository_root).resolve() / candidate
    return candidate.resolve()
