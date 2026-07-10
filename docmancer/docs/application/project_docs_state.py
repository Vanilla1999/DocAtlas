from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
import json

from docmancer.docs.domain.project_state import has_high_level_project_overview, partition_project_doc_state
from docmancer.docs.models import ProjectMetadata


class ProjectDocsState:
    """Read indexed/discovered project-doc state and dependency-doc readiness."""

    def __init__(self, dependencies: Any):
        self.dependencies = dependencies

    def __getattr__(self, name: str) -> Any:
        return getattr(self.dependencies, name)

    def indexed_project_doc_sources(self, project_path: str) -> list[dict[str, Any]]:
        root = Path(project_path).expanduser().resolve()
        agent = self._agent_instance()
        rows: list[dict[str, Any]] = []
        with agent.store._connect() as conn:
            for row in conn.execute(
                """
                SELECT source, metadata_json, ingested_at
                FROM sources
                WHERE json_extract(metadata_json, '$.project_path') = ?
                  AND json_extract(metadata_json, '$.source_class') = 'project_file'
                  AND json_extract(metadata_json, '$.project_docs') = 1
                ORDER BY source
                """,
                (str(root),),
            ):
                metadata = json.loads(row["metadata_json"] or "{}")
                rows.append({
                    "source": row["source"],
                    "path": metadata.get("project_doc_path") or metadata.get("source_path"),
                    "source_class": metadata.get("source_class"),
                    "content_hash": metadata.get("project_doc_content_hash"),
                    "mtime_ns": metadata.get("project_doc_mtime_ns"),
                    "reason": metadata.get("project_doc_reason"),
                    "doc_scope": metadata.get("doc_scope") or "project",
                    "module_id": metadata.get("module_id"),
                    "module_name": metadata.get("module_name"),
                    "module_path": metadata.get("module_path"),
                    "module_type": metadata.get("module_type"),
                    "ingested_at": row["ingested_at"],
                })
        return rows

    @staticmethod
    def source_state_guidance() -> dict[str, Any]:
        return {
            "stale_source": {
                "meaning": "An indexed project-doc source differs from the current file on disk.",
                "next_action": "Run sync_project_docs, then retry inspect_project_docs or get_project_context.",
            },
            "indexed_source_not_discovered": {
                "meaning": "The source exists in the index, but the current discovery pass did not select it as a project-doc candidate. This does not by itself mean the file is deleted or invalid.",
                "next_action": "Link the file from docs/INDEX.md or root docs, move it under a discovered docs location, adjust discovery, or run sync_project_docs to remove obsolete index entries.",
            },
            "ignored_generated_or_tooling_doc": {
                "meaning": "Generated, build, dependency, or tooling docs are not treated as reviewable project-owned docs by default.",
                "next_action": "Usually no action is required. If the file is official project documentation, link it from docs/INDEX.md or move it to a reviewable docs location.",
            },
            "missing_expected_source": {
                "meaning": "A document the user expected was not selected or cited.",
                "next_action": "Check inspect_project_docs output, docs/INDEX.md links, discovery scope, manifest entries, and ingestion freshness.",
            },
        }

    @staticmethod
    def partition_project_doc_state(
        candidates: list[dict[str, Any]],
        indexed_sources: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        return partition_project_doc_state(candidates, indexed_sources)

    @staticmethod
    def has_high_level_project_overview(candidates: list[dict[str, Any]]) -> bool:
        return has_high_level_project_overview(candidates)

    def project_dependency_docs_state(self, metadata: ProjectMetadata) -> dict[str, Any]:
        exact_dependencies = [item for item in metadata.dependencies if item.resolved_version and item.source_kind == "registry"]
        prefetched = []
        missing = []
        for dependency in exact_dependencies:
            record = self.registry.get(
                dependency.package_name,
                ecosystem=dependency.ecosystem,
                version=dependency.resolved_version,
                source_type="api",
            )
            item = {
                "library": dependency.package_name,
                "ecosystem": dependency.ecosystem,
                "version": dependency.resolved_version,
                "version_source": dependency.version_source,
            }
            if record and record.status == "available":
                prefetched.append({**item, "canonical_id": record.canonical_id})
            else:
                missing.append(item)
        available = bool(exact_dependencies)
        dependency_next_action: dict[str, Any] = {}
        if missing:
            missing_packages = sorted({item["library"] for item in missing})
            dependency_next_action = {
                "type": "ask_user_to_prefetch_dependency_docs",
                "tool_after_confirmation": "prepare_docs",
                "alias_tool_after_confirmation": "prefetch_project_dependency_docs",
                "requires_confirmation": True,
                "confirmation_reason": "network_fetch",
                "arguments_patch": {
                    "action": "prefetch_project_dependency_docs",
                    "project_path": metadata.project_path,
                    "include_packages": missing_packages,
                },
                "user_message": "I found dependency manifests/lockfiles. I can fetch exact documentation for the dependency versions used by this project. This may use the network. Proceed?",
            }
        return {
            "dependency_docs_available": available,
            "dependency_docs_prefetched": available and not missing,
            "dependency_docs_prefetched_count": len(prefetched),
            "dependency_docs_missing_count": len(missing),
            "dependency_docs_prefetched_sources": prefetched,
            "dependency_docs_missing_sources": missing,
            "dependency_next_action": dependency_next_action,
        }

    @staticmethod
    def candidate_sources(metadata: ProjectMetadata) -> list[dict[str, Any]]:
        return [asdict(item) for item in metadata.docs_candidates]
