"""Versioned, human-reviewable documentation manifest contract."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


MANIFEST_AUTHORITIES = {
    "official_registry",
    "official_project",
    "official_product",
    "community",
    "user_provided",
}
MANIFEST_IDENTITY_KINDS = {"package", "framework", "sdk", "product"}
MANIFEST_VERSION_POLICIES = {"exact", "channel", "rolling", "project"}
MANIFEST_VERSION_BINDINGS = {"exact", "channel", "rolling", "unversioned", "unknown"}
MANIFEST_COVERAGE = {"complete", "bounded", "sampled", "unknown"}
MANIFEST_DOC_FORMATS = {"html", "markdown", "direct-text", "dartdoc", "godoc", "javadoc"}
MANIFEST_DISCOVERY_STRATEGIES = {
    "auto", "llms.txt", "llms-full.txt", "sitemap.xml", "nav-crawl",
}
ROLLING_VERSIONS = {"latest", "stable", "main", "master", "beta", "next", "rolling"}


def normalize_manifest_target(raw: dict[str, Any], *, manifest_version: int) -> dict[str, Any]:
    """Flatten one v2 target into the existing DocsTarget-compatible shape."""

    if manifest_version == 1:
        return dict(raw)
    identity = raw.get("identity") or {}
    version = raw.get("version") or {}
    source = raw.get("source") or {}
    scope = raw.get("scope") or {}
    if not all(isinstance(item, dict) for item in (identity, version, source, scope)):
        raise ValueError("identity, version, source, and scope must be mappings")
    ecosystem = str(identity.get("ecosystem") or "").strip()
    namespace = str(identity.get("namespace") or "").strip()
    name = str(identity.get("name") or "").strip()
    library = _qualified_library(ecosystem, namespace, name)
    return {
        "id": raw.get("id"),
        "library": library,
        "ecosystem": ecosystem or None,
        "version": version.get("requested") or "latest",
        "project_version": {
            "package": version.get("package"),
            "fallback": version.get("fallback") or "latest",
        } if version.get("policy") == "project" else {},
        "source_type": source.get("type") or "api",
        "docs_url": source.get("url"),
        "docs_url_template": source.get("url_template"),
        "seed_urls": list(scope.get("seed_urls") or []),
        "allowed_domains": list(scope.get("allowed_domains") or []),
        "path_prefixes": list(scope.get("path_prefixes") or []),
        "max_pages": scope.get("max_pages") or 200,
        "browser": bool(scope.get("browser") or False),
        "doc_format": source.get("format"),
        "source_manifest": dict(source.get("manifest") or {}),
        "identity": dict(identity),
        "authority": source.get("authority"),
        "version_policy": version.get("policy"),
        "version_binding": source.get("version_binding"),
        "version_evidence": dict(source.get("version_evidence") or {}),
        "coverage": scope.get("coverage"),
        "discovery_strategy": scope.get("discovery_strategy"),
        "query": raw.get("query"),
    }


def semantic_manifest_errors(target: dict[str, Any], *, manifest_version: int) -> tuple[list[str], list[str]]:
    """Return semantic errors and warnings that structural target parsing cannot catch."""

    errors: list[str] = []
    warnings: list[str] = []
    label = str(target.get("id") or target.get("library") or "target")
    if target.get("query"):
        errors.append(f"{label}: query is task-specific and must not be persisted in a docs manifest")
    urls = [target.get("docs_url"), *(target.get("seed_urls") or [])]
    remote = [str(url) for url in urls if str(url or "").startswith(("http://", "https://"))]
    if remote and not target.get("allowed_domains"):
        errors.append(f"{label}: allowed_domains is required for remote targets")
    max_pages = target.get("max_pages", 200)
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 500:
        errors.append(f"{label}: max_pages must be an integer between 1 and 500")
    strategy = target.get("discovery_strategy")
    if strategy and strategy not in MANIFEST_DISCOVERY_STRATEGIES:
        errors.append(f"{label}: unsupported discovery_strategy: {strategy}")
    doc_format = target.get("doc_format")
    if doc_format and doc_format not in MANIFEST_DOC_FORMATS:
        errors.append(f"{label}: unsupported documentation format: {doc_format}")
    if manifest_version == 1:
        return errors, warnings

    identity = target.get("identity") or {}
    kind = identity.get("kind")
    if kind not in MANIFEST_IDENTITY_KINDS:
        errors.append(f"{label}: identity.kind must be one of {sorted(MANIFEST_IDENTITY_KINDS)}")
    if not identity.get("name"):
        errors.append(f"{label}: identity.name is required")
    if not identity.get("ecosystem"):
        errors.append(f"{label}: identity.ecosystem is required")
    authority = target.get("authority")
    if authority not in MANIFEST_AUTHORITIES:
        errors.append(f"{label}: source.authority must be one of {sorted(MANIFEST_AUTHORITIES)}")
    policy = target.get("version_policy")
    if policy not in MANIFEST_VERSION_POLICIES:
        errors.append(f"{label}: version.policy must be one of {sorted(MANIFEST_VERSION_POLICIES)}")
    binding = target.get("version_binding")
    if binding not in MANIFEST_VERSION_BINDINGS:
        errors.append(f"{label}: source.version_binding must be one of {sorted(MANIFEST_VERSION_BINDINGS)}")
    coverage = target.get("coverage")
    if coverage not in MANIFEST_COVERAGE:
        errors.append(f"{label}: scope.coverage must be one of {sorted(MANIFEST_COVERAGE)}")
    requested = str(target.get("version") or "").strip().casefold()
    if policy == "exact" and requested in ROLLING_VERSIONS:
        errors.append(f"{label}: an exact version policy cannot use rolling version {requested!r}")
    if policy == "exact" and binding != "exact":
        errors.append(f"{label}: exact version policy requires source.version_binding='exact'")
    exact_url = str(target.get("docs_url") or target.get("docs_url_template") or "").casefold()
    if (
        policy == "exact"
        and requested not in exact_url
        and not target.get("version_evidence")
    ):
        errors.append(
            f"{label}: exact source URL does not contain the requested version; source.version_evidence is required"
        )
    if policy in {"rolling", "channel"} and binding == "exact":
        errors.append(f"{label}: rolling/channel version policy cannot claim an exact source binding")
    if remote and not target.get("path_prefixes"):
        broad = any((urlparse(url).path or "/") == "/" for url in remote)
        if broad:
            warnings.append(f"{label}: broad documentation root has no path_prefixes")
    if strategy == "llms-full.txt" and coverage != "complete":
        warnings.append(f"{label}: llms-full.txt is selected without complete coverage intent")
    return errors, warnings


def manifest_v2_target_from_flat(target: dict[str, Any]) -> dict[str, Any]:
    """Build a reviewable v2 manifest target from an inspected flat target."""

    identity = dict(target.get("identity") or {})
    identity.setdefault("kind", "package")
    identity.setdefault("ecosystem", target.get("ecosystem") or "web")
    identity.setdefault("name", target.get("library"))
    requested = target.get("version") or "latest"
    policy = target.get("version_policy") or (
        "rolling" if str(requested).casefold() in ROLLING_VERSIONS else "exact"
    )
    binding = target.get("version_binding") or (
        "rolling" if policy in {"rolling", "channel"} else "unknown"
    )
    return {
        "id": target.get("id") or _proposal_id(identity),
        "identity": identity,
        "version": {"requested": requested, "policy": policy},
        "source": {
            "type": target.get("source_type") or "reference",
            "url": target.get("docs_url"),
            "authority": target.get("authority") or "user_provided",
            "version_binding": binding,
            "version_evidence": dict(target.get("version_evidence") or {}),
            "format": target.get("doc_format") or "html",
        },
        "scope": {
            "allowed_domains": list(target.get("allowed_domains") or []),
            "path_prefixes": list(target.get("path_prefixes") or []),
            "seed_urls": list(target.get("seed_urls") or []),
            "max_pages": int(target.get("max_pages") or 50),
            "coverage": target.get("coverage") or "bounded",
            "discovery_strategy": target.get("discovery_strategy") or "auto",
        },
    }


def _qualified_library(ecosystem: str, namespace: str, name: str) -> str:
    if not name:
        return ""
    if not namespace:
        return name
    separator = ":" if ecosystem.casefold() in {"maven", "gradle", "java"} else "/"
    return f"{namespace.rstrip('/:')}{separator}{name.lstrip('/:')}"


def _proposal_id(identity: dict[str, Any]) -> str:
    namespace = str(identity.get("namespace") or "").strip().replace("/", "-").replace(":", "-")
    name = str(identity.get("name") or "docs").strip().replace("/", "-").replace(":", "-")
    return "-".join(part for part in (namespace, name) if part).lower()
