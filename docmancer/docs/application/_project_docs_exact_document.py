"""Bounded retrieval of canonical stored sections for an exact document."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.evidence_selection import requirement_probe_query
from docmancer.docs.domain.project_doc_ranking import normalize_doc_path


_EXACT_DOCUMENT_FALLBACK_LIMIT = 12


def _exact_document_index_chunks(
    agent: Any,
    *,
    root: Path,
    evidence_path: str,
    indexed_source: str,
    requirements: Any | None,
) -> list[RetrievedChunk]:
    """Return bounded canonical stored sections for one resolved indexed document.

    This fallback is used only after the normal retrieval lane returned no
    candidates. It reads the active generation's already-indexed display text,
    never reparses the working-tree file, and therefore cannot create a second
    source of truth. Canonical evidence selection still decides support.
    """

    try:
        rows = list(
            agent.store.list_sections_for_source(indexed_source, limit=64)
        )
    except (AttributeError, OSError, RuntimeError):
        return []

    normalized_path = normalize_doc_path(evidence_path)
    probes = tuple(dict.fromkeys(
        probe
        for requirement in requirements or ()
        if getattr(requirement, "mandatory", False)
        and (probe := requirement_probe_query(requirement))
    ))[:8]
    terms = tuple(dict.fromkeys(
        token.casefold()
        for probe in probes
        for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9_.:/=+-]{3,}", probe)
    ))[:24]

    metadata_cache: dict[str, dict[str, Any]] = {}
    candidates: list[RetrievedChunk] = []
    for row in rows:
        source = str(row.get("source") or "")
        if not source:
            continue
        if source not in metadata_cache:
            try:
                metadata_cache[source] = dict(agent.store.source_metadata(source) or {})
            except (AttributeError, OSError, RuntimeError):
                metadata_cache[source] = {}
        source_metadata = metadata_cache[source]
        row_path = normalize_doc_path(
            source_metadata.get("project_doc_path") or row.get("source_path")
        )
        if row_path != normalized_path:
            continue
        indexed_project_path = str(
            source_metadata.get("project_path") or row.get("project_path") or ""
        )
        if indexed_project_path != str(root):
            continue
        source_class = str(
            source_metadata.get("source_class") or row.get("source_class") or ""
        )
        if source_class != "project_file":
            continue
        display_text = str(row.get("display_text") or row.get("text") or "").strip()
        if not display_text:
            continue

        searchable = " ".join((
            str(row.get("title") or ""),
            str(row.get("anchor") or ""),
            str(row.get("text") or ""),
            display_text,
        )).casefold()
        hit_count = sum(term in searchable for term in terms)
        if terms and hit_count == 0:
            continue
        metadata = {**source_metadata}
        metadata.update({
            "project_doc_path": row_path,
            "source_path": row_path,
            "source_class": source_class,
            "project_path": indexed_project_path,
            "project_identity": (
                source_metadata.get("project_identity")
                or row.get("project_identity")
            ),
            "doc_scope": source_metadata.get("doc_scope") or row.get("doc_scope") or "project",
            "module_id": source_metadata.get("module_id") or row.get("module_id"),
            "project_doc_authority": (
                source_metadata.get("project_doc_authority")
                or row.get("authority")
            ),
            "project_doc_lifecycle_status": (
                source_metadata.get("project_doc_lifecycle_status")
                or row.get("lifecycle_status")
                or "active"
            ),
            "title": row.get("title"),
            "anchor": row.get("anchor"),
            "line_start": row.get("line_start"),
            "line_end": row.get("line_end"),
            "token_estimate": int(row.get("token_estimate") or 0),
            "stable_chunk_id": row.get("stable_chunk_id"),
            "parent_logical_id": row.get("parent_logical_id"),
            "exact_path_match": True,
        })
        start, end = row.get("char_start"), row.get("char_end")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end:
            metadata["char_span"] = [start, end]
        candidates.append(RetrievedChunk(
            source=source,
            chunk_index=int(row.get("chunk_index") or 0),
            text=display_text,
            score=float(1000 + hit_count),
            metadata=metadata,
        ))

    candidates.sort(key=lambda item: (-item.score, item.chunk_index, item.source))
    return candidates[:_EXACT_DOCUMENT_FALLBACK_LIMIT]
