"""Pure qualification rules for model-visible project documentation evidence."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal, Mapping

CoverageKind = Literal["direct", "derived"]


@dataclass(frozen=True, slots=True)
class EvidenceQualification:
    qualified: bool
    covered_query_ids: tuple[str, ...]
    coverage_kind: CoverageKind | None
    reason: str
    trace: Mapping[str, Any]


def qualify_evidence(
    probe: Mapping[str, Any], *, query_id: str, visible_text: str,
    evidence_text: str | None = None,
    catalog_role: str = "", forbidden_catalog_roles: tuple[str, ...] = (),
    forbidden_evidence_terms: tuple[str, ...] = (),
) -> EvidenceQualification:
    """Qualify one retrieval probe against evidence visible to the model."""
    result = dict(probe)
    normalized_visible = visible_text.casefold()
    normalized_evidence = (
        evidence_text if evidence_text is not None else visible_text
    ).casefold()
    forbidden_terms = tuple(dict.fromkeys((
        *(str(value) for value in probe.get("forbidden_evidence_terms") or ()),
        *forbidden_evidence_terms,
    )))
    forbidden_roles = set(str(value) for value in (
        *(probe.get("forbidden_catalog_roles") or ()),
        *forbidden_catalog_roles,
    ))
    if any(str(term).casefold() in normalized_visible for term in forbidden_terms):
        return _rejected(result, "forbidden_evidence_term")
    if catalog_role and catalog_role in forbidden_roles:
        return _rejected(result, "forbidden_catalog_role")
    if not any(
        line.strip() and not line.lstrip().startswith("#")
        for line in (evidence_text if evidence_text is not None else visible_text).splitlines()
    ):
        return _rejected(result, "metadata_only_evidence")

    if str(probe.get("mode") or "") == "exact_path":
        query_text = str(probe.get("query_text") or "").replace("\\", "/").casefold()
        qualified = bool(query_text and query_text in normalized_visible)
        result.update(
            qualified=qualified,
            qualification_reason="visible_exact_path" if qualified else "missing_visible_exact_path",
        )
        return EvidenceQualification(
            qualified,
            (query_id,) if qualified else (),
            _coverage_kind(probe) if qualified else None,
            str(result["qualification_reason"]),
            result,
        )

    terms = tuple(
        str(value).casefold() for value in probe.get("query_terms") or () if value
    )
    if not terms:
        terms = tuple(dict.fromkeys(
            token.casefold()
            for token in re.findall(
                r"[A-Za-zА-Яа-яЁё0-9_.-]{4,}", str(probe.get("query_text") or ""),
            )
        ))
    if not terms:
        return _rejected(result, "missing_visible_query_terms")

    exact_terms = tuple(
        str(value).casefold() for value in probe.get("exact_terms") or () if value
    )
    matched = tuple(
        term for term in terms
        if _visible_term_present(
            term, normalized_evidence, exact=term in exact_terms,
        )
    )
    missing_exact = tuple(
        term for term in exact_terms
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized_evidence) is None
    )
    missing_parent_exact = tuple(
        str(value).casefold()
        for value in probe.get("parent_exact_terms") or ()
        if re.search(
            rf"(?<!\w){re.escape(str(value).casefold())}(?!\w)",
            normalized_evidence,
        ) is None
    )
    ratio = len(matched) / len(terms)
    required_ratio = 1.0 if len(terms) == 1 else 0.4 if exact_terms else 0.5
    qualified = bool(matched) and ratio >= required_ratio and not missing_exact
    reason = "visible_fields" if qualified else "insufficient_visible_match"
    result.update({
        "matched_terms": list(matched),
        "missing_exact_terms": list(missing_exact),
        "missing_parent_exact_terms": list(missing_parent_exact),
        "matched_term_count": len(matched),
        "match_ratio": round(ratio, 4),
        "qualified": qualified,
        "qualification_reason": reason,
    })
    return EvidenceQualification(
        qualified,
        (query_id,) if qualified else (),
        _coverage_kind(probe) if qualified else None,
        reason,
        result,
    )


def qualify_visible_trace(
    trace: Mapping[str, Any], *, visible_text: str, catalog_role: str = "",
) -> dict[str, Any]:
    """Compatibility wrapper for callers that qualify one anonymous trace."""
    return dict(qualify_evidence(
        trace,
        query_id=str(trace.get("query_id") or "query"),
        visible_text=visible_text,
        evidence_text=visible_text,
        catalog_role=catalog_role,
    ).trace)


def derived_parent_trace(
    trace: Mapping[str, Any], *, source_query_id: str, parent_query_id: str,
) -> dict[str, Any] | None:
    """Derive parent coverage only from a qualified audited rewrite."""
    if (
        trace.get("qualified") is not True
        or trace.get("relation") != "audited_rewrite"
        or not parent_query_id
        or bool(trace.get("missing_parent_exact_terms"))
    ):
        return None
    result = dict(trace)
    result.update({
        "query_id": parent_query_id,
        "coverage_kind": "derived",
        "coverage_kinds": ["derived"],
        "derived_from_query_id": source_query_id,
        "derived_from_query_ids": [source_query_id],
    })
    return result


def _coverage_kind(probe: Mapping[str, Any]) -> CoverageKind:
    return "derived" if probe.get("coverage_kind") == "derived" else "direct"


def _visible_term_present(term: str, text: str, *, exact: bool) -> bool:
    suffix = "" if exact else r"(?:s|es|ed|ing)?"
    return re.search(rf"(?<!\w){re.escape(term)}{suffix}(?!\w)", text) is not None


def _rejected(trace: dict[str, Any], reason: str) -> EvidenceQualification:
    trace.update(qualified=False, qualification_reason=reason)
    return EvidenceQualification(False, (), None, reason, trace)


__all__ = [
    "CoverageKind",
    "EvidenceQualification",
    "derived_parent_trace",
    "qualify_evidence",
    "qualify_visible_trace",
]
