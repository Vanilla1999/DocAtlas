"""Lightweight source-policy metadata lookup before text hydration."""
from __future__ import annotations

from ._sqlite_store_shared import *  # noqa: F401,F403


class _SQLiteStoreFilterMetadata:
    def section_filter_metadata_for(
        self, section_ids: list[int],
    ) -> dict[int, dict[str, Any]]:
        """Return only filter metadata for active-generation hydration ids.

        This boundary deliberately excludes display/retrieval text so source
        policy can reject expansion candidates before content is hydrated.
        """
        if not section_ids:
            return {}
        ordered_ids = list(dict.fromkeys(int(value) for value in section_ids))
        placeholders = ",".join("?" for _ in ordered_ids)
        with self._connect() as conn:
            active_generation = self._active_generation_id(conn)
            if not active_generation:
                return {}
            rows = conn.execute(
                f"""
                SELECT hydration_id AS id, source, metadata_json,
                       source_path, source_identity, library_id,
                       resolved_version, version_family,
                       project_identity, project_path, module_id, doc_scope,
                       source_class, authority, lifecycle_status,
                       temporal_relevance, index_freshness,
                       docs_snapshot_exact
                FROM retrieval_children
                WHERE generation_id = ?
                  AND hydration_id IN ({placeholders})
                """,
                (active_generation, *ordered_ids),
            )
            result: dict[int, dict[str, Any]] = {}
            for row in rows:
                try:
                    metadata = json.loads(str(row["metadata_json"] or "{}"))
                except (TypeError, json.JSONDecodeError):
                    metadata = {}
                promoted = {
                    "source": str(row["source"] or ""),
                    "source_path": str(row["source_path"] or ""),
                    "source_identity": str(row["source_identity"] or ""),
                    "library_id": str(row["library_id"] or ""),
                    "resolved_version": str(row["resolved_version"] or ""),
                    "version_family": str(row["version_family"] or ""),
                    "project_identity": str(row["project_identity"] or ""),
                    "project_path": str(row["project_path"] or ""),
                    "module_id": str(row["module_id"] or ""),
                    "doc_scope": str(row["doc_scope"] or ""),
                    "source_class": str(row["source_class"] or ""),
                    "authority": str(row["authority"] or "unknown"),
                    "lifecycle_status": str(row["lifecycle_status"] or "active"),
                    "temporal_relevance": str(row["temporal_relevance"] or "current"),
                    "index_freshness": str(row["index_freshness"] or "synchronized"),
                }
                if row["docs_snapshot_exact"] is not None:
                    promoted["docs_snapshot_exact"] = bool(row["docs_snapshot_exact"])
                metadata.update(promoted)
                result[int(row["id"])] = metadata
            return result
