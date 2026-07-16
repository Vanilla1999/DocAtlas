"""Bounded, deterministic query analysis for contextual hybrid retrieval."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict
from typing import Any, Mapping

from docmancer.retrieval.contracts import (
    ExactTerm,
    FilterSpec,
    QueryPlan,
    canonical_hash,
)


QUERY_PLAN_SCHEMA_VERSION = "deterministic-query-plan-v1"
MAX_EXACT_TERMS = 12
MAX_CONCEPT_QUERIES = 3
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "be", "can", "do", "does", "for", "how",
    "i", "in", "is", "it", "of", "on", "or", "the", "this", "to",
    "what", "when", "where", "which", "with", "you", "your",
})
_TERM_PATTERNS = (
    ("quoted", re.compile(r"[`\"]([^`\"\n]{2,160})[`\"]")),
    ("flag", re.compile(r"(?<![\w.-])--[A-Za-z][A-Za-z0-9-]{1,118}")),
    ("error_code", re.compile(r"\b(?:ERR(?:OR)?[_-]?\d+|[A-Z][A-Z0-9]+[_-]\d+)\b")),
    ("config_key", re.compile(r"\b[A-Z][A-Z0-9_]{2,119}\b")),
    ("symbol", re.compile(r"\b[A-Za-z_]\w*(?:(?:::|\.)[A-Za-z_]\w*)+\b")),
    ("path", re.compile(r"(?<![\w/])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+")),
)

_AUTHORITY_MINIMUMS = {
    "unknown": (
        "unknown", "stale", "external_generic", "mirror", "generated",
        "community", "verified", "legal", "project_rule", "project_owned", "official",
    ),
    "community": ("community", "verified", "project_rule", "project_owned", "official"),
    "verified": ("verified", "project_rule", "project_owned", "official"),
    "project_rule": ("project_rule", "project_owned", "official"),
    "project_owned": ("project_owned", "official"),
    "official": ("official",),
    "legal": ("legal",),
}


def _strict_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return False


def _normalize_term(value: str) -> str:
    return " ".join(value.split()).casefold()[:160]


def _canonical_filter_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_filter_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_canonical_filter_value(item) for item in value),
            key=lambda item: canonical_hash(item),
        )
    if isinstance(value, (list, tuple)):
        return [_canonical_filter_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def extract_exact_terms(query: str) -> tuple[ExactTerm, ...]:
    found: list[ExactTerm] = []
    seen: set[str] = set()
    for kind, pattern in _TERM_PATTERNS:
        for match in pattern.finditer(query):
            value = match.group(1) if match.lastindex else match.group(0)
            value = " ".join(value.split())[:160]
            normalized = _normalize_term(value)
            if not normalized or normalized in seen:
                continue
            found.append(ExactTerm(value=value, normalized_value=normalized, kind=kind))
            seen.add(normalized)
            if len(found) >= MAX_EXACT_TERMS:
                return tuple(found)
    return tuple(found)


def _concept_queries(query: str, exact_terms: tuple[ExactTerm, ...]) -> tuple[str, ...]:
    cleaned = query
    for term in exact_terms:
        cleaned = cleaned.replace(term.value, " ")
    tokens = [
        token.casefold()
        for token in re.findall(r"[\w+-]+", cleaned, flags=re.UNICODE)
        if token.casefold() not in _STOPWORDS and len(token) > 1
    ]
    normalized = " ".join(tokens)[:320]
    return (normalized,) if normalized else ()


def _filter_spec(filters: Mapping[str, Any] | None) -> FilterSpec:
    filters = filters or {}

    def text(name: str) -> str | None:
        value = filters.get(name)
        return str(value).strip()[:240] if isinstance(value, (str, int)) and str(value).strip() else None

    def texts(name: str) -> tuple[str, ...]:
        value = filters.get(name)
        if isinstance(value, str):
            return (value[:240],)
        if isinstance(value, (list, tuple, set)):
            normalized = {
                str(item).strip()[:240] for item in value if str(item).strip()
            }
            return tuple(sorted(normalized))[:16]
        return ()

    return FilterSpec(
        project_identity=text("project_identity"),
        library_id=text("library_id"),
        resolved_version=text("resolved_version"),
        version_family=text("version_family"),
        source_classes=texts("source_class") or texts("source_classes"),
        minimum_authority=text("minimum_authority"),
        module_ids=texts("module_id") or texts("module_ids"),
        doc_scopes=texts("doc_scope") or texts("doc_scopes"),
        exact_snapshot_required=_strict_bool(filters.get("exact_snapshot_required", False)),
        forbidden_sources=texts("forbidden_sources"),
    )


def compile_backend_filters(filters: Mapping[str, Any] | None) -> dict[str, Any]:
    """Compile the public filter vocabulary to backend-positive predicates.

    Negative source predicates are deliberately enforced by the dispatcher after
    every lane; neither sqlite-vec nor all supported Qdrant versions expose the
    same portable negative-filter contract.
    """
    raw = dict(filters or {})
    spec = _filter_spec(raw)
    for alias in (
        "source_classes", "module_ids", "doc_scopes", "minimum_authority",
        "exact_snapshot_required", "forbidden_sources",
    ):
        raw.pop(alias, None)
    if spec.source_classes:
        raw["source_class"] = {"in": list(spec.source_classes)}
    if spec.module_ids:
        raw["module_id"] = {"in": list(spec.module_ids)}
    if spec.doc_scopes:
        raw["doc_scope"] = {"in": list(spec.doc_scopes)}
    if spec.exact_snapshot_required:
        raw["docs_snapshot_exact"] = True
    if spec.minimum_authority:
        minimum = spec.minimum_authority.casefold().replace("-", "_")
        raw["authority"] = {"in": list(_AUTHORITY_MINIMUMS.get(minimum, ()))}
    return raw


def metadata_matches_filters(
    metadata: Mapping[str, Any],
    filters: Mapping[str, Any] | None,
    *,
    source: str = "",
) -> bool:
    """Defense-in-depth evaluator shared by lexical and vector results."""
    spec = _filter_spec(filters)
    values = dict(metadata)
    values.setdefault("source", source)
    for key, expected in compile_backend_filters(filters).items():
        actual = values.get(key)
        if isinstance(expected, Mapping) and "in" in expected:
            if actual not in expected["in"]:
                return False
        elif isinstance(expected, (list, tuple, set, frozenset)):
            if actual not in expected:
                return False
        elif isinstance(expected, bool):
            if _strict_bool(actual) != expected:
                return False
        elif actual != expected:
            return False
    forbidden = {item.strip().casefold() for item in spec.forbidden_sources if item.strip()}
    identities = {
        str(source or "").strip().casefold(),
        str(values.get("source") or "").strip().casefold(),
        str(values.get("source_identity") or "").strip().casefold(),
        str(values.get("canonical_url") or "").strip().casefold(),
        str(values.get("source_url") or "").strip().casefold(),
        str(values.get("library_id") or "").strip().casefold(),
        str(values.get("canonical_id") or "").strip().casefold(),
        str(values.get("path") or "").strip().casefold(),
        str(values.get("project_doc_path") or "").strip().casefold(),
        str(values.get("source_path") or "").strip().casefold(),
    }
    return not bool(forbidden.intersection(identities))


def build_query_plan(
    query: str,
    *,
    filters: Mapping[str, Any] | None = None,
    requested_lanes: tuple[str, ...] = ("lexical",),
) -> QueryPlan:
    exact_terms = extract_exact_terms(query)
    concepts = _concept_queries(query, exact_terms)[:MAX_CONCEPT_QUERIES]
    filter_spec = _filter_spec(filters)
    executed_filters_hash = canonical_hash(_canonical_filter_value(filters or {}))
    original_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
    payload = {
        "schema_version": QUERY_PLAN_SCHEMA_VERSION,
        "original_query_hash": original_hash,
        "exact_terms": [asdict(term) for term in exact_terms],
        "concept_queries": list(concepts),
        "filters": asdict(filter_spec),
        "executed_filters_hash": executed_filters_hash,
        "requested_lanes": list(requested_lanes),
    }
    return QueryPlan(
        original_query_hash=original_hash,
        exact_terms=exact_terms,
        concept_queries=concepts,
        filters=filter_spec,
        requested_lanes=requested_lanes,
        executed_filters_hash=executed_filters_hash,
        plan_hash=canonical_hash(payload),
    )


__all__ = [
    "MAX_CONCEPT_QUERIES",
    "MAX_EXACT_TERMS",
    "QUERY_PLAN_SCHEMA_VERSION",
    "build_query_plan",
    "compile_backend_filters",
    "extract_exact_terms",
    "metadata_matches_filters",
]
