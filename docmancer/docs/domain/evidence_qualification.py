"""Pure qualification rules for model-visible project documentation evidence."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Any, Literal, Mapping

from docmancer.docs.domain.technical_tokens import technical_term_pattern
from docmancer.docs.domain.lifecycle_policy import lifecycle_allows
from docmancer.docs.domain.project_answer_contract import LifecycleIntent

CoverageKind = Literal["direct", "derived"]


_COMPARISON_RELATION_MARKERS = frozenset({"different", "separate"})
_GENERAL_COMPARISON_RELATION_RE = re.compile(
    r"(?:"
    r"\b(?:differs?|differed|differing|whereas)\b|"
    r"\b(?:different|distinct|separate)\s+from\b|"
    r"\b(?:are|is|was|were|remain(?:s|ed)?|become(?:s)?|became)\s+"
    r"(?:different|distinct|separate)\b|"
    r"\brather\s+than\b|\binstead\s+of\b|\bnot\s+the\s+same\b|"
    r"\bno\s+distinction\b"
    r")",
    re.I,
)
_PROOF_INSUFFICIENCY_RELATION_RE = re.compile(
    r"(?:"
    r"\b(?:not|never)\b[^.!?\n]{0,40}\b(?:enough|sufficient)\b"
    r"[^.!?\n]{0,48}\b(?:prove|support|establish|answer|cover)\w*\b|"
    r"\b(?:does|do|did|is|are|was|were)\s+not\b[^.!?\n]{0,56}"
    r"\b(?:prove|support|establish|certif|sufficien)\w*\b"
    r")",
    re.I,
)


def _clean_relation_line(value: str) -> str:
    value = re.sub(r"!?\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])", "", value)
    value = re.sub(r"https?://\S+", "", value)
    return " ".join(value.split()).strip()


def _relation_units(body: str) -> tuple[str, ...]:
    """Build relation-local units while preserving Markdown structural boundaries."""
    lines = body.splitlines()
    units: list[str] = []
    buffer: list[str] = []
    buffer_kind = ""
    fence = ""

    def flush() -> None:
        nonlocal buffer, buffer_kind
        value = _clean_relation_line(" ".join(buffer))
        if value:
            units.append(value)
        buffer = []
        buffer_kind = ""

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        fence_match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if (
                fence_match
                and fence_match[1][0] == fence[0]
                and len(fence_match[1]) >= len(fence)
                and not fence_match[2].strip()
            ):
                flush()
                fence = ""
            elif stripped:
                buffer.append(line)
            index += 1
            continue
        if fence_match:
            flush()
            fence = fence_match[1]
            buffer_kind = "code"
            index += 1
            continue
        if not stripped:
            flush()
            index += 1
            continue
        if line.lstrip().startswith("#"):
            flush()
            index += 1
            continue
        next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if next_line and re.fullmatch(r"[=-]{3,}", next_line):
            flush()
            index += 2
            continue
        if re.fullmatch(r"\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?", stripped):
            flush()
            index += 1
            continue
        if line.count("|") >= 2:
            flush()
            for cell in re.split(r"(?<!\\)\|", line.strip().strip("|")):
                value = _clean_relation_line(cell)
                if value and not re.fullmatch(r":?-{3,}:?", value):
                    units.append(value)
            index += 1
            continue
        list_match = re.match(r"^\s*(?:[-*+] |\d+[.)]\s+)(.*)$", line)
        if list_match:
            flush()
            buffer = [list_match.group(1)]
            buffer_kind = "list"
            index += 1
            continue
        if buffer_kind == "list" and not line[:1].isspace():
            flush()
        buffer.append(line)
        if not buffer_kind:
            buffer_kind = "prose"
        index += 1
    flush()
    return tuple(units)


def _comparison_relation_probe(query_id: str, query_text: str) -> bool:
    if not query_id.startswith("query-relation-"):
        return False
    tokens = tuple(re.findall(r"[A-Za-z]+", query_text.casefold()))
    return len(tokens) >= 2 and tuple(tokens[-2:]) == ("different", "separate")


def _relation_term_count(text: str, terms: tuple[str, ...]) -> int:
    return sum(_visible_term_present(term, text, exact=False) for term in terms)


def _proof_relation_is_locally_bound(
    clause: str, match: re.Match[str], terms: tuple[str, ...],
) -> bool:
    """Do not borrow proof subjects from a neighboring comma-delimited clause."""
    left = max(clause.rfind(",", 0, match.start()), clause.rfind(";", 0, match.start()))
    right_candidates = [
        pos for token in (",", ";")
        if (pos := clause.find(token, match.end())) >= 0
    ]
    right = min(right_candidates) if right_candidates else len(clause)
    local = clause[left + 1:right]
    return any(_visible_term_present(term, local, exact=False) for term in terms)


def _general_relation_is_locally_bound(
    clause: str, match: re.Match[str], terms: tuple[str, ...],
) -> bool:
    marker = match.group(0).casefold()
    before, after = clause[:match.start()], clause[match.end():]
    splits_sides = (
        "whereas" in marker
        or re.search(r"\bdiffers?\b", marker) is not None
        or "rather than" in marker
        or "instead of" in marker
        or " from" in marker
        or ("not the same" in marker and re.match(r"\s+as\b", after) is not None)
    )
    if splits_sides:
        return (
            _relation_term_count(before, terms) >= 1
            and _relation_term_count(after, terms) >= 1
        )
    needed = min(2, len(terms))
    return bool(needed and _relation_term_count(clause, terms) >= needed)


def _visible_comparison_relation(text: str, terms: tuple[str, ...]) -> bool:
    """Require the visible relation to be local to the requested concepts."""
    for sentence in re.split(r"[.!?\n]+", text):
        sentence = sentence.strip()
        if not sentence:
            continue
        for clause in (value.strip() for value in sentence.split(";")):
            if not clause:
                continue
            for match in _PROOF_INSUFFICIENCY_RELATION_RE.finditer(clause):
                if _proof_relation_is_locally_bound(clause, match, terms):
                    return True
            for match in _GENERAL_COMPARISON_RELATION_RE.finditer(clause):
                if _general_relation_is_locally_bound(clause, match, terms):
                    return True
    return False


@dataclass(frozen=True, slots=True)
class EvidenceQualification:
    qualified: bool
    covered_query_ids: tuple[str, ...]
    coverage_kind: CoverageKind | None
    reason: str
    trace: Mapping[str, Any]


def evidence_policy_rejection_reason(
    probe: Mapping[str, Any], *, visible_text: str, catalog_role: str = "",
    forbidden_catalog_roles: tuple[str, ...] = (),
    forbidden_evidence_terms: tuple[str, ...] = (),
    candidate: Mapping[str, Any] | None = None,
    expected_project_identity: str | None = None,
    lifecycle_intent: LifecycleIntent = "current",
) -> str | None:
    """Return the source/policy rejection independently of lexical matching."""
    if candidate is not None or expected_project_identity:
        candidate = candidate or {}
        identity = str(candidate.get("project_identity") or "").strip()
        if (expected_project_identity or candidate.get("source_class") == "project_doc") and not identity:
            return "missing_project_identity"
        if expected_project_identity and identity != expected_project_identity:
            return "wrong_project_identity"
        if candidate.get("stale") or str(candidate.get("freshness") or "current") != "current":
            return "stale_evidence"
        if str(candidate.get("index_freshness") or "synchronized") != "synchronized":
            return "unsynchronized_index"
        if candidate.get("risk_flags"):
            return "unsafe_evidence"
        if not lifecycle_allows(candidate, lifecycle_intent):
            return "lifecycle_not_allowed"
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
        return "forbidden_evidence_term"
    if catalog_role and catalog_role in forbidden_roles:
        return "forbidden_catalog_role"
    return None



def _substantive_markdown_line(line: str) -> str:
    """Keep visible inline-link labels only when the line carries a real statement."""
    if re.match(r"^\s*\[[^\]]+\]:\s*\S+", line):
        return ""

    code_parts: list[str] = []

    def protect_code(match: re.Match[str]) -> str:
        code_parts.append(match.group(2))
        return f"\x00CODE{len(code_parts) - 1}\x00"

    protected = re.sub(r"(`+)(.+?)\1", protect_code, line)
    protected = re.sub(r"!\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])", "", protected)
    link_re = re.compile(r"(?<!!)\[([^\]]+)\](?:\([^)]*\)|\[[^\]]*\])")
    without_links = link_re.sub("", protected)
    without_links = re.sub(r"https?://\S+", "", without_links)

    probe = without_links
    for index, code in enumerate(code_parts):
        probe = probe.replace(f"\x00CODE{index}\x00", code)
    has_statement = bool(probe.strip(" \t-*+0123456789.)|:<>_=`"))

    rendered = link_re.sub(lambda m: m.group(1) if has_statement else "", protected)
    rendered = re.sub(r"https?://\S+", "", rendered)
    for index, code in enumerate(code_parts):
        rendered = rendered.replace(f"\x00CODE{index}\x00", code)
    return rendered

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
    policy_reason = evidence_policy_rejection_reason(
        probe, visible_text=visible_text, catalog_role=catalog_role,
        forbidden_catalog_roles=forbidden_catalog_roles,
        forbidden_evidence_terms=forbidden_evidence_terms, candidate=candidate,
        expected_project_identity=expected_project_identity, lifecycle_intent=lifecycle_intent,
    )
    if policy_reason is not None:
        return _rejected(result, policy_reason)
    body = evidence_text if evidence_text is not None else visible_text
    from .query_reference_binding import prepare_reference_probe
    probe, reference_reason = prepare_reference_probe(probe, candidate=candidate, evidence_text=body)
    result = dict(probe)
    if reference_reason is not None:
        return _rejected(result, reference_reason)
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
        line = _substantive_markdown_line(line)
        if line.strip(" \t-*+0123456789.)|:<>_="):
            substantive_lines.append(line)
    if not substantive_lines:
        return _rejected(result, "metadata_only_evidence")
    # A heading may identify the subject of an already relevant body, but cannot
    # turn unrelated prose or a single generic match into factual evidence.
    normalized_evidence = "\n".join(substantive_lines).casefold()
    normalized_headings = "\n".join(heading_lines).casefold()

    relation_text = str(probe.get("query_text") or "").casefold()
    comparison_relation = _comparison_relation_probe(query_id, relation_text)
    if query_id.startswith("query-relation-"):
        negated_state = re.search(
            r"(?<!\w)(?:not|without|never|no)(?!\w)\s+([a-z][a-z0-9_-]{2,})\s*$",
            relation_text, re.I,
        )
        if negated_state is not None:
            state = re.escape(negated_state.group(1))
            if re.search(
                rf"(?<!\w)(?:not|without|never|no)(?!\w)(?:\s+\w+){{0,2}}\s+{state}(?!\w)",
                normalized_evidence, re.I,
            ) is None:
                return _rejected(result, "missing_visible_relation_negation")

    if str(probe.get("mode") or "") == "exact_path":
        query_text = str(probe.get("query_text") or "").replace("\\", "/").casefold()
        normalized_visible = visible_text.replace("\\", "/").casefold()
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
    if comparison_relation:
        terms = tuple(term for term in terms if term not in _COMPARISON_RELATION_MARKERS)
        relation_units = _relation_units(body)
        if not any(_visible_comparison_relation(unit, terms) for unit in relation_units):
            return _rejected(result, "missing_visible_comparison_relation")
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
    bound_subjects = tuple(
        str(value).casefold() for value in probe.get("bound_subjects") or () if value
    )
    bound_subject_context = str(probe.get("bound_subject_context") or "").casefold()
    missing_bound_subjects = tuple(
        subject for subject in bound_subjects
        if not _visible_term_present(subject, normalized_evidence, exact=True)
        and not (
            heading_context_allowed
            and _visible_term_present(subject, bound_subject_context, exact=True)
        )
    )
    if missing_bound_subjects:
        result.update(
            bound_subjects=list(bound_subjects),
            missing_bound_subjects=list(missing_bound_subjects),
            qualified=False,
            qualification_reason="missing_bound_subject",
        )
        return EvidenceQualification(
            False, (), None, "missing_bound_subject", result,
        )
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
            and (_visible_term_present(term, normalized_headings, exact=term in exact_terms)
                 or (term in bound_subjects and _visible_term_present(term, bound_subject_context, exact=True)))
        ),
    )))
    exact_evidence = (
        f"{normalized_evidence}\n{normalized_headings}"
        if heading_context_allowed else normalized_evidence
    )
    missing_exact = tuple(
        term for term in exact_terms
        if not _visible_term_present(term, exact_evidence, exact=True)
    )
    missing_parent_exact = tuple(
        str(value).casefold()
        for value in probe.get("parent_exact_terms") or ()
        if not _visible_term_present(str(value).casefold(), exact_evidence, exact=True)
    )
    ratio = len(matched) / len(terms)
    required_ratio = (
        1.0 if len(terms) == 1
        else 0.4 if exact_terms or comparison_relation
        else 0.5
    )
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


@lru_cache(maxsize=4096)
def _visible_term_present(term: str, text: str, *, exact: bool) -> bool:
    suffix = "" if exact else r"(?:s|es|ed|ing)?"
    if re.search(technical_term_pattern(term, exact=exact), text) is not None:
        return True
    if not exact and re.fullmatch(r"[a-z]+", term):
        # Regular consonant-y inflection is lexical equivalence, not an
        # identifier alias: retry/retried/retries, identity/identities.
        stem = re.sub(r"(?:ied|ies|y)$", "", term)
        if (stem != term and len(stem) >= 3 and stem[-1] not in 'aeiou'
                and re.search(rf"(?<!\w){re.escape(stem)}(?:y|ied|ies)(?!\w)", text)):
            return True
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
    "evidence_policy_rejection_reason",
    "qualify_evidence",
    "qualify_visible_trace",
]
