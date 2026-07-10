from __future__ import annotations

from typing import Any
import threading

from docmancer.docs.application.dependency_resolution import flutter_docs_url_for, flutter_docs_version_for, project_resolution_summary
from docmancer.docs.dartdoc import pub_dartdoc_root_url
from docmancer.docs.models import DocsJobStartResult, DocsTarget, ProjectPrefetchResult, RefreshResult

NO_PROJECT_VERSION_WARNING = "No version was found in project metadata; using latest/default docs."
FLUTTER_CHANNEL_DOCS_WARNING = (
    "Flutter project version {version} was detected, but api.flutter.dev provides current stable API docs, "
    "not an exact archived snapshot."
)


class DependencyProjectPrefetch:
    """Build and dispatch project dependency docs prefetch targets."""

    def __init__(self, dependencies: Any):
        self.dependencies = dependencies

    def __getattr__(self, name: str) -> Any:
        return getattr(self.dependencies, name)

    def prefetch_project_docs(
        self,
        project_path: str,
        include_flutter: bool = True,
        include_dart: bool = False,
        include_rust: bool = True,
        include_packages: list[str] | None = None,
        force_refresh: bool = False,
        continue_on_error: bool = True,
        async_: bool = False,
    ) -> ProjectPrefetchResult | DocsJobStartResult:
        metadata = self.read_project_metadata(project_path)
        warnings = list(metadata.warnings)
        targets: list[DocsTarget] = []

        if include_flutter:
            flutter_version = flutter_docs_version_for(metadata.flutter_version, metadata.flutter_channel)
            if flutter_version:
                if metadata.flutter_version and flutter_version == "stable":
                    warnings.append(FLUTTER_CHANNEL_DOCS_WARNING.format(version=metadata.flutter_version))
                targets.append(DocsTarget(
                    library="flutter-api",
                    ecosystem="flutter",
                    version=flutter_version,
                    source_type="api",
                    docs_url=flutter_docs_url_for(metadata.flutter_version, metadata.flutter_channel),
                    allowed_domains=["api.flutter.dev", "main-api.flutter.dev"],
                    doc_format="dartdoc",
                ))
            else:
                warnings.append(NO_PROJECT_VERSION_WARNING)
                if not continue_on_error:
                    return ProjectPrefetchResult(
                        project=metadata,
                        results=[],
                        warnings=warnings,
                        detected_ecosystems=metadata.detected_ecosystems,
                        resolution_summary=project_resolution_summary(metadata),
                    )

        if include_dart:
            warnings.append("Dart SDK documentation version detection is not implemented.")

        for package in include_packages or []:
            rust_version = metadata.packages.get(f"rust:{package}")
            if rust_version and include_rust:
                targets.append(DocsTarget(
                    library=package,
                    ecosystem="rust",
                    version=rust_version,
                    docs_url=f"https://docs.rs/{package}/{rust_version}/",
                    source_type="api",
                    allowed_domains=["docs.rs"],
                    path_prefixes=[f"/{package}/{rust_version}/"],
                ))
                continue
            npm_version = metadata.packages.get(f"npm:{package}")
            if npm_version:
                record = self.registry.get(package, ecosystem="npm", version=npm_version, source_type="api")
                if not record:
                    warnings.append(
                        f"{package}: Exact npm version {npm_version} was found, "
                        "but no npm documentation source is registered."
                    )
                    if not continue_on_error:
                        break
                    continue
                target = self._target_from_record(record)
                if not target.allowed_domains:
                    warnings.append(
                        f"{package}: Registered npm documentation source has no allowed_domains security policy."
                    )
                    if not continue_on_error:
                        break
                    continue
                targets.append(target)
                continue
            version = metadata.packages.get(package)
            if not version:
                warnings.append(f"{package}: Package was not found in project lockfiles.")
                if not continue_on_error:
                    break
                continue
            targets.append(DocsTarget(
                library=package,
                ecosystem="pub",
                version=version,
                docs_url=pub_dartdoc_root_url(package, version),
                source_type="api",
                doc_format="dartdoc",
                allowed_domains=["pub.dev"],
                path_prefixes=[f"/documentation/{package}/{version}/"],
            ))

        if async_:
            job = self.jobs.create("prefetch_project_docs")
            self.jobs.update(job.job_id, status="running", message="Started project docs prefetch job.", total_targets=len(targets))
            threading.Thread(
                target=self._run_prefetch_docs_targets_job,
                args=(job.job_id, targets, force_refresh, continue_on_error),
                daemon=True,
            ).start()
            return DocsJobStartResult(job_id=job.job_id, status="running", message="Started project docs prefetch job.")

        batch = self._prefetch_docs_targets_sync(targets, force_refresh=force_refresh, continue_on_error=continue_on_error)
        results = [
            RefreshResult(
                library_id=item.canonical_id,
                status=item.status,
                docs_url=item.docs_url,
                last_refreshed_at=None,
                version=item.version,
                source_type=item.source_type,
                message=item.message,
                pages_indexed=item.pages_indexed,
                targets_completed=1 if item.status in {"ready", "skipped"} else 0,
                targets_failed=1 if item.status == "failed" else 0,
            )
            for item in batch.results
        ]
        return ProjectPrefetchResult(
            project=metadata,
            results=results,
            warnings=[*warnings, *batch.warnings],
            detected_ecosystems=metadata.detected_ecosystems,
            resolution_summary=project_resolution_summary(metadata),
        )
