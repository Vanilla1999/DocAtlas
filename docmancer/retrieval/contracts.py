"""Versioned internal contracts for deterministic contextual retrieval."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping


CONTEXT_SCHEMA_VERSION = "deterministic-context-v2"
SYMBOL_EXTRACTOR_VERSION = "retrieval-symbols-v1"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ContextConfig:
    schema_version: str = CONTEXT_SCHEMA_VERSION
    max_prefix_bytes: int = 1024
    max_prefix_tokens: int = 192
    allowed_fields: tuple[str, ...] = (
        "document_title",
        "canonical_location",
        "heading_path",
        "library",
        "resolved_version",
        "version_family",
        "project_module",
        "project_scope",
        "source_class",
        "authority",
        "symbol_aliases",
        "catalog_description",
    )
    symbol_extractor_version: str = SYMBOL_EXTRACTOR_VERSION

    def __post_init__(self) -> None:
        if self.max_prefix_bytes < 0 or self.max_prefix_tokens < 0:
            raise ValueError("context prefix limits cannot be negative")
        if len(set(self.allowed_fields)) != len(self.allowed_fields):
            raise ValueError("context allowed_fields cannot contain duplicates")

    @property
    def config_hash(self) -> str:
        return canonical_hash({
            "schema_version": self.schema_version,
            "max_prefix_bytes": self.max_prefix_bytes,
            "max_prefix_tokens": self.max_prefix_tokens,
            "allowed_fields": list(self.allowed_fields),
            "symbol_extractor_version": self.symbol_extractor_version,
        })


@dataclass(frozen=True, slots=True)
class ContextField:
    name: str
    normalized_value: str
    provenance: str
    priority: int

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("context field name cannot be empty")
        if not self.provenance.strip():
            raise ValueError("context field provenance cannot be empty")
        if self.priority < 0:
            raise ValueError("context field priority cannot be negative")

    def manifest_entry(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.normalized_value,
            "provenance": self.provenance,
            "priority": self.priority,
        }


@dataclass(frozen=True, slots=True)
class ContextPrefix:
    text: str
    fields: tuple[ContextField, ...]
    schema_version: str
    config_hash: str
    content_hash: str
    token_estimate: int
    truncated: bool

    def __post_init__(self) -> None:
        if self.token_estimate < 0:
            raise ValueError("context token estimate cannot be negative")
        expected = canonical_hash([field.manifest_entry() for field in self.fields])
        if self.content_hash != expected:
            raise ValueError("context content hash does not match its field manifest")

    def manifest(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "config_hash": self.config_hash,
            "content_hash": self.content_hash,
            "token_estimate": self.token_estimate,
            "truncated": self.truncated,
            "fields": [field.manifest_entry() for field in self.fields],
        }


@dataclass(frozen=True, slots=True)
class ExactTerm:
    value: str
    normalized_value: str
    kind: str


@dataclass(frozen=True, slots=True)
class FilterSpec:
    project_identity: str | None = None
    library_id: str | None = None
    resolved_version: str | None = None
    version_family: str | None = None
    source_classes: tuple[str, ...] = ()
    minimum_authority: str | None = None
    module_ids: tuple[str, ...] = ()
    doc_scopes: tuple[str, ...] = ()
    exact_snapshot_required: bool = False
    forbidden_sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QueryPlan:
    original_query_hash: str
    exact_terms: tuple[ExactTerm, ...]
    concept_queries: tuple[str, ...]
    filters: FilterSpec
    requested_lanes: tuple[str, ...]
    executed_filters_hash: str
    plan_hash: str


@dataclass(frozen=True, slots=True)
class CandidateHit:
    stable_child_id: str
    hydration_id: int
    vector_id: str | None
    component: str
    component_rank: int
    raw_score: float | None
    source_identity: str
    filter_proof: Mapping[str, Any] = field(default_factory=dict)
    collection_identity: str | None = None

    def __post_init__(self) -> None:
        if not self.stable_child_id.strip():
            raise ValueError("candidate stable_child_id cannot be empty")
        if self.component_rank < 1:
            raise ValueError("candidate component_rank must be positive")


@dataclass(slots=True)
class CandidatePool:
    candidates: list[CandidateHit]
    query_plan_hash: str
    fusion_config_hash: str
    component_counts: dict[str, int]
    failures: dict[str, str]
    degraded_mode: str | None = None


__all__ = [
    "CONTEXT_SCHEMA_VERSION",
    "SYMBOL_EXTRACTOR_VERSION",
    "CandidateHit",
    "CandidatePool",
    "ContextConfig",
    "ContextField",
    "ContextPrefix",
    "ExactTerm",
    "FilterSpec",
    "QueryPlan",
    "canonical_hash",
]
