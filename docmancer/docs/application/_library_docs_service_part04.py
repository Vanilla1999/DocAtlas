"""LibraryDocsApplicationService implementation shard 4."""
from __future__ import annotations

from ._library_docs_service_shared import *  # noqa: F401,F403


class _LibraryDocsApplicationServicePart04:
    def _bounded_library_index_witness(
        self,
        *,
        record: LibraryRecord,
        info: LibraryInfo,
        requirements: Any,
        support_decision: Any,
        retrieval_filters: dict[str, Any],
        allowed_ids: set[str],
        expected_roots: set[str],
        dispatcher_candidate_ids: set[str],
        resolved_version: str | None,
        requested_version: str | None,
        docs_exactness: str | None,
        docs_snapshot_exact: bool | None,
        exact_version_match: bool | None,
    ) -> dict[str, Any]:
        """Prove an omission only from a complete manifest-owned corpus.

        The probe is diagnostic-only and retains no text in public diagnostics.
        It never upgrades a support verdict; it only replaces the insufficiency
        reason after finding a missing requirement outside dispatcher results.
        """

        if support_decision.answer_supported or not support_decision.missing_requirement_ids:
            return {"status": "not_needed"}
        if not self._library_manifest_is_complete(record):
            return {"status": "not_attempted", "reason_code": "corpus_not_proven_complete"}
        probe = self.facade.agent_gateway.probe_library_requirements(
            record,
            requirements,
            missing_requirement_ids=support_decision.missing_requirement_ids,
            filters=retrieval_filters,
        )
        summary: dict[str, Any] = {
            "status": probe.status,
            "queried_requirement_ids": list(probe.queried_requirement_ids),
            "candidate_count": len(probe.chunks),
            "failure_count": probe.failure_count,
        }
        if probe.status != "ok":
            return summary
        candidates: list[dict[str, Any]] = []
        for index, chunk in enumerate(probe.chunks, start=1):
            if self._library_chunk_rejection_reason(chunk, info, allowed_ids, expected_roots):
                continue
            metadata = dict(getattr(chunk, "metadata", None) or {})
            if _drop_low_value_library_section(str(getattr(chunk, "text", "")), metadata.get("title")):
                continue
            content = str(getattr(chunk, "text", ""))
            source = str(getattr(chunk, "source", ""))
            stable_id = str(
                metadata.get("stable_chunk_id")
                or metadata.get("section_id")
                or metadata.get("chunk_id")
                or "library-witness-" + hashlib.sha256(
                    f"{source}\0{metadata.get('title')}\0{content}".encode("utf-8")
                ).hexdigest()[:16]
            )
            candidates.append({
                "title": metadata.get("title"),
                "content": content,
                "source": source,
                "url": source if source.startswith(("http://", "https://")) else None,
                "metadata": {
                    **metadata,
                    "source_class": "library_doc",
                    "doc_scope": "library",
                    "origin_lane": "library_index_witness",
                    "canonical_id": info.library_id,
                    "library_id": info.library_id,
                    "version": resolved_version,
                    "requested_version": requested_version,
                    "docs_exactness": docs_exactness,
                    "exact_version_match": exact_version_match,
                },
                "stable_chunk_id": stable_id,
                "parent_logical_id": str(metadata.get("parent_logical_id") or metadata.get("source_id") or source),
                "display_content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "authority": metadata.get("authority") or "official",
                "docs_exactness": metadata.get("docs_exactness") or docs_exactness,
                "resolved_version": metadata.get("version") or resolved_version,
                "version": metadata.get("version") or resolved_version,
                "docs_snapshot_exact": docs_snapshot_exact,
                "retrieval_rank": index,
            })
        if not candidates:
            summary["status"] = "no_witness"
            return summary
        witness_selection = select_evidence(
            candidates,
            question="",
            config=library_docs_selection_config(DEFAULT_DOC_TOKENS),
            requirements=requirements,
        )
        missing = set(support_decision.missing_requirement_ids)
        witnesses = [
            {
                "evidence_id": candidate.stable_id,
                "covered_requirement_ids": sorted(
                    set(candidate.covered_requirement_ids) & missing
                ),
            }
            for candidate in witness_selection.selected_candidates
            if candidate.stable_id not in dispatcher_candidate_ids
            and set(candidate.covered_requirement_ids) & missing
        ]
        summary["witnesses"] = witnesses
        summary["status"] = "witness_found" if witnesses else "no_witness"
        return summary

    def _library_manifest_is_complete(self, record: LibraryRecord) -> bool:
        manifest = ((record.target_spec or {}).get("source_manifest") or {})
        if manifest.get("schema_version") != 2 or manifest.get("complete") is not True:
            return False
        if manifest.get("truncated") is True:
            return False
        pages, _ = self.registry_ops.count_index_entries(record)
        expected, indexed, missing, stale_orphans, _ = self.registry_ops.manifest_coverage(
            record, pages,
        )
        return bool(expected) and indexed == expected and not missing and not stale_orphans

    def _index_size_for(self, record: LibraryRecord) -> int:
        return self.registry_ops.index_size_for(record)

    def _delete_index_for(self, record: LibraryRecord) -> int:
        return self.registry_ops.delete_index_for(record)

    def inspect_library_docs(self, canonical_id: str) -> DocsInspectResult:
        return self.registry_ops.inspect_library_docs(canonical_id)

    def remove_library_docs(self, canonical_id: str) -> DocsRemoveResult:
        return self.registry_ops.remove_library_docs(canonical_id)

    def _record_age_cutoff_value(self, record: LibraryRecord) -> str | None:
        return self.registry_ops.record_age_cutoff_value(record)

    def prune_library_docs(
        self,
        *,
        library: str | None = None,
        keep_versions: list[str] | None = None,
        older_than_days: int = 90,
        dry_run: bool = True,
    ) -> DocsPruneResult:
        if hasattr(self.facade, "_library_prune_library_docs_impl"):
            return self.facade._library_prune_library_docs_impl(
                library=library,
                keep_versions=keep_versions,
                older_than_days=older_than_days,
                dry_run=dry_run,
            )
        return self.registry_ops.prune_library_docs(library=library, keep_versions=keep_versions, older_than_days=older_than_days, dry_run=dry_run)

    def list_libraries(self, stale_only: bool = False, limit: int | None = None) -> list[LibraryInfo]:
        return self.registry_ops.list_libraries(stale_only=stale_only, limit=limit)
