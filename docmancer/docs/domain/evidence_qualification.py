"""Pure qualification rules for model-visible project documentation evidence."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal, Mapping

from docmancer.docs.domain.lifecycle_policy import lifecycle_allows
from docmancer.docs.domain.project_answer_contract import LifecycleIntent

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
    candidate: Mapping[str, Any] | None = None,
    expected_project_identity: str | None = None,
    lifecycle_intent: LifecycleIntent = "current",
) -> EvidenceQualification:
    """Qualify one retrieval probe against evidence visible to the model."""
    result = dict(probe)
    if candidate is not None or expected_project_identity:
        candidate = candidate or {}
        identity = str(candidate.get("project_identity") or "").strip()
        if (expected_project_identity or candidate.get("source_class") == "project_doc") and not identity:
            return _rejected(result, "missing_project_identity")
        if expected_project_identity and identity != expected_project_identity:
            return _rejected(result, "wrong_project_identity")
        if candidate.get("stale") or str(candidate.get("freshness") or "current") != "current":
            return _rejected(result, "stale_evidence")
        if str(candidate.get("index_freshness") or "synchronized") != "synchronized":
            return _rejected(result, "unsynchronized_index")
        if candidate.get("risk_flags"):
            return _rejected(result, "unsafe_evidence")
        if not lifecycle_allows(candidate, lifecycle_intent):
            return _rejected(result, "lifecycle_not_allowed")
    normalized_visible = visible_text.casefold()
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
    body = evidence_text if evidence_text is not None else visible_text
    lines = body.splitlines()
    substantive_lines = []
    heading_lines = []
    table_rows: list[tuple[str, str]] = []
    fence = ""
    for index, line in enumerate(lines):
        fence_match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if (
                fence_match and fence_match[1][0] == fence[0]
                and len(fence_match[1]) >= len(fence) and not fence_match[2].strip()
            ):
                fence = ""
            elif line.strip():
                substantive_lines.append(line)
            continue
        if fence_match:
            fence = fence_match[1]
            continue
        if line.lstrip().startswith("#"):
            heading_lines.append(line.lstrip().lstrip("#").strip())
            continue
        next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if re.fullmatch(r"[=-]{3,}", next_line):
            heading_lines.append(line.strip())
            continue
        if (
            "|" in line and re.fullmatch(
                r"\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?", next_line,
            )
        ):
            for row in lines[index + 2:]:
                if not row.strip() or "|" not in row:
                    break
                table_rows.append((line, row))
            continue
        line = re.sub(r"!?\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])", "", line)
        line = re.sub(r"https?://\S+", "", line)
        if line.strip(" \t-*+0123456789.)|:<>_="):
            substantive_lines.append(line)
    if not substantive_lines:
        return _rejected(result, "metadata_only_evidence")
    # A heading may identify the subject of an already relevant body, but cannot
    # turn unrelated prose or a single generic match into factual evidence.
    normalized_evidence = "\n".join(substantive_lines).casefold()
    normalized_headings = "\n".join(heading_lines).casefold()

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
    body_matched = tuple(
        term for term in terms
        if _visible_term_present(
            term, normalized_evidence, exact=term in exact_terms,
        )
    )
    heading_context_allowed = len(body_matched) >= 2
    # Column labels describe a substantive row, not standalone evidence. Only
    # bind them when that table's key cell contains every requested exact term.
    # They may recover a relation term, but never supply a missing identifier.
    table_context = _bound_table_context(table_rows, exact_terms)
    table_matched = tuple(
        term for term in terms if term not in exact_terms
        and _visible_term_present(term, table_context, exact=False)
    )
    matched = tuple(dict.fromkeys((
        *body_matched,
        *table_matched,
        *(
            term for term in terms
            if heading_context_allowed
            and _visible_term_present(term, normalized_headings, exact=term in exact_terms)
        ),
    )))
    exact_evidence = (
        f"{normalized_evidence}\n{normalized_headings}"
        if heading_context_allowed else normalized_evidence
    )
    missing_exact = tuple(
        term for term in exact_terms
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", exact_evidence) is None
    )
    missing_parent_exact = tuple(
        str(value).casefold()
        for value in probe.get("parent_exact_terms") or ()
        if re.search(
            rf"(?<!\w){re.escape(str(value).casefold())}(?!\w)",
            exact_evidence,
        ) is None
    )
    ratio = len(matched) / len(terms)
    required_ratio = 1.0 if len(terms) == 1 else 0.4 if exact_terms else 0.5
    qualified = bool(matched) and ratio >= required_ratio and not missing_exact
    reason = "visible_fields" if qualified else "insufficient_visible_match"
    result.update({
        "matched_terms": list(matched),
        "body_matched_terms": list(body_matched),
        "heading_context_used": heading_context_allowed and any(
            term not in body_matched and term not in table_matched for term in matched
        ),
        "table_context_used": any(term not in body_matched for term in table_matched),
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


def _bound_table_context(rows: list[tuple[str, str]], exact_terms: tuple[str, ...]) -> str:
    if not exact_terms:
        return ""
    headers = []
    for header, row in rows:
        cells = row.strip().strip("|").split("|")
        if len(cells) < 2 or len(cells) != len(header.strip().strip("|").split("|")):
            continue
        cells = [re.sub(r"!?\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])", "", cell) for cell in cells]
        cells = [re.sub(r"https?://\S+", "", cell).casefold() for cell in cells]
        if not all(_visible_term_present(term, cells[0], exact=True) for term in exact_terms):
            continue
        if any(cell.strip(" \t-*+0123456789.)|:<>_=`") for cell in cells[1:]):
            headers.append(header)
    return "\n".join(headers).casefold()


def _coverage_kind(probe: Mapping[str, Any]) -> CoverageKind:
    return "derived" if probe.get("coverage_kind") == "derived" else "direct"


def _visible_term_present(term: str, text: str, *, exact: bool) -> bool:
    suffix = "" if exact else r"(?:s|es|ed|ing)?"
    if re.search(rf"(?<!\w){re.escape(term)}{suffix}(?!\w)", text) is not None:
        return True
    if not exact and re.fullmatch(r"[a-z]+", term):
        base = re.sub(r"(?:ing|ed|es|s)$", "", term)
        if len(base) >= 4:
            return re.search(rf"(?<!\w){re.escape(base)}{suffix}(?!\w)", text) is not None
    return False


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
