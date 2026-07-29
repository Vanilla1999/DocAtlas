"""Pure manifest, diagnostics, and failure policy for library refreshes."""

from __future__ import annotations

import re
from typing import Any

import httpx

from docmancer.docs.dart_official_docs import build_dart_diagnostics, canonical_dart_ecosystem
from docmancer.docs.fetch_policy import DocsFetchSecurityError, redact_url
from docmancer.docs.models import MANIFEST_INGESTION_POLICY_VERSION
from docmancer.docs.registry import LibraryRecord


_SAFE_EXCEPTION_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_MAX_EXCEPTION_TYPE_CHARS = 200
_MAX_EXCEPTION_MESSAGE_CHARS = 1000
_MAX_EXCEPTION_TRACEBACK_CHARS = 4000
_REDACTED_EXCEPTION_TYPE = "<redacted exception type>"
_REDACTED_DIAGNOSTIC_TEXT = "<redacted diagnostic text>"
_REDACTED_TRACEBACK = "<redacted traceback>"


def refresh_failure_code(exc: Exception) -> str:
    if isinstance(exc, DocsFetchSecurityError):
        return exc.category
    if isinstance(exc, httpx.ConnectTimeout):
        return "connect_timeout"
    if isinstance(exc, httpx.ReadTimeout):
        return "read_timeout"
    if isinstance(exc, httpx.TimeoutException):
        return "network_timeout"
    if isinstance(exc, httpx.ConnectError):
        return "network_unreachable"
    if isinstance(exc, httpx.TransportError):
        return "network_transport_error"
    if isinstance(exc, httpx.HTTPStatusError):
        return "http_failure"
    return "extraction_failed" if "extract" in str(exc).lower() else "indexing_failed"


def retryable_failure(exc: Exception, reason_code: str) -> bool:
    if isinstance(exc, DocsFetchSecurityError):
        return exc.retryable
    return reason_code in {
        "dns_failure", "network_unreachable", "connect_timeout", "read_timeout",
        "tls_failure", "network_timeout", "network_transport_error",
    }


def safe_failure_message(exc: Exception, reason_code: str) -> str:
    return f"{reason_code}: {exc.failed_url}" if isinstance(exc, DocsFetchSecurityError) else reason_code


def bounded_exception_diagnostics(
    exc: Exception,
    *,
    failure_phase: str,
    failure_operation: str,
) -> dict[str, str]:
    """Return bounded, secret-safe exception evidence for durable job reporting."""
    return {
        "failure_phase": failure_phase,
        "failure_operation": failure_operation,
        "exception_type": _safe_exception_type(exc)[:_MAX_EXCEPTION_TYPE_CHARS],
        "exception_message": _safe_exception_message(exc)[:_MAX_EXCEPTION_MESSAGE_CHARS],
        "exception_traceback": _REDACTED_TRACEBACK[:_MAX_EXCEPTION_TRACEBACK_CHARS],
    }


def _safe_exception_type(exc: Exception) -> str:
    name = type(exc).__name__
    return name if _SAFE_EXCEPTION_TYPE.fullmatch(name) else _REDACTED_EXCEPTION_TYPE


def _safe_exception_message(exc: Exception) -> str:
    if isinstance(exc, DocsFetchSecurityError):
        return f"{exc.category}: {redact_url(exc.failed_url)}"
    return _REDACTED_DIAGNOSTIC_TEXT


def merged_discovery_diagnostics(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {
            "discovery_strategy": "unknown", "sitemap_pages": 0, "seed_pages": 0,
            "fallback_pages": 0, "warnings": [], "page_ledger": [],
            "page_failure_count": 0, "page_failure_summary": [],
        }
    strategies: list[str] = []
    fallback_reasons: list[str] = []
    page_ledger: list[dict[str, Any]] = []
    sitemap_pages = seed_pages = fallback_pages = 0
    for item in items:
        strategy = item.get("discovery_strategy")
        if strategy and str(strategy) not in strategies:
            strategies.append(str(strategy))
        sitemap_pages += int(item.get("sitemap_pages") or 0)
        seed_pages += int(item.get("seed_pages") or 0)
        fallback_pages += int(item.get("fallback_pages") or 0)
        reason = item.get("fallback_reason")
        if reason and str(reason) not in fallback_reasons:
            fallback_reasons.append(str(reason))
        page_ledger.extend(dict(page) for page in item.get("page_ledger") or [] if isinstance(page, dict))
    failed = [page for page in page_ledger if page.get("outcome") in {"failed", "skipped"}]
    return {
        "discovery_strategy": "+".join(strategies) if strategies else "unknown",
        "sitemap_pages": sitemap_pages,
        "seed_pages": seed_pages,
        "fallback_pages": fallback_pages,
        "warnings": [{"code": reason, "blocking": False} for reason in fallback_reasons],
        "page_ledger": page_ledger[:200],
        "page_failure_count": len(failed),
        "page_failure_summary": [
            {"url": page.get("discovered_url"), "reason_code": page.get("reason_code")}
            for page in failed[:20]
        ],
    }


def dart_refresh_diagnostics(
    record: LibraryRecord,
    *,
    pages_discovered: int | None,
    pages_extracted: int | None,
    chunks_created: int | None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    if canonical_dart_ecosystem(record.ecosystem) != "dart":
        return {}
    return {"dartdoc": build_dart_diagnostics(
        package=record.name,
        version=record.version,
        root_url=record.docs_url,
        pages_discovered=pages_discovered,
        pages_extracted=pages_extracted,
        chunks_created=chunks_created,
        used_official_docs=bool(record.docs_url and "pub.dev" not in record.docs_url),
        reason_code=reason_code,
    )}


def metadata_for_record(record: LibraryRecord) -> dict[str, Any]:
    metadata = {
        "library_id": record.library_id,
        "canonical_id": record.canonical_id,
        "ecosystem": record.ecosystem,
        "source_type": record.source_type,
        "docs_url": record.docs_url,
        "docs_url_resolved": record.docs_url_resolved or record.docs_url,
        "registry_docset_root": record.docs_url_resolved or record.docs_url,
        "requested_version": record.requested_version,
        "resolved_version": record.resolved_version,
        "version_binding": (record.target_spec or {}).get("dart_docs", {}).get("version_binding"),
        "docs_snapshot_exact": record.docs_snapshot_exact,
    }
    if record.docs_snapshot_exact is not False and record.version:
        metadata["version"] = record.version
    return {key: value for key, value in metadata.items() if value is not None}


def manifest_attempt_spec(target_spec: dict | None) -> dict:
    spec = dict(target_spec or {})
    manifest = spec.get("source_manifest") or {}
    digest = manifest.get("digest") if manifest.get("schema_version") == 2 else None
    if digest:
        spec["last_attempt_manifest_digest"] = digest
    return spec


def rollback_safe_manifest_spec(target_spec: dict | None) -> dict:
    spec = dict(target_spec or {})
    active_manifest = spec.pop("active_source_manifest", None)
    if active_manifest is not None:
        spec["source_manifest"] = active_manifest
    return spec


def manifest_rollback_spec(target_spec: dict | None, reason_code: str) -> dict:
    spec = rollback_safe_manifest_spec(target_spec)
    attempted_digest = spec.get("last_attempt_manifest_digest")
    if attempted_digest:
        spec["last_attempt_manifest_diagnostics"] = {
            "attempted_manifest_digest": attempted_digest,
            "reason_code": reason_code,
        }
    return spec


def published_manifest_spec(target_spec: dict | None) -> dict:
    spec = dict(target_spec or {})
    spec.pop("active_source_manifest", None)
    manifest = spec.get("source_manifest") or {}
    digest = manifest.get("digest") if manifest.get("schema_version") == 2 else None
    if digest and manifest.get("complete") is True and not manifest.get("truncated"):
        spec["active_manifest_digest"] = digest
        spec["last_complete_manifest_digest"] = digest
        spec["ingestion_policy_version"] = MANIFEST_INGESTION_POLICY_VERSION
    return spec
