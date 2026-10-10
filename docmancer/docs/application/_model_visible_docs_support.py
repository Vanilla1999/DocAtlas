"""Bounded documentation source rendering and verbatim answer materialization."""
from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from .model_visible_projection_helpers import canonical_projection_bytes


def _docs_candidates(retrieval: dict[str, Any]) -> list[dict[str, Any]]:
    values = [retrieval.get("primary_snippet"), *(retrieval.get("primary_snippets") or []), *(retrieval.get("supporting_snippets") or []), *(retrieval.get("context_pack") or [])]
    return [dict(item) for item in values if isinstance(item, dict)]


def _docs_source(item: dict[str, Any], *, evidence_id: str | None = None,
                 display_snippet: str | None = None) -> dict[str, Any] | None:
    from . import model_visible_projection as public

    path = str(item.get("source_url") or item.get("url") or item.get("path") or item.get("source") or "").strip()
    section = str(item.get("heading_path") or item.get("title") or "document").strip()
    snippet = display_snippet if display_snippet is not None else (
        item.get("code") or item.get("snippet") or item.get("content")
        or item.get("display_text")
    )
    if isinstance(snippet, dict):
        snippet = snippet.get("code") or snippet.get("text") or snippet.get("content")
    snippet = str(snippet or "").strip()
    version = str(item.get("version_binding") or item.get("version") or item.get("requested_version") or "unversioned")
    if (not path or not snippet or len(path) > 500 or len(section) > 300
        or len(version) > 100):
        return None
    digest = public._source_digest(item)
    identity = canonical_projection_bytes({"path": path, "section": section, "sha256": digest})
    return {
        "evidence_id": evidence_id or "ev-" + hashlib.sha256(identity).hexdigest()[:16],
        "path_or_url": path, "section": section, "snippet": snippet,
        "version_binding": version, "content_sha256": digest,
    }


def _source_digest(item: dict[str, Any]) -> str:
    material = {
        "path": item.get("path") or item.get("source") or item.get("url") or item.get("source_url"),
        "section": item.get("heading_path") or item.get("title"),
        "content": item.get("content") or item.get("display_text"),
        "snippet": item.get("snippet") or item.get("code"),
        "version": item.get("version_binding") or item.get("version") or item.get("requested_version"),
    }
    return hashlib.sha256(canonical_projection_bytes(material)).hexdigest()


def _snapshot_entry(original: dict[str, Any], projected: dict[str, Any]) -> dict[str, Any]:
    """Bind raw content and the exact visible row; retain historical flat fields."""
    canonical = dict(projected)
    return {"source": deepcopy(original), "projected_source": canonical, **canonical}


def _answer_text(question: str, retrieval: dict[str, Any], sources: list[dict[str, Any]], *,
                 require_all_sources: bool = False) -> tuple[str, list[str], bool]:
    """Return only text directly present in projected sources."""
    from . import model_visible_projection as public

    explicit = retrieval.get("answer")
    if isinstance(explicit, str) and explicit.strip():
        normalized = " ".join(explicit.split()).casefold()
        refs = [str(source["evidence_id"]) for source in sources
                if normalized and normalized in " ".join(str(source.get("snippet") or "").split()).casefold()]
        required_refs = [str(source["evidence_id"]) for source in sources]
        if refs and (not require_all_sources or refs == required_refs):
            answer = explicit.strip()
            return answer, refs, public._needs_actionable_limitation(question, answer)
    if require_all_sources:
        snippets = [str(source["snippet"]).strip() for source in sources]
        answer = "\n\n".join(dict.fromkeys(snippet for snippet in snippets if snippet))
        refs = [str(source["evidence_id"]) for source in sources]
        return answer, refs, public._needs_actionable_limitation(question, answer)
    primary = sources[0]
    answer = str(primary["snippet"])
    return answer, [str(primary["evidence_id"])], public._needs_actionable_limitation(question, answer)


def _needs_actionable_limitation(question: str, answer: str) -> bool:
    # Source quotation is not proof of actionability; no prose exemption.
    return True
