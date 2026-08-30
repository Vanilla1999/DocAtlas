from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
import hashlib
import json
import shutil
import threading
import time
from urllib.parse import urlparse

import httpx
import yaml

from docmancer.core.config import DocmancerConfig
from docmancer.docs.domain.policies import docs_policy, is_stale
from docmancer.docs.domain.project_state import create_project_docs_next_action, has_high_level_project_overview, partition_project_doc_state, project_docs_structured_next_action
from docmancer.docs.domain.source_identity import docs_exactness, docs_identity, docs_request
from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error
from docmancer.docs.domain.trust_contract import build_project_context_trust_contract
from docmancer.docs.models import DocsChunk, DocsInspectResult, DocsJobStartResult, DocsManifestValidationResult, DocsPruneResult, DocsRemoveResult, DocsResult, DocsSourceResolution, DocsTarget, DocsTargetResult, DocsTargetsPrefetchResult, LibraryInfo, ProjectDocsBootstrapResult, ProjectDocsChunk, ProjectDocsIngestResult, ProjectDocsInspectResult, ProjectDocsResult, ProjectMetadata, ProjectPrefetchResult, RefreshResult
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import canonical_library_id, normalize_library_name, normalize_version
from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, is_pub_dartdoc_target, normalize_pub_dartdoc_target, pub_dartdoc_root_url
from docmancer.docs.manifest_contract import normalize_manifest_target, semantic_manifest_errors

STALE_AFTER_DAYS = 30
DEFAULT_DOC_TOKENS = 4000
PUB_DOCS_URL_TEMPLATE = "https://pub.dev/documentation/{library}/{version}/"
NO_PROJECT_VERSION_WARNING = "No version was found in project metadata; using latest/default docs."
PACKAGE_NOT_FOUND_WARNING = "Package was not found in pubspec.lock."
FLUTTER_CHANNEL_DOCS_WARNING = (
    "Flutter project version {version} was detected, but api.flutter.dev provides current stable API docs, "
    "not an exact archived snapshot."
)


class DocsManifestDependencies(Protocol):
    jobs: Any

    def read_project_metadata(self, project_path: str) -> ProjectMetadata: ...
    def _target_from_dict(self, value: dict[str, Any] | DocsTarget) -> DocsTarget: ...
    def _target_urls(self, target: DocsTarget) -> tuple[list[str], str | None]: ...
    def _dependency_docs_url_guidance(self, target: DocsTarget) -> list[str]: ...
    def prefetch_docs_targets(self, targets: list[DocsTarget], *, force_refresh: bool = False, continue_on_error: bool = True) -> DocsTargetsPrefetchResult: ...
    def _prefetch_docs_targets_sync(self, targets: list[DocsTarget], *, force_refresh: bool = False, continue_on_error: bool = True, job_id: str | None = None) -> DocsTargetsPrefetchResult: ...


class DocsManifestService:
    def __init__(self, deps: DocsManifestDependencies):
        self.deps = deps
        self.jobs = deps.jobs

    @staticmethod
    def merge_manifest_defaults(defaults: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
        merged = dict(defaults)
        for key, value in target.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = DocsManifestService.merge_manifest_defaults(merged[key], value)
            else:
                merged[key] = value
        return merged

    def resolve_manifest_project_version(
        self,
        target: dict[str, Any],
        project_path: str | None,
        warnings: list[str],
    ) -> dict[str, Any]:
        if target.get("version") != "project-version":
            return target
        spec = target.get("project_version") or {}
        package = spec.get("package") or target.get("library")
        fallback = spec.get("fallback") or "latest"
        resolved = fallback
        if project_path:
            metadata = self.deps.read_project_metadata(project_path)
            warnings.extend(metadata.warnings)
            resolved = metadata.packages.get(package) or fallback
            if resolved == fallback and package not in metadata.packages:
                warnings.append(f"{package}: Package was not found in resolved project metadata; using {fallback}.")
        else:
            warnings.append(f"{target.get('id') or target.get('library')}: project_path is required for project-version; using {fallback}.")
        updated = dict(target)
        updated["version"] = resolved
        return updated

    def validate_docs_manifest(
        self,
        manifest_path: str,
        *,
        project_path: str | None = None,
        targets: list[str] | None = None,
    ) -> DocsManifestValidationResult:
        path = Path(manifest_path).expanduser()
        errors: list[str] = []
        warnings: list[str] = []
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            return DocsManifestValidationResult(False, str(path), errors=[f"invalid YAML: {exc}"])
        except OSError as exc:
            return DocsManifestValidationResult(False, str(path), errors=[str(exc)])
        if not isinstance(data, dict):
            return DocsManifestValidationResult(False, str(path), errors=["manifest must be a mapping"])
        manifest_version = data.get("version")
        if manifest_version != 2:
            errors.append("manifest version must be 2")
        defaults = data.get("defaults") or {}
        raw_targets = data.get("targets") or []
        if not isinstance(raw_targets, list):
            errors.append("targets must be a list")
            raw_targets = []

        selected = set(targets or [])
        seen_ids: set[str] = set()
        seen_canonical: set[str] = set()
        docs_targets: list[DocsTarget] = []
        valid_source_types = {"api", "guides", "tutorials", "migration", "reference", "specification"}

        for index, raw in enumerate(raw_targets):
            if not isinstance(raw, dict):
                errors.append(f"targets[{index}] must be a mapping")
                continue
            target_id = raw.get("id")
            if selected and target_id not in selected:
                continue
            if target_id:
                if target_id in seen_ids:
                    errors.append(f"duplicate target id: {target_id}")
                seen_ids.add(target_id)
            merged = self.merge_manifest_defaults(defaults, raw)
            try:
                merged = normalize_manifest_target(merged, manifest_version=int(manifest_version or 0))
            except (TypeError, ValueError) as exc:
                errors.append(f"target {target_id or index}: {exc}")
                continue
            merged = self.resolve_manifest_project_version(merged, project_path, warnings)
            semantic_errors, semantic_warnings = semantic_manifest_errors(
                merged, manifest_version=int(manifest_version or 0)
            )
            errors.extend(semantic_errors)
            warnings.extend(semantic_warnings)
            source_type = merged.get("source_type") or "api"
            if source_type not in valid_source_types:
                errors.append(f"invalid source_type for {target_id or merged.get('library')}: {source_type}")
                continue
            try:
                target = self.deps._target_from_dict(merged)
            except KeyError as exc:
                errors.append(f"target {target_id or index} missing required field: {exc.args[0]}")
                continue
            canonical_id = canonical_library_id(target.library, target.ecosystem, target.version, target.source_type)
            if canonical_id in seen_canonical:
                errors.append(f"duplicate canonical target id: {canonical_id}")
            seen_canonical.add(canonical_id)
            _, error = self.deps._target_urls(target)
            if error:
                errors.append(f"{target_id or canonical_id}: {error}")
                continue
            warnings.extend(self.deps._dependency_docs_url_guidance(target))
            docs_targets.append(target)

        if selected:
            found = {raw.get("id") for raw in raw_targets if isinstance(raw, dict)}
            for target_id in selected - found:
                errors.append(f"unknown target id: {target_id}")
        lock = self._read_lock(path)
        if lock and lock.get("manifest_digest") != self._manifest_digest(path):
            warnings.append("manifest_outdated: the docs manifest changed after the resolved lock was written")
        project_digest = self._project_digest(project_path)
        if (
            lock
            and project_digest
            and lock.get("project_dependency_digest") != project_digest
        ):
            warnings.append(
                "manifest_outdated: project dependency evidence changed after the resolved lock was written"
            )
        return DocsManifestValidationResult(not errors, str(path), targets=docs_targets, errors=errors, warnings=warnings)

    def prefetch_docs_manifest(
        self,
        manifest_path: str,
        *,
        project_path: str | None = None,
        targets: list[str] | None = None,
        force_refresh: bool = False,
        continue_on_error: bool = True,
        async_: bool = False,
    ) -> DocsTargetsPrefetchResult | DocsJobStartResult:
        if async_:
            job = self.jobs.create("prefetch_docs_manifest")
            self.jobs.update(job.job_id, status="running", message="Started docs prefetch job.")
            threading.Thread(
                target=self._run_prefetch_docs_manifest_job,
                args=(job.job_id, manifest_path, project_path, targets, force_refresh, continue_on_error),
                daemon=True,
            ).start()
            return DocsJobStartResult(job_id=job.job_id, status="running", message="Started docs prefetch job.")

        validation = self.validate_docs_manifest(manifest_path, project_path=project_path, targets=targets)
        if not validation.valid:
            return DocsTargetsPrefetchResult(
                status="failed",
                warnings=validation.warnings + validation.errors,
                message="manifest validation failed",
            )
        result = self.deps.prefetch_docs_targets(
            validation.targets,
            force_refresh=force_refresh,
            continue_on_error=continue_on_error,
        )
        if result.status not in {"failed", "aborted"}:
            self._write_lock(
                Path(manifest_path).expanduser(), validation.targets, result,
                project_path=project_path,
            )
        if validation.warnings:
            return DocsTargetsPrefetchResult(
                status=result.status,
                results=result.results,
                warnings=validation.warnings + result.warnings,
                message=result.message,
            )
        return result

    def _run_prefetch_docs_manifest_job(
        self,
        job_id: str,
        manifest_path: str,
        project_path: str | None,
        targets: list[str] | None,
        force_refresh: bool,
        continue_on_error: bool,
    ) -> None:
        try:
            self.jobs.update(job_id, status="running", phase="validating", message="Validating docs manifest.")
            validation = self.validate_docs_manifest(manifest_path, project_path=project_path, targets=targets)
            if validation.warnings:
                for warning in validation.warnings:
                    self.jobs.append_warning(job_id, warning)
            if not validation.valid:
                for error in validation.errors:
                    self.jobs.append_error(job_id, error)
                self.jobs.update(job_id, status="failed", phase="done", message="manifest validation failed")
                return
            result = self.deps._prefetch_docs_targets_sync(
                validation.targets,
                force_refresh=force_refresh,
                continue_on_error=continue_on_error,
                job_id=job_id,
            )
            if result.status not in {"failed", "aborted"}:
                self._write_lock(
                    Path(manifest_path).expanduser(), validation.targets, result,
                    project_path=project_path,
                )
        except Exception as exc:
            self.jobs.append_error(job_id, str(exc))
            self.jobs.update(job_id, status="failed", phase="done", message=str(exc))

    @staticmethod
    def _lock_path(manifest_path: Path) -> Path:
        return manifest_path.parent / ".docatlas" / "docs.lock.json"

    @staticmethod
    def _manifest_digest(manifest_path: Path) -> str | None:
        try:
            content = manifest_path.read_bytes()
        except OSError:
            return None
        return "sha256:" + hashlib.sha256(content).hexdigest()

    def _read_lock(self, manifest_path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(self._lock_path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def _write_lock(
        self,
        manifest_path: Path,
        targets: list[DocsTarget],
        result: DocsTargetsPrefetchResult,
        *,
        project_path: str | None = None,
    ) -> None:
        lock_path = self._lock_path(manifest_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        result_by_id = {
            item.canonical_id: asdict(item)
            for item in result.results
            if item.canonical_id
        }
        canonical_targets = {
            canonical_library_id(target.library, target.ecosystem, target.version, target.source_type): {
                "canonical_id": canonical_library_id(
                    target.library, target.ecosystem, target.version, target.source_type
                ),
                "library": target.library,
                "ecosystem": target.ecosystem,
                "version": target.version,
                "source_type": target.source_type,
                "docs_url": target.docs_url,
                "allowed_domains": list(target.allowed_domains),
                "path_prefixes": list(target.path_prefixes),
                "max_pages": target.max_pages,
                "authority": target.authority,
                "version_policy": target.version_policy,
                "version_binding": target.version_binding,
                "version_evidence": dict(target.version_evidence),
                "coverage": target.coverage,
                "result": result_by_id.get(canonical_library_id(
                    target.library, target.ecosystem, target.version, target.source_type
                )),
            }
            for target in targets
        }
        previous = self._read_lock(manifest_path)
        manifest_digest = self._manifest_digest(manifest_path)
        if previous and previous.get("manifest_digest") == manifest_digest:
            for item in previous.get("targets") or []:
                if isinstance(item, dict) and item.get("canonical_id"):
                    canonical_targets.setdefault(str(item["canonical_id"]), item)
        payload = {
            "schema_version": 1,
            "manifest_path": manifest_path.name,
            "manifest_digest": manifest_digest,
            "project_dependency_digest": self._project_digest(project_path),
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "status": result.status,
            "targets": [canonical_targets[key] for key in sorted(canonical_targets)],
        }
        temporary = lock_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(lock_path)

    def _project_digest(self, project_path: str | None) -> str | None:
        if not project_path:
            return None
        metadata = self.deps.read_project_metadata(project_path)
        rows = sorted([
            {
                "ecosystem": item.ecosystem,
                "package_name": item.package_name,
                "workspace_member": item.workspace_member,
                "dependency_group": item.dependency_group,
                "specifier_raw": item.specifier_raw,
                "resolved_version": item.resolved_version,
                "version_source": item.version_source,
                "source_kind": item.source_kind,
            }
            for item in metadata.dependencies
        ], key=lambda item: (
            item["ecosystem"], item["package_name"], item["workspace_member"] or "",
            item["dependency_group"], item["specifier_raw"] or "",
        ))
        encoded = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()
