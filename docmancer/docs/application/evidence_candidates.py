"""Candidate normalization for deterministic evidence selection.

This module converts raw retrieval rows into immutable ``EvidenceCandidate``
objects.  It deliberately owns source/span/token normalization so selector
orchestration does not also carry input-shape policy.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Iterable, Literal, Mapping

from docmancer.docs.application.evidence_models import (
    EvidenceCandidate,
    EvidenceQualifier,
    Omission,
)
from docmancer.docs.domain.answer_units import extract_answer_units
from docmancer.retrieval.contracts import canonical_hash

_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def observed_qualifiers(text: str) -> tuple[EvidenceQualifier, ...]:
    """No semantic qualifiers are inferred from source wording."""
    return ()


def estimated_tokens(value: str) -> int:
    return max(1, math.ceil(len(value.encode("utf-8")) / 4))


def docs_answer_candidate_tokens(
    *, stable_id: str, path: str, section: str, projected: str,
    version_binding: str,
) -> int:
    source_row = {
        "evidence_id": stable_id,
        "path_or_url": path,
        "section": section,
        "snippet": projected,
        "version_binding": version_binding,
        "content_sha256": "0" * 64,
    }
    serialized_source = json.dumps(
        source_row, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return estimated_tokens(serialized_source) + estimated_tokens(projected)


def positive_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return parsed if parsed > 0 else default


def normalized_source(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").rstrip("/").casefold()


def requirement_value_visible(value: str, text: str) -> bool:
    """Match literal query terms at identifier boundaries; no derived aliases."""

    wanted = str(value or "").strip()
    haystack = str(text or "")
    if not wanted:
        return False
    if re.search(rf"(?<![\w]){re.escape(wanted)}(?![\w])", haystack, re.I):
        return True
    return False


def source_path(item: Mapping[str, Any]) -> str:
    value = item.get("source_url") or item.get("url") or item.get("path") or item.get("source") or ""
    if isinstance(value, Mapping):
        value = value.get("path") or value.get("source") or value.get("url") or ""
    return str(value).strip()


def section(item: Mapping[str, Any]) -> str:
    value = item.get("heading_path") or item.get("title") or item.get("section") or "document"
    if isinstance(value, Mapping):
        value = value.get("heading_path") or value.get("title") or "document"
    if isinstance(value, (list, tuple)):
        return " > ".join(str(part) for part in value)
    return str(value)


def display_text(item: Mapping[str, Any]) -> str:
    value = item.get("display_text") or item.get("code") or item.get("snippet") or item.get("content")
    if isinstance(value, Mapping):
        value = value.get("code") or value.get("content") or value.get("text")
    return str(value or "")


def _text(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("code") or value.get("content") or value.get("text")
    return str(value or "").strip()


def symbols(item: Mapping[str, Any]) -> tuple[str, ...]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
    values: list[Any] = []
    for source in (item, metadata):
        for key in ("symbols", "matched_symbols", "symbol_names", "symbol"):
            value = source.get(key)
            values.extend(value if isinstance(value, (list, tuple, set)) else [value] if value else [])
    names = [value.get("name") if isinstance(value, Mapping) else value for value in values]
    return tuple(dict.fromkeys(str(value) for value in names if str(value or "").strip()))


def projected_text(item: Mapping[str, Any], raw_display_text: str, result_kind: str) -> str:
    # Only the visible source window participates in assignment and cost.
    # Hidden content, paths and symbol metadata must not manufacture a quote.
    return raw_display_text


def authority(item: Mapping[str, Any]) -> str:
    packet_authority = str(item.get("_packet_authority") or "").casefold()
    if packet_authority:
        return "canonical" if packet_authority == "canonical" else "supporting"
    values = {
        str(item.get("authority") or "").casefold(),
        str(item.get("repository_authority") or "").casefold(),
    }
    return "canonical" if values & {
        "canonical", "source_of_truth", "explicit_agent_policy", "primary",
        "official", "project_owned", "project_rule",
    } else "supporting"


def version_binding(item: Mapping[str, Any]) -> str:
    return str(
        item.get("docs_exactness")
        or item.get("version_binding")
        or item.get("resolved_version")
        or item.get("version")
        or "not_applicable"
    ).strip()


def resolved_version(item: Mapping[str, Any]) -> str:
    return str(item.get("resolved_version") or item.get("version") or item.get("requested_version") or "").strip()


def version_rank(value: str) -> int:
    normalized = value.casefold().replace("-", "_")
    if normalized in {
        "exact", "exact_snapshot", "exact_version", "exact_version_indexed",
        "exact_version_url", "version_exact",
    }:
        return 0
    if normalized in {"", "unknown", "latest", "unversioned", "not_applicable"} or "fallback" in normalized:
        return 2
    return 1


def _span(item: Mapping[str, Any], name: str) -> tuple[int | None, int | None]:
    start, end = item.get(f"{name}_start"), item.get(f"{name}_end")
    packed = item.get(f"{name}_span")
    if (start is None or end is None) and isinstance(packed, (list, tuple)) and len(packed) == 2:
        start, end = packed
    try:
        return (int(start), int(end)) if start is not None and end is not None else (None, None)
    except (TypeError, ValueError):
        return None, None


def _span_was_supplied(item: Mapping[str, Any], name: str) -> bool:
    return any(key in item for key in (f"{name}_start", f"{name}_end", f"{name}_span"))


def identity_aliases(item: Mapping[str, Any], path: str) -> tuple[str, ...]:
    values = (
        item.get("source_identity"), path, item.get("source"), item.get("path"),
        item.get("url"), item.get("source_url"), item.get("canonical_id"),
        item.get("library_id"), item.get("library"),
    )
    return tuple(sorted({key for value in values if (key := normalized_source(value))}))


def normalize_candidates(
    items: Iterable[Mapping[str, Any]],
    *,
    result_kind: Literal["docs_answer", "patch_context"],
    include_soft_wrapped_prose: bool = False,
) -> tuple[list[EvidenceCandidate], list[Omission]]:
    candidates: list[EvidenceCandidate] = []
    omissions: list[Omission] = []
    for rank, raw in enumerate(items, start=1):
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        path, heading, display = source_path(item), section(item), display_text(item)
        digest = hashlib.sha256(display.encode("utf-8")).hexdigest()
        metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
        child_stable = str(
            item.get("stable_chunk_id")
            or item.get("stable_child_id")
            or metadata.get("stable_chunk_id")
            or ""
        )
        stable = child_stable or str(item.get("stable_id") or "")
        identity_kind = "stable_child" if child_stable else "legacy"
        source_class = str(item.get("source_class") or "")
        # A fake host-policy URI cannot waive indexed source identity checks.
        indexed_project_doc = source_class in {"project_doc", "project_file"} and bool(metadata)
        if indexed_project_doc and not child_stable:
            omissions.append(Omission(f"invalid:{rank}", "invalid_identity"))
            continue
        if not stable and path and display:
            stable = "legacy:" + canonical_hash({
                "path": path,
                "section": heading,
                "content": digest,
                "symbols": sorted(symbols(item)),
            })[:40]
        char_start, char_end = _span(item, "char")
        line_start, line_end = _span(item, "line")
        invalid_span = (
            (_span_was_supplied(item, "char") and (char_start is None or char_end is None))
            or (_span_was_supplied(item, "line") and (line_start is None or line_end is None))
            or (char_start is None) != (char_end is None)
            or (char_start is not None and (char_start < 0 or char_end <= char_start))
            or (line_start is None) != (line_end is None)
            or (line_start is not None and (line_start < 0 or line_end < line_start))
        )
        expected_hash = str(item.get("display_content_hash") or "").casefold()
        missing_parent = identity_kind == "stable_child" and not str(
            item.get("parent_logical_id") or metadata.get("parent_logical_id") or ""
        ).strip()
        invalid_hash = (identity_kind == "stable_child" and not expected_hash) or bool(expected_hash) and (
            _HEX_SHA256.fullmatch(expected_hash) is None or expected_hash != digest
        )
        if not path or not display or not stable or invalid_span or missing_parent or invalid_hash:
            omissions.append(Omission(stable or f"invalid:{rank}", "invalid_identity"))
            continue
        score = next((value for value in (
            item.get("score"), item.get("relevance_score"), metadata.get("score"), metadata.get("relevance_score")
        ) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))), 0.0)
        projected = projected_text(item, display, result_kind)
        reported = item.get("token_estimate") or metadata.get("token_estimate")
        trace = metadata.get("retrieval_trace") if isinstance(metadata.get("retrieval_trace"), Mapping) else {}
        component_values = item.get("component_ranks") or trace.get("component_ranks") or {}
        component_ranks = tuple(sorted(
            (str(name), int(value))
            for name, value in component_values.items()
            if isinstance(value, int) and not isinstance(value, bool) and value > 0
        )) if isinstance(component_values, Mapping) else ()
        exact_values = item.get("exact_terms") or metadata.get("exact_terms") or ()
        if isinstance(exact_values, str):
            exact_values = (exact_values,)
        candidates.append(EvidenceCandidate(
            stable_id=stable,
            evidence_id=str(item.get("evidence_id") or ""),
            hydration_id=(
                int(item.get("hydration_id"))
                if isinstance(item.get("hydration_id"), int) and not isinstance(item.get("hydration_id"), bool)
                else int(item.get("section_id"))
                if isinstance(item.get("section_id"), int) and not isinstance(item.get("section_id"), bool)
                else None
            ),
            identity_kind=identity_kind,
            source_identity=str(item.get("source_identity") or path),
            identity_aliases=identity_aliases(item, path),
            path_or_url=path,
            section=heading,
            parent_logical_id=str(item.get("parent_logical_id") or metadata.get("parent_logical_id") or ""),
            content_sha256=digest,
            display_text=display,
            projected_text=projected,
            token_estimate=(estimated_tokens(projected) if result_kind == "docs_answer" else estimated_tokens(projected) + 88),
            fit_token_estimate=(
                docs_answer_candidate_tokens(
                    stable_id=stable, path=path, section=heading, projected=projected,
                    version_binding=version_binding(item),
                )
                if result_kind == "docs_answer" else estimated_tokens(projected) + 88
            ),
            reported_token_estimate=int(reported) if isinstance(reported, int) and not isinstance(reported, bool) else None,
            char_start=char_start, char_end=char_end, line_start=line_start, line_end=line_end,
            retrieval_rank=positive_int(
                item.get("retrieval_rank") if item.get("retrieval_rank") is not None else item.get("rank"),
                default=10_000,
            ),
            component_ranks=component_ranks,
            relevance_millis=int(round(float(score) * 1000)),
            authority=authority(item),
            source_class=str(item.get("source_class") or ("legal" if str(item.get("authority") or "").casefold() == "legal" else "")),
            version_binding=version_binding(item),
            resolved_version=resolved_version(item),
            docs_snapshot_exact=(item.get("docs_snapshot_exact") if isinstance(item.get("docs_snapshot_exact"), bool) else None),
            project_identity=str(item.get("project_identity") or ""),
            module_id=str(item.get("module_id") or ""),
            doc_scope=str(item.get("doc_scope") or ""),
            symbols=symbols(item),
            exact_terms=tuple(sorted({str(value) for value in exact_values if str(value).strip()})),
            instruction_risk_flags=(),
            freshness=str(item.get("freshness") or "current"),
            navigation_only=bool(item.get("navigation_only")) or str(item.get("answer_type") or "") in {"navigation_only", "partial_navigational"},
            answer_units=extract_answer_units(
                display,
                source_fields={"path_or_url": path, "section": heading},
                include_soft_wrapped_prose=include_soft_wrapped_prose,
                representation_bounded=result_kind != "patch_context",
            ),
            answer_units_representation_bounded=result_kind != "patch_context",
            original=item,
        ))
    return candidates, omissions


__all__ = [
    "authority", "display_text", "docs_answer_candidate_tokens", "estimated_tokens",
    "identity_aliases", "normalize_candidates", "normalized_source", "observed_qualifiers",
    "positive_int", "projected_text", "requirement_value_visible", "resolved_version",
    "section", "source_path", "symbols", "version_binding", "version_rank",
]
