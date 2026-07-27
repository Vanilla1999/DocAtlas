"""Validation and canonicalization for immutable GitHub directory manifests."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import PurePosixPath
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import quote, unquote, urlparse


_GITHUB_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?$")
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_DOC_SUFFIXES = frozenset({".md", ".mdx"})


class GitHubSourceManifestError(ValueError):
    """Raised when a GitHub source manifest violates its immutable scope."""


class GitHubApiClient(Protocol):
    def get(self, url: str, **kwargs: Any) -> Any: ...


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise GitHubSourceManifestError(f"{field} is required")
    return text


def _github_name(value: Any, field: str) -> str:
    text = _required_text(value, field)
    if _GITHUB_NAME.fullmatch(text) is None:
        raise GitHubSourceManifestError(f"invalid {field}")
    return text


def _normalized_relative_path(value: Any, field: str) -> str:
    text = _required_text(value, field)
    if "\\" in text or "%" in text or "\x00" in text or text.startswith("/"):
        raise GitHubSourceManifestError(f"invalid {field}")
    path = PurePosixPath(text)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise GitHubSourceManifestError(f"invalid {field}")
    normalized = path.as_posix()
    if normalized != text:
        raise GitHubSourceManifestError(f"non-canonical {field}")
    return normalized


def _hex_40(value: Any, field: str) -> str:
    text = _required_text(value, field).lower()
    if _HEX_40.fullmatch(text) is None:
        raise GitHubSourceManifestError(f"invalid {field}")
    return text


def _document_identity(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    discovery = manifest["discovery"]
    scope = {
        "owner": discovery["owner"],
        "repository": discovery["repository"],
        "resolved_commit_sha": discovery["resolved_commit_sha"],
        "directory": discovery["directory"],
    }
    return [scope, *[
        {
            "owner": discovery["owner"],
            "repository": discovery["repository"],
            "resolved_commit_sha": discovery["resolved_commit_sha"],
            "path": document["path"],
            "git_blob_sha": document["git_blob_sha"],
            "size": document["size"],
        }
        for document in manifest["documents"]
    ]]


def canonical_manifest_digest(manifest: Mapping[str, Any]) -> str:
    """Hash only immutable repository, commit, path, blob, and size identity."""

    payload = json.dumps(
        _document_identity(manifest),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_github_blob_scope_url(url: str, discovery: Mapping[str, Any]) -> bool:
    """Return whether *url* is an exact canonical blob file within the manifest scope."""

    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment:
        return False
    prefix = (
        f"/{discovery['owner']}/{discovery['repository']}/blob/"
        f"{quote(str(discovery['requested_ref']), safe='')}/"
        f"{quote(str(discovery['directory']), safe='/')}/"
    )
    file_path = parsed.path.removeprefix(prefix) if parsed.path.startswith(prefix) else ""
    return bool(
        file_path
        and not file_path.endswith("/")
        and quote(unquote(file_path), safe="/") == file_path
    )


def normalize_resolved_github_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and canonicalize a complete, already-resolved schema-v2 manifest."""

    if value.get("schema_version") != 2:
        raise GitHubSourceManifestError("schema_version must be 2")
    for field in ("official", "complete", "truncated"):
        if type(value.get(field)) is not bool:
            raise GitHubSourceManifestError(f"{field} must be a boolean")
    if value["official"] is not True:
        raise GitHubSourceManifestError("official must be true")
    if value["complete"] is True and value["truncated"] is True:
        raise GitHubSourceManifestError("complete manifest cannot be truncated")
    raw_discovery = value.get("discovery")
    if not isinstance(raw_discovery, Mapping) or raw_discovery.get("kind") != "github_directory":
        raise GitHubSourceManifestError("discovery.kind must be github_directory")

    owner = _github_name(raw_discovery.get("owner"), "owner")
    repository = _github_name(raw_discovery.get("repository"), "repository")
    requested_ref = _required_text(raw_discovery.get("requested_ref"), "requested_ref")
    commit = _hex_40(raw_discovery.get("resolved_commit_sha"), "resolved_commit_sha")
    directory = _normalized_relative_path(raw_discovery.get("directory"), "directory")

    raw_documents = value.get("documents")
    if not isinstance(raw_documents, list):
        raise GitHubSourceManifestError("documents must be a list")
    documents: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    prefix = f"{directory}/"
    for raw_document in raw_documents:
        if not isinstance(raw_document, Mapping):
            raise GitHubSourceManifestError("document must be an object")
        if "type" in raw_document and raw_document.get("type") != "file":
            raise GitHubSourceManifestError("document must be a regular file")
        if "owner" in raw_document and raw_document.get("owner") != owner:
            raise GitHubSourceManifestError("document owner does not match manifest scope")
        if "repository" in raw_document and raw_document.get("repository") != repository:
            raise GitHubSourceManifestError("document repository does not match manifest scope")
        if "resolved_commit_sha" in raw_document:
            document_commit = _hex_40(
                raw_document.get("resolved_commit_sha"), "document resolved_commit_sha"
            )
            if document_commit != commit:
                raise GitHubSourceManifestError(
                    "document resolved_commit_sha does not match manifest scope"
                )
        path = _normalized_relative_path(raw_document.get("path"), "document path")
        if not path.startswith(prefix) or path == directory:
            raise GitHubSourceManifestError("document path is outside directory")
        if PurePosixPath(path).suffix.lower() not in _DOC_SUFFIXES:
            raise GitHubSourceManifestError("document is not markdown")
        if path in seen_paths:
            raise GitHubSourceManifestError("duplicate document path")
        seen_paths.add(path)
        blob_sha = _hex_40(raw_document.get("git_blob_sha"), "git_blob_sha")
        size = raw_document.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise GitHubSourceManifestError("invalid document size")
        encoded_path = quote(path, safe="/")
        documents.append(
            {
                "path": path,
                "git_blob_sha": blob_sha,
                "size": size,
                "blob_url": f"https://github.com/{owner}/{repository}/blob/{commit}/{encoded_path}",
                "raw_url": f"https://raw.githubusercontent.com/{owner}/{repository}/{commit}/{encoded_path}",
            }
        )
    documents.sort(key=lambda document: document["path"])

    normalized: dict[str, Any] = {
        "schema_version": 2,
        "official": value["official"],
        "discovery": {
            "kind": "github_directory",
            "owner": owner,
            "repository": repository,
            "requested_ref": requested_ref,
            "resolved_commit_sha": commit,
            "directory": directory,
        },
        "documents": documents,
        "complete": value.get("complete") is True,
        "truncated": value.get("truncated") is True,
    }
    normalized["digest"] = canonical_manifest_digest(normalized)
    supplied_digest = value.get("digest")
    if supplied_digest is not None and supplied_digest != normalized["digest"]:
        raise GitHubSourceManifestError("manifest digest mismatch")
    return normalized


def resolve_github_directory_manifest(
    client: GitHubApiClient, *, owner: str, repository: str, requested_ref: str,
    directory: str, official: bool = True, max_api_requests: int = 50,
    max_directory_depth: int = 8, max_entries_seen: int = 10_000,
    max_api_response_bytes: int = 8 * 1024 * 1024, max_total_seconds: float = 30.0,
    max_accepted_documents: int = 2_000,
    cancellation_callback: Callable[[], bool] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Resolve a ref then traverse its Contents tree under independent bounds."""
    owner = _github_name(owner, "owner")
    repository = _github_name(repository, "repository")
    if official is not True:
        raise GitHubSourceManifestError("official must be true")
    requested_ref = _required_text(requested_ref, "requested_ref")
    directory = _normalized_relative_path(directory, "directory")
    started = monotonic()
    requests = entries_seen = response_bytes = 0
    documents: list[dict[str, Any]] = []
    commit = ""

    def partial(reason: str) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema_version": 2, "official": official,
            "discovery": {"kind": "github_directory", "owner": owner,
                "repository": repository, "requested_ref": requested_ref,
                "resolved_commit_sha": commit, "directory": directory},
            "documents": documents, "complete": False, "truncated": True,
            "reason_code": reason,
        }
        if not commit:
            value["digest"] = ""
            return value
        normalized = normalize_resolved_github_manifest(value)
        normalized["reason_code"] = reason
        return normalized

    def request(url: str) -> tuple[Any | None, str | None]:
        nonlocal requests, response_bytes
        if cancellation_callback and cancellation_callback():
            return None, "cancelled"
        if monotonic() - started >= max_total_seconds:
            return None, "deadline_exceeded"
        if requests >= max_api_requests:
            return None, "max_api_requests"
        requests += 1
        try:
            remaining_seconds = max_total_seconds - (monotonic() - started)
            if remaining_seconds <= 0:
                return None, "deadline_exceeded"
            response = client.get(url, timeout=remaining_seconds)
            if cancellation_callback and cancellation_callback():
                return None, "cancelled"
            if monotonic() - started >= max_total_seconds:
                return None, "deadline_exceeded"
            response_bytes += len(bytes(response.content))
            if response_bytes > max_api_response_bytes:
                return None, "max_api_response_bytes"
            status = int(response.status_code)
            if status in {403, 429}:
                return None, "rate_limited"
            if status != 200:
                return None, "api_http_failure"
            return response.json(), None
        except Exception:
            return None, "malformed_response"

    payload, reason = request(
        f"https://api.github.com/repos/{owner}/{repository}/commits/{quote(requested_ref, safe='')}"
    )
    if reason:
        return partial(reason)
    if not isinstance(payload, Mapping):
        return partial("malformed_response")
    try:
        commit = _hex_40(payload.get("sha"), "resolved_commit_sha")
    except GitHubSourceManifestError:
        return partial("malformed_ref")

    queue: list[tuple[str, int]] = [(directory, 0)]
    listed_paths: set[str] = set()
    while queue:
        current, depth = queue.pop(0)
        if depth > max_directory_depth:
            return partial("max_directory_depth")
        payload, reason = request(
            f"https://api.github.com/repos/{owner}/{repository}/contents/"
            f"{quote(current, safe='/')}?ref={commit}"
        )
        if reason:
            return partial(reason)
        if not isinstance(payload, list):
            return partial("malformed_listing")
        if len(payload) >= 1000:
            return partial("ambiguous_listing")
        entries_seen += len(payload)
        if entries_seen > max_entries_seen:
            return partial("max_entries_seen")
        for entry in payload:
            if cancellation_callback and cancellation_callback():
                return partial("cancelled")
            if not isinstance(entry, Mapping):
                return partial("malformed_entry")
            try:
                path = _normalized_relative_path(entry.get("path"), "entry path")
                if path in listed_paths:
                    return partial("duplicate_entry")
                listed_paths.add(path)
                if not path.startswith(f"{directory}/"):
                    raise GitHubSourceManifestError("outside scope")
                kind = entry.get("type")
                if kind == "dir":
                    _hex_40(entry.get("sha"), "directory sha")
                    queue.append((path, depth + 1))
                    continue
                if kind != "file":
                    return partial("unsupported_entry_type")
                if PurePosixPath(path).suffix.lower() not in _DOC_SUFFIXES:
                    continue
                sha = _hex_40(entry.get("sha"), "git_blob_sha")
                size = entry.get("size")
                if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                    raise GitHubSourceManifestError("invalid size")
            except GitHubSourceManifestError:
                return partial("malformed_entry")
            if len(documents) >= max_accepted_documents:
                return partial("max_accepted_documents")
            documents.append({"path": path, "git_blob_sha": sha, "size": size})
    if cancellation_callback and cancellation_callback():
        return partial("cancelled")
    if monotonic() - started >= max_total_seconds:
        return partial("deadline_exceeded")
    return normalize_resolved_github_manifest({
        "schema_version": 2, "official": official,
        "discovery": {"kind": "github_directory", "owner": owner,
            "repository": repository, "requested_ref": requested_ref,
            "resolved_commit_sha": commit, "directory": directory},
        "documents": documents, "complete": True, "truncated": False,
    })


__all__ = [
    "GitHubSourceManifestError",
    "canonical_manifest_digest",
    "normalize_resolved_github_manifest",
    "resolve_github_directory_manifest",
]
