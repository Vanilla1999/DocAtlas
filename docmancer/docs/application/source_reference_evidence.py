"""Prepare query reference evidence from the allowed immutable SQLite snapshot.

No retrieval, disk scanning, network access, or metadata-issued trust flags.
The complete catalog is loaded once; source bytes/structure are cached per call.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from typing import Any, Mapping

from docmancer.core.structured_chunking import parse_markdown_parents
from docmancer.docs.domain.lifecycle_policy import lifecycle_allows
from docmancer.docs.domain.query_reference_binding import CatalogSource, ScopeKey, resolve_references, normalize_reference_path
from docmancer.docs.project_docs_catalog import SUPPORTED_EXTENSIONS


class SourceReferenceContext:
    def __init__(self, store: Any, *, question: str, queries=(), filters: Mapping[str, Any], lifecycle_intent="current"):
        self.store = store
        self.question = question
        self.plans: dict[str, dict[str, Any]] = {}
        self.sources: dict[str, CatalogSource] = {}
        self.source_file_hashes: dict[str, str] = {}
        self.documents: dict[str, Any] = {}
        self.complete = False
        generation = store.active_generation_id() if hasattr(store, "active_generation_id") else None
        self.scope = ScopeKey(str(filters.get("project_identity") or ""), "", str(generation or ""))
        if generation and hasattr(store, "_connect"):
            with store._connect() as conn:
                rows = conn.execute(
                    "SELECT source, source_identity, content_hash, metadata_json FROM generation_sources "
                    "WHERE generation_id=? AND json_extract(metadata_json, '$.project_path')=?",
                    (generation, str(filters.get("project_path") or "")),
                ).fetchall()
            for row in rows:
                metadata = json.loads(row["metadata_json"] or "{}")
                if (metadata.get("project_identity") or metadata.get("repository_identity")) != self.scope.project_id:
                    continue
                if metadata.get("source_class") != filters.get("source_class") or not lifecycle_allows(metadata, lifecycle_intent):
                    continue
                if any(metadata.get(key) != filters[key] for key in ("doc_scope", "module_path") if key in filters):
                    continue
                path = str(metadata.get("project_doc_path") or metadata.get("source_path") or "")
                if "project_doc_path" in filters and normalize_reference_path(path) != normalize_reference_path(str(filters["project_doc_path"])):
                    continue
                if not path or path.startswith(("/", "\\")) or ".." in path.replace("\\", "/").split("/"):
                    continue
                if metadata.get("risk_flags") or metadata.get("index_freshness") not in (None, "", "synchronized"):
                    continue
                source_key = str(row["source"])
                self.sources[source_key] = CatalogSource(
                    str(row["source_identity"]), self.scope, path, str(row["content_hash"])
                )
                self.source_file_hashes[source_key] = str(
                    metadata.get("project_doc_content_hash") or ""
                )
            self.complete = True
        for text in dict.fromkeys((question, *(getattr(query, "text", "") for query in queries))):
            self.plan(text)

    def plan(self, text: str) -> dict[str, Any]:
        if text not in self.plans:
            self.plans[text] = asdict(resolve_references(text, catalog=tuple(self.sources.values()),
                scope=self.scope, catalog_complete=self.complete, document_suffixes=frozenset(SUPPORTED_EXTENSIONS)))
        return self.plans[text]

    def _document(self, source: str):
        if source not in self.documents:
            value = None
            identity = self.sources.get(source)
            if identity:
                with self.store._connect() as conn:
                    row = conn.execute("SELECT content FROM generation_sources WHERE generation_id=? AND source=?",
                        (self.scope.snapshot_id, source)).fetchone()
                    children = conn.execute(
                        "SELECT stable_chunk_id, json_extract(metadata_json, '$.generation_id') AS embedded_generation "
                        "FROM retrieval_children WHERE generation_id=? AND source=?",
                        (self.scope.snapshot_id, source),
                    ).fetchall()
                if row is not None and hashlib.sha256(row["content"].encode("utf-8")).hexdigest() == identity.content_sha256:
                    content = row["content"]
                    value = content, parse_markdown_parents(content, identity.document_id), {
                        str(child["stable_chunk_id"]): child["embedded_generation"] for child in children}

            self.documents[source] = value
        return self.documents[source]

    def prepare(self, chunks, query_text: str | None = None):
        if query_text is not None:
            self.plan(query_text)
        if not self.complete:
            # Existing lightweight embedders have no source snapshot. Preserve
            # strict body-only fallback; never mint a source or owner witness.
            return list(chunks)
        result = []
        for chunk in chunks:
            metadata = dict(chunk.metadata or {})
            metadata.pop("_reference_evidence", None)
            metadata.update(_reference_root_plan=self.plan(self.question), _reference_plans=self.plans)
            identity = self.sources.get(str(chunk.source))
            document = self._document(str(chunk.source))
            if identity and document:
                content, parents, embedded_generations = document
                span = metadata.get("char_span") or ()
                if len(span) == 2 and all(type(pos) is int for pos in span):
                    start, end = span
                    path = str(metadata.get("project_doc_path") or metadata.get("source_path") or "")
                    project_digest = str(metadata.get("project_doc_content_hash") or "").removeprefix("sha256:")
                    source_digest = str(metadata.get("source_content_hash") or "").removeprefix("sha256:")
                    trusted_file_hash = self.source_file_hashes.get(str(chunk.source), "")
                    trusted_file_digest = trusted_file_hash.removeprefix("sha256:")
                    hash_valid = bool(trusted_file_digest or source_digest)
                    if trusted_file_digest:
                        hash_valid = hash_valid and project_digest == trusted_file_digest
                    if source_digest:
                        hash_valid = hash_valid and source_digest == identity.content_sha256
                    if 0 <= start <= end <= len(content):
                        window = content[start:end]
                        if window != chunk.text:
                            # Some exact-document fallback rows retain a wider boundary span around
                            # an already-trimmed chunk. Rebind only to exact current bytes; never
                            # normalize both sides and then attest different text.
                            offset = window.find(chunk.text)
                            if offset < 0 or window.find(chunk.text, offset + 1) >= 0:
                                continue
                            start += offset
                            end = start + len(chunk.text)
                        valid = (content[start:end] == chunk.text
                            and hash_valid
                            and path.casefold() == identity.canonical_path.casefold()
                            and (metadata.get("generation_id", self.scope.snapshot_id) == self.scope.snapshot_id
                                 or (metadata.get("stable_chunk_id") in embedded_generations
                                     and metadata.get("generation_id") == embedded_generations[metadata["stable_chunk_id"]])))
                        if valid:
                            # Incremental index copies can retain the previous
                            # generation label inside a current child's metadata.
                            # Reconcile only against that actual current child;
                            # arbitrary/replayed generation claims never qualify.
                            # Source identity is not selected by basename/hash.
                            owners = [p for p in parents if p.char_start <= start and end <= p.char_end]
                            owner = owners[0] if len(owners) == 1 else None
                            header = content[owner.char_start:owner.char_end].splitlines(keepends=True)[0] if owner and owner.level else ""
                            line_start = content.count("\n", 0, start) + 1
                            line_end = content.count("\n", 0, end) + (
                                0 if end > start and content[end - 1] == "\n" else 1
                            )
                            metadata.update(project_doc_path=identity.canonical_path, source_path=identity.canonical_path,
                                generation_id=self.scope.snapshot_id, char_span=[start, end],
                                line_span=[line_start, line_end])
                            metadata["_reference_evidence"] = {
                                "schema_version": 1, "source": asdict(identity),
                                "project_doc_content_hash": trusted_file_hash,
                                "char_start": start, "char_end": end,
                                "text": content[start:end], "raw_document": content,
                                "owner": {"text": header, "char_start": owner.char_start,
                                    "char_end": owner.char_start+len(header), "scope_start": owner.char_start,
                                    "scope_end": owner.char_end, "logical_id": owner.logical_id} if owner else None,
                            }
            result.append(chunk.model_copy(update={"metadata": metadata}))
        return result
