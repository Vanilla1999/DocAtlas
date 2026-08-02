"""Deterministic evidence policy for documentation source decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlparse


_OFFICIAL_AUTHORITIES = {"official_registry", "official_product", "official_project"}
_EXACT_SOURCES = {
    "lockfile_exact", "uv.lock_exact", "poetry.lock_exact", "pdm.lock_exact",
    "pipfile.lock_exact", "gradle.lockfile_exact", "vendor_modules_exact",
}
_REGISTRY_HOSTS = {
    "go": {"pkg.go.dev"},
    "pub": {"pub.dev"},
    "dart": {"pub.dev", "api.flutter.dev", "main-api.flutter.dev"},
    "flutter": {"pub.dev", "api.flutter.dev", "main-api.flutter.dev"},
    "rust": {"docs.rs"},
}


@dataclass(frozen=True)
class EvidenceDimension:
    status: str
    evidence: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentationEvidenceReport:
    decision: str
    identity: EvidenceDimension
    authority: EvidenceDimension
    version: EvidenceDimension
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_documentation_evidence(
    *,
    library: str,
    ecosystem: str | None,
    docs_url: str | None,
    authority: str | None,
    requested_version: str | None,
    version_binding: str | None,
    version_source: str | None = None,
    discovered_from: str | None = None,
) -> DocumentationEvidenceReport:
    """Return accept/confirm/reject without inventing a numeric confidence score."""

    identity_evidence: list[str] = []
    identity_conflicts: list[str] = []
    identity_missing: list[str] = []
    if library.strip() and ecosystem:
        identity_evidence.append(f"declared:{ecosystem}:{library}")
    else:
        identity_missing.append("package identity is incomplete")
    if discovered_from:
        identity_evidence.append(f"registry_metadata:{discovered_from}")
    parsed = urlparse(docs_url or "")
    if docs_url and (parsed.scheme != "https" or not parsed.hostname):
        identity_conflicts.append("documentation URL is not a safe HTTPS origin")

    authority_evidence = [authority] if authority else []
    authority_conflicts: list[str] = []
    authority_status = "confirmed" if authority in _OFFICIAL_AUTHORITIES else "unconfirmed"
    expected_hosts = _REGISTRY_HOSTS.get(str(ecosystem or "").casefold())
    if authority == "official_registry" and expected_hosts and parsed.hostname not in expected_hosts:
        authority_status = "rejected"
        authority_conflicts.append(
            f"official registry authority conflicts with origin {parsed.hostname or 'missing'}"
        )
    if not authority:
        authority_conflicts.append("source authority has not been established")

    version_evidence: list[str] = []
    version_conflicts: list[str] = []
    version_status = "unconfirmed"
    if version_binding in {"rolling", "channel"}:
        version_status = "confirmed"
        version_evidence.append(f"binding:{version_binding}")
    elif version_binding == "exact":
        if version_source in _EXACT_SOURCES:
            version_status = "confirmed"
            version_evidence.append(f"resolved:{version_source}")
        elif requested_version and requested_version in (docs_url or ""):
            version_status = "confirmed"
            version_evidence.append("version appears in documentation URL")
        else:
            version_conflicts.append("exact version binding lacks resolution evidence")
    else:
        version_conflicts.append("documentation version binding is unconfirmed")

    identity_status = (
        "rejected" if identity_conflicts else
        ("unconfirmed" if identity_missing else "confirmed")
    )
    if identity_status == "rejected" or authority_status == "rejected":
        decision = "reject"
    elif authority_status == "confirmed" and version_status == "confirmed":
        decision = "accept"
    else:
        decision = "confirm"
    reasons = [*identity_conflicts, *identity_missing, *authority_conflicts, *version_conflicts]
    return DocumentationEvidenceReport(
        decision=decision,
        identity=EvidenceDimension(identity_status, identity_evidence, [*identity_conflicts, *identity_missing]),
        authority=EvidenceDimension(authority_status, authority_evidence, authority_conflicts),
        version=EvidenceDimension(version_status, version_evidence, version_conflicts),
        reasons=reasons,
    )
