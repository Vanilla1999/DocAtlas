"""Bounded registry-metadata discovery for unknown library documentation."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlparse

import httpx

from docmancer.docs.resolver import normalize_lookup_key, normalize_version

_MAX_METADATA_BYTES = 2 * 1024 * 1024


def discover_library_docs_sources(
    library: str,
    ecosystem: str | None,
    version: str | None = None,
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Return bounded, user-reviewable docs candidates from an ecosystem registry."""

    name = normalize_lookup_key(library)
    selected_version = normalize_version(version)
    normalized_ecosystem = normalize_lookup_key(ecosystem or "")
    if normalized_ecosystem in {"go", "golang"}:
        module = library.strip()
        if not _safe_go_module(module):
            return {
                **_result(library, "go", []),
                "status": "invalid_package_identity",
                "message": "Go discovery requires a full module path such as github.com/gin-gonic/gin.",
            }
        # Module versions and paths are preserved for the public URL; the Go
        # proxy escaping rules are case-sensitive for uppercase characters.
        docs_version = version.strip() if isinstance(version, str) and version.strip() else None
        suffix = f"@{quote(docs_version, safe='.-_~+')}" if docs_version else ""
        return _result(library, "go", [
            _candidate(
                f"https://pkg.go.dev/{quote(module, safe='/.-_~')}{suffix}",
                label="pkg.go.dev module documentation",
                confidence="high" if docs_version else "medium",
                source="go_module_registry",
                ecosystem="go",
                version=docs_version,
                source_type="api",
            )
        ])
    if normalized_ecosystem in {"dart", "flutter", "pub"}:
        docs_version = selected_version or "latest"
        return _result(library, "pub", [
            _candidate(
                f"https://pub.dev/documentation/{quote(name, safe='')}/{quote(docs_version, safe='')}/",
                label="pub.dev API reference",
                confidence="high",
                source="pub_registry",
                ecosystem="pub",
                version=docs_version,
                source_type="api",
            )
        ])
    if normalized_ecosystem == "rust":
        docs_version = selected_version or "latest"
        return _result(library, "rust", [
            _candidate(
                f"https://docs.rs/{quote(name, safe='')}/{quote(docs_version, safe='')}/",
                label="docs.rs API reference",
                confidence="high",
                source="crates_registry",
                ecosystem="rust",
                version=docs_version,
                source_type="api",
            )
        ])
    if normalized_ecosystem not in {"python", "npm"}:
        return {
            **_result(library, normalized_ecosystem or "unknown", []),
            "status": "unsupported_ecosystem",
            "message": "Automatic registry discovery is available for Python, npm, Pub/Dart, Go, and Rust. Provide docs_url manually for this ecosystem.",
        }

    endpoint = _registry_endpoint(name, normalized_ecosystem, selected_version)
    try:
        with httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "docmancer/1.0 (+https://github.com/Vanilla1999/DocAtlas)"},
        ) as client:
            response = client.get(endpoint)
    except httpx.RequestError:
        return {**_result(library, normalized_ecosystem, []), "status": "registry_unavailable", "retryable": True}
    if response.status_code != 200:
        return {
            **_result(library, normalized_ecosystem, []),
            "status": "package_not_found" if response.status_code == 404 else "registry_error",
            "http_status": response.status_code,
            "retryable": response.status_code >= 500 or response.status_code == 429,
        }
    if len(response.content) > _MAX_METADATA_BYTES:
        return {**_result(library, normalized_ecosystem, []), "status": "registry_metadata_too_large"}
    try:
        payload = response.json()
    except ValueError:
        return {**_result(library, normalized_ecosystem, []), "status": "invalid_registry_metadata"}

    candidates = (
        _python_candidates(payload, library, selected_version)
        if normalized_ecosystem == "python"
        else _npm_candidates(payload, library, selected_version)
    )
    result = _result(library, normalized_ecosystem, candidates)
    if not candidates:
        result.update(
            status="needs_manual_docs_url",
            message="The registry package exists but does not publish an authoritative documentation URL. Ask the user for docs_url.",
        )
    return result


def _registry_endpoint(name: str, ecosystem: str, version: str | None) -> str:
    encoded = quote(name, safe="@")
    if ecosystem == "python":
        suffix = f"/{quote(version, safe='')}" if version else ""
        return f"https://pypi.org/pypi/{encoded}{suffix}/json"
    suffix = f"/{quote(version, safe='')}" if version else "/latest"
    return f"https://registry.npmjs.org/{encoded}{suffix}"


def _python_candidates(payload: Any, library: str, version: str | None) -> list[dict[str, Any]]:
    info = payload.get("info") if isinstance(payload, dict) else None
    if not isinstance(info, dict):
        return []
    project_urls = info.get("project_urls") if isinstance(info.get("project_urls"), dict) else {}
    ranked: list[tuple[int, str, str]] = []
    for label, raw_url in project_urls.items():
        if not isinstance(raw_url, str) or not _safe_public_url(raw_url):
            continue
        normalized_label = str(label).casefold()
        rank = 0 if any(term in normalized_label for term in ("documentation", "docs", "reference")) else 2
        if any(term in normalized_label for term in ("homepage", "home")):
            rank = 1
        ranked.append((rank, str(label), raw_url))
    home_page = info.get("home_page")
    if isinstance(home_page, str) and _safe_public_url(home_page):
        ranked.append((1, "Project homepage", home_page))
    return _dedupe_candidates([
        _candidate(
            url,
            label=label,
            confidence="high" if rank == 0 else "medium",
            source="pypi_project_metadata",
            ecosystem="python",
            version=version,
            source_type="web",
            library=library,
        )
        for rank, label, url in sorted(ranked)
    ])


def _npm_candidates(payload: Any, library: str, version: str | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    rows: list[tuple[str, str, str]] = []
    homepage = payload.get("homepage")
    if isinstance(homepage, str) and _safe_public_url(homepage):
        rows.append(("Package homepage", homepage, "high"))
    repository = payload.get("repository")
    repository_url = repository.get("url") if isinstance(repository, dict) else repository
    normalized_repository = _normalize_repository_url(repository_url)
    if normalized_repository:
        rows.append(("Source repository", normalized_repository, "medium"))
    return _dedupe_candidates([
        _candidate(
            url,
            label=label,
            confidence=confidence,
            source="npm_registry_metadata",
            ecosystem="npm",
            version=version,
            source_type="web",
            library=library,
        )
        for label, url, confidence in rows
    ])


def _normalize_repository_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    url = value.strip()
    for prefix in ("git+", "git://"):
        if url.startswith(prefix):
            url = "https://" + url[len(prefix):].removeprefix("https://")
    url = url.removesuffix(".git")
    return url if _safe_public_url(url) else None


def _safe_public_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def _safe_go_module(value: str) -> bool:
    if not value or len(value) > 500 or value.startswith((".", "/")) or ".." in value:
        return False
    if "://" in value or "@" in value or any(char.isspace() for char in value):
        return False
    first = value.split("/", 1)[0]
    return "." in first and all(char.isalnum() or char in ".-_/~" for char in value)


def _candidate(
    docs_url: str,
    *,
    label: str,
    confidence: str,
    source: str,
    ecosystem: str,
    version: str | None,
    source_type: str,
    library: str | None = None,
) -> dict[str, Any]:
    arguments_patch = {
        "action": "prefetch_library_docs",
        "library": library,
        "ecosystem": ecosystem,
        "version": version,
        "source_type": source_type,
        "docs_url": docs_url,
    }
    return {
        "label": label,
        "docs_url": docs_url,
        "confidence": confidence,
        "discovered_from": source,
        "requires_confirmation": True,
        "arguments_patch": {key: value for key, value in arguments_patch.items() if value is not None},
    }


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = str(candidate.get("docs_url") or "")
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(candidate)
        if len(result) >= 5:
            break
    return result


def _result(library: str, ecosystem: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    # Fill deterministic registry candidates after construction.
    for candidate in candidates:
        candidate.get("arguments_patch", {}).setdefault("library", library)
    return {
        "tool": "prepare_docs",
        "action": "discover_library_docs",
        "status": "candidates_found" if candidates else "not_found",
        "library": library,
        "ecosystem": ecosystem,
        "candidates": candidates,
        "requires_confirmation": bool(candidates),
        "next_action": (
            {
                "tool": "prepare_docs",
                "arguments_patch": candidates[0]["arguments_patch"],
                "requires_confirmation": True,
            }
            if candidates else None
        ),
    }
