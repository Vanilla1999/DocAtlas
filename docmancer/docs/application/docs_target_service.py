from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import httpx
from collections.abc import Callable
from typing import Any, ContextManager, Protocol
from urllib.parse import urlparse

from docmancer.docs.domain.target_security import host_allowed, is_remote_url, path_allowed, url_security_error
from docmancer.docs.models import DocsTarget
from docmancer.docs.registry import LibraryRecord
from docmancer.docs.resolver import normalize_version
from docmancer.docs.dartdoc import discover_pub_dartdoc_seed_urls, is_pub_dartdoc_target, normalize_pub_dartdoc_target, pub_dartdoc_root_url
from docmancer.docs.fetch_policy import DocsFetchPolicy, DocsFetchSecurityError
from docmancer.docs.fetch_transport import DocsHttpClient
from docmancer.docs.github_source_manifest import (
    GitHubApiClient,
    GitHubSourceManifestError,
    canonical_github_blob_scope_url,
    normalize_resolved_github_manifest,
    resolve_github_directory_manifest,
)


class DocsTargetJobs(Protocol):
    def update(self, job_id: str, **changes: Any) -> Any: ...
    def append_event(self, job_id: str, event: dict[str, Any], max_events: int = 50) -> None: ...
    def get(self, job_id: str) -> Any: ...


class DocsTargetService:
    """Application boundary for docs target normalization and URL validation."""

    def __init__(
        self,
        render_docs_url: Callable[[str, str, str], str],
        jobs: DocsTargetJobs | None = None,
        github_api_client_factory: Callable[[], ContextManager[GitHubApiClient]] | None = None,
    ):
        self.render_docs_url = render_docs_url
        self.jobs = jobs
        self.github_api_client_factory = github_api_client_factory

    @contextmanager
    def _github_api_client(self, owner: str, repository: str):
        if self.github_api_client_factory is not None:
            with self.github_api_client_factory() as client:
                yield client
            return
        policy = DocsFetchPolicy(
            allowed_hosts=("api.github.com",),
            path_prefixes=(f"/repos/{owner}/{repository}/",),
        )
        raw_client = httpx.Client(
            timeout=30.0,
            follow_redirects=False,
            headers={"User-Agent": "docmancer/1.0"},
            trust_env=False,
        )
        with DocsHttpClient(raw_client, policy) as client:
            yield client

    def resolve_github_directory_target(self, target: DocsTarget) -> DocsTarget:
        """Resolve an approved schema-v2 directory declaration exactly once before ingest."""

        manifest = target.source_manifest or {}
        if manifest.get("schema_version") != 2 or "documents" in manifest:
            return target
        official = manifest.get("official")
        if type(official) is not bool:
            raise ValueError("official must be a boolean")
        discovery = manifest.get("discovery")
        if not isinstance(discovery, dict) or discovery.get("kind") != "github_directory":
            raise ValueError("discovery.kind must be github_directory")
        approved = target.docs_url
        if not approved:
            raise ValueError("github directory manifest requires an explicitly approved blob target")
        if not canonical_github_blob_scope_url(approved, discovery):
            raise ValueError("github directory manifest scope does not match approved blob target")
        security_error = url_security_error(approved)
        if security_error:
            raise ValueError(security_error)
        if not target.allowed_domains or not host_allowed(approved, target.allowed_domains):
            raise ValueError(f"URL host is not in allowed_domains: {approved}")
        if not path_allowed(approved, target.path_prefixes):
            raise ValueError(f"URL path is outside path_prefixes: {approved}")
        try:
            with self._github_api_client(str(discovery.get("owner") or ""), str(discovery.get("repository") or "")) as client:
                resolved = resolve_github_directory_manifest(
                    client,
                    owner=str(discovery.get("owner") or ""),
                    repository=str(discovery.get("repository") or ""),
                    requested_ref=str(discovery.get("requested_ref") or ""),
                    directory=str(discovery.get("directory") or ""),
                    official=official,
                )
        except GitHubSourceManifestError as exc:
            raise ValueError(str(exc)) from exc
        if not resolved["complete"] or resolved["truncated"]:
            raise ValueError(str(resolved.get("reason_code") or "github directory manifest is incomplete"))
        return replace(target, source_manifest=resolved)

    @staticmethod
    def target_from_dict(value: dict[str, Any] | DocsTarget) -> DocsTarget:
        if isinstance(value, DocsTarget):
            return value
        return DocsTarget(
            library=value["library"],
            ecosystem=value.get("ecosystem"),
            version=value.get("version") or "latest",
            source_type=value.get("source_type") or "api",
            docs_url=value.get("docs_url"),
            docs_url_template=value.get("docs_url_template"),
            seed_urls=list(value.get("seed_urls") or []),
            allowed_domains=list(value.get("allowed_domains") or []),
            path_prefixes=list(value.get("path_prefixes") or []),
            max_pages=int(value.get("max_pages") or 200),
            browser=bool(value.get("browser") or False),
            doc_format=value.get("doc_format"),
            warnings=list(value.get("warnings") or []),
            source_manifest=dict(value.get("source_manifest") or {}),
        )

    @staticmethod
    def target_to_spec(target: DocsTarget, urls: list[str] | None = None) -> dict[str, Any]:
        source_manifest = dict(target.source_manifest)
        if source_manifest.get("schema_version") == 2:
            source_manifest = normalize_resolved_github_manifest(source_manifest)
        return {
            "library": target.library,
            "ecosystem": target.ecosystem,
            "version": normalize_version(target.version) or "latest",
            "source_type": target.source_type or "api",
            "docs_url": target.docs_url,
            "docs_url_template": target.docs_url_template,
            "seed_urls": list(target.seed_urls),
            "resolved_urls": list(urls or []),
            "allowed_domains": list(target.allowed_domains),
            "path_prefixes": list(target.path_prefixes),
            "max_pages": target.max_pages,
            "browser": target.browser,
            "doc_format": target.doc_format,
            "warnings": list(target.warnings),
            "source_manifest": source_manifest,
        }

    def target_from_record(self, record: LibraryRecord) -> DocsTarget:
        spec = record.target_spec or {}
        return DocsTarget(
            library=spec.get("library") or record.name,
            ecosystem=spec.get("ecosystem") or record.ecosystem,
            version=spec.get("version") or record.version,
            source_type=spec.get("source_type") or record.source_type or "api",
            docs_url=spec.get("docs_url") if "docs_url" in spec else record.docs_url,
            docs_url_template=spec.get("docs_url_template") if "docs_url_template" in spec else record.docs_url_template,
            seed_urls=list(spec.get("seed_urls") or []),
            allowed_domains=list(spec.get("allowed_domains") or []),
            path_prefixes=list(spec.get("path_prefixes") or []),
            max_pages=int(spec.get("max_pages") or 200),
            browser=bool(spec.get("browser") or False),
            doc_format=spec.get("doc_format"),
            warnings=list(spec.get("warnings") or []),
            source_manifest=dict(spec.get("source_manifest") or {}),
        )

    def record_urls(self, record: LibraryRecord) -> list[str]:
        spec = record.target_spec or {}
        resolved = spec.get("resolved_urls")
        if isinstance(resolved, list) and resolved:
            return [str(url) for url in resolved]
        target = self.target_from_record(record)
        urls, _ = self.target_urls(target)
        return urls or ([record.docs_url] if record.docs_url else [])

    def target_urls(self, target: DocsTarget) -> tuple[list[str], str | None]:
        manifest = target.source_manifest or {}
        if manifest.get("schema_version") == 2:
            try:
                normalized = normalize_resolved_github_manifest(manifest)
            except GitHubSourceManifestError as exc:
                return [], str(exc)
            if not normalized["complete"] or normalized["truncated"]:
                return [], "github directory manifest is incomplete"
            discovery = normalized["discovery"]
            approved = target.docs_url
            if not approved:
                return [], "github directory manifest requires an explicitly approved blob target"
            if not canonical_github_blob_scope_url(approved, discovery):
                return [], "github directory manifest scope does not match approved blob target"
            urls = [document["blob_url"] for document in normalized["documents"]]
            for url in [approved, *urls]:
                security_error = url_security_error(url)
                if security_error:
                    return [], security_error
                if not target.allowed_domains:
                    return [], "allowed_domains is required for remote docs targets"
                if not host_allowed(url, target.allowed_domains):
                    return [], f"URL host is not in allowed_domains: {url}"
                if not path_allowed(url, target.path_prefixes):
                    return [], f"URL path is outside path_prefixes: {url}"
            return urls or [approved], None

        version = normalize_version(target.version) or "latest"
        urls = list(target.seed_urls)
        if target.docs_url:
            urls.insert(0, target.docs_url)
        elif target.docs_url_template:
            urls.insert(0, self.render_docs_url(target.docs_url_template, target.library, version))
        if not urls:
            return [], "target must provide docs_url, docs_url_template, or seed_urls"
        for url in urls:
            security_error = url_security_error(url)
            if security_error:
                return [], security_error
            if is_remote_url(url):
                if not target.allowed_domains:
                    return [], "allowed_domains is required for remote docs targets"
                if not host_allowed(url, target.allowed_domains):
                    return [], f"URL host is not in allowed_domains: {url}"
                if not path_allowed(url, target.path_prefixes):
                    return [], f"URL path is outside path_prefixes: {url}"
        return urls, None

    @staticmethod
    def dependency_docs_url_guidance(target: DocsTarget) -> list[str]:
        urls = list(target.seed_urls)
        if target.docs_url:
            urls.insert(0, target.docs_url)
        elif target.docs_url_template:
            version = normalize_version(target.version) or "latest"
            urls.insert(0, target.docs_url_template.format(library=target.library, version=version))

        warnings: list[str] = []
        for url in urls:
            parsed = urlparse(url)
            if parsed.hostname == "pub.dev" and parsed.path.startswith("/packages/"):
                version = normalize_version(target.version) or "latest"
                warnings.append(
                    f"{target.library}: Prefer exact pub.dev API docs such as "
                    f"https://pub.dev/documentation/{target.library}/{version}/ over package landing pages."
                )
        return warnings

    def discover_pub_dartdoc_target(self, target: DocsTarget, warnings: list[str], job_id: str | None = None, canonical_id: str | None = None) -> DocsTarget:
        if not is_pub_dartdoc_target(target):
            return target
        target = normalize_pub_dartdoc_target(target)
        version = normalize_version(target.version) or "latest"
        root_url = pub_dartdoc_root_url(target.library, version)
        if job_id and self.jobs:
            self.jobs.update(job_id, phase="discovering", current_target=canonical_id, current_url=root_url, message=f"Discovering Dartdoc seed URLs for {target.library}.")
            self.jobs.append_event(job_id, {"phase": "discovering", "message": f"Discovering Dartdoc seed URLs for {target.library}", "url": root_url})
        try:
            policy = DocsFetchPolicy(
                allowed_hosts=tuple(target.allowed_domains),
                path_prefixes=tuple(target.path_prefixes),
            )
            raw_client = httpx.Client(
                timeout=30.0,
                follow_redirects=False,
                headers={"User-Agent": "docmancer/1.0"},
                trust_env=False,
            )
            with DocsHttpClient(raw_client, policy) as client:
                resp = client.get(root_url)
                if resp.status_code != 200:
                    raise ValueError(f"status {resp.status_code}")

                def fetch_url(url: str) -> str | None:
                    fetched = client.get(url)
                    if fetched.status_code != 200:
                        return None
                    return fetched.text

                seeds = discover_pub_dartdoc_seed_urls(target.library, version, resp.text, root_url, max_seed_urls=target.max_pages or 500, fetch_url=fetch_url)
        except DocsFetchSecurityError as exc:
            if exc.category != "transport_error":
                raise
            warning = f"{target.library}: could not discover pub.dev Dartdoc seed URLs (transport_error); falling back to root URL."
            warnings.append(warning)
            target = replace(target, warnings=[*target.warnings, warning])
            return target
        except Exception as exc:
            warning = f"{target.library}: could not discover pub.dev Dartdoc seed URLs ({exc}); falling back to root URL."
            warnings.append(warning)
            target = replace(target, warnings=[*target.warnings, warning])
            return target
        if not seeds:
            warning = f"{target.library}: no pub.dev Dartdoc seed URLs discovered; falling back to root URL."
            warnings.append(warning)
            target = replace(target, warnings=[*target.warnings, warning])
            return target
        if job_id and self.jobs:
            self.jobs.update(job_id, discovered_pages=len(seeds), total_pages=max((self.jobs.get(job_id).total_pages if self.jobs.get(job_id) else 0), len(seeds)), message=f"Discovered {len(seeds)} Dartdoc seed URLs for {target.library}.")
            self.jobs.append_event(job_id, {"phase": "discovering", "message": f"Discovered {len(seeds)} Dartdoc seed URLs", "url": root_url, "discovered_pages": len(seeds), "total_pages": len(seeds)})
        return replace(target, docs_url=None, docs_url_template=None, seed_urls=seeds)

def target_result_summary(result: Any) -> dict[str, Any]:
    return {
        "canonical_id": result.canonical_id,
        "status": result.status,
        "pages_indexed": result.pages_indexed,
        "message": result.message,
    }
