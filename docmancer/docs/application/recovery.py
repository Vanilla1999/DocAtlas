"""Bounded recovery guidance for failed project-document evidence proof.

Recovery is diagnostic-only: it never changes canonical evidence selection or
turns an unsupported documentation answer into a supported one.  It explains
where proof failed and, for parser/retrieval/bounded-selection failures, offers
one non-automatic retry assembled only from source question spans plus fixed
neutral wrappers.
"""
from __future__ import annotations

import re
from typing import Any

from docmancer.docs.application.evidence_requirements import build_requirements
from docmancer.docs.application.proofability import diagnose_proofability
from docmancer.docs.domain.question_frame_core import split_question_clause_spans
from docmancer.retrieval.query_planning import extract_document_locator

RECOVERY_SCHEMA_VERSION = 1
MAX_PROBLEM_SPANS = 2
MAX_RECOGNIZED_SPANS = 6
MAX_SUGGESTED_QUESTIONS = 2

_GENERIC_REPHRASE_PREFIX = "What does the project documentation say about "
_GENERATED_EXACT_REPHRASE_RE = re.compile(
    r"^\s*according\s+to\s+[`\"']?(?:\.?\.?/)?(?:[A-Za-z0-9_.-]+/)*"
    r"[A-Za-z0-9_.-]+\.(?:md|mdx|rst|txt|adoc)[`\"']?\s*,\s*"
    r"what\s+does\s+it\s+say\s+about\s+",
    re.I,
)

# These are operational states with a concrete recovery that is more precise
# than changing the wording of the question.
_OPERATIONAL_RECOVERY_REASONS = frozenset({
    "project_docs_found_not_indexed", "project_docs_stale",
    "invalid_project_docs_catalog", "project_docs_preflight",
    "module_ambiguous", "module_not_found", "no_module_docs",
    "document_not_indexed", "ambiguous_document_locator",
    "library_docs_source_required", "library_docs_network_fetch_required",
    "latest_fallback_network_fetch_required",
})


def _selection_decision(value: Any) -> Any | None:
    nested = getattr(value, "selection_decision", None)
    return nested if nested is not None else value


def _clean_fragment(value: object, *, max_chars: int = 180) -> str:
    text = " ".join(str(value or "").strip().split())
    return text.strip(" \t\r\n,;:.!?")[:max_chars]


def _requirement_spans(requirements: Any, question: str) -> list[str]:
    rows: list[tuple[int, int, str]] = []
    for item in requirements:
        if not getattr(item, "mandatory", False) or getattr(item, "kind", "") == "unsupported_query":
            continue
        start = getattr(item, "query_span_start", None)
        end = getattr(item, "query_span_end", None)
        text = _clean_fragment(getattr(item, "query_span_text", None))
        if (
            isinstance(start, int) and isinstance(end, int)
            and 0 <= start < end <= len(question) and text
        ):
            rows.append((start, end, text))
    rows.sort(key=lambda row: (row[0], row[1], row[2].casefold()))
    return list(dict.fromkeys(text for _, _, text in rows))[:MAX_RECOGNIZED_SPANS]


def _exact_question_hints(requirements: Any, question: str) -> list[str]:
    folded = question.casefold()
    rows: list[str] = []
    for value in getattr(requirements, "retrieval_hints", ()) or ():
        text = _clean_fragment(value, max_chars=140)
        if not text or text.casefold() not in folded:
            continue
        rows.append(text)
    # Prefer code-shaped/numeric and longer exact source fragments without
    # giving any vocabulary special parsing meaning.
    rows = list(dict.fromkeys(rows))
    rows.sort(
        key=lambda text: (
            -int(bool(re.search(r"[_.:/=]", text))),
            -int(bool(re.search(r"\d", text))),
            -len(text),
            text.casefold(),
        )
    )
    return rows[:MAX_RECOGNIZED_SPANS]


def _problem_spans(question: str, requirements: Any) -> list[str]:
    """Return exact source clauses that are not fully covered by known spans."""

    covered: list[tuple[int, int]] = [
        (int(start), int(end))
        for _, start, end, _ in getattr(requirements, "query_requirement_spans", ()) or ()
        if 0 <= int(start) < int(end) <= len(question)
    ]
    clauses = split_question_clause_spans(question)
    if not clauses:
        return [_clean_fragment(question, max_chars=220)] if question.strip() else []

    scored: list[tuple[float, int, str]] = []
    for clause in clauses:
        overlap = sum(
            max(0, min(clause.end, end) - max(clause.start, start))
            for start, end in covered
        )
        ratio = min(1.0, overlap / max(1, clause.end - clause.start))
        text = _clean_fragment(clause.text, max_chars=220)
        if text:
            scored.append((ratio, clause.start, text))
    scored.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in scored[:MAX_PROBLEM_SPANS]]


def _already_rephrased(question: str) -> bool:
    folded = question.strip().casefold()
    return folded.startswith(_GENERIC_REPHRASE_PREFIX.casefold()) or bool(
        _GENERATED_EXACT_REPHRASE_RE.search(question)
    )


def _suggested_questions(
    question: str,
    requirements: Any,
    *,
    evidence_path: str | None,
) -> list[str]:
    candidates = _requirement_spans(requirements, question)
    for hint in _exact_question_hints(requirements, question):
        if hint.casefold() not in {item.casefold() for item in candidates}:
            candidates.append(hint)
    if not candidates:
        candidates = _problem_spans(question, requirements)
    if evidence_path:
        normalized_locator = evidence_path.replace("\\", "/").casefold()
        locator_leaf = normalized_locator.rsplit("/", 1)[-1]
        candidates = [
            value for value in candidates
            if _clean_fragment(value, max_chars=240).replace("\\", "/").casefold()
            not in {normalized_locator, locator_leaf}
        ]

    result: list[str] = []
    for fragment in candidates:
        fragment = _clean_fragment(fragment, max_chars=140)
        if not fragment:
            continue
        if evidence_path:
            suggestion = f"According to {evidence_path}, what does it say about {fragment}?"
        else:
            suggestion = f"{_GENERIC_REPHRASE_PREFIX}{fragment}?"
        if suggestion.casefold() == question.strip().casefold():
            continue
        result.append(suggestion[:320])
        if len(result) >= MAX_SUGGESTED_QUESTIONS:
            break
    return result


def build_recovery_diagnosis(
    question: str,
    selection: Any,
    *,
    operational_reason_code: str | None = None,
) -> dict[str, Any]:
    """Explain one failed docs proof and return a bounded recovery contract.

    The returned mapping is safe to expose to an agent.  It is intentionally
    independent of selector authorization: ``documentation_supported`` remains
    false for every recovery state.
    """

    decision = _selection_decision(selection)
    if decision is None:
        return {}
    support = getattr(decision, "support_decision", None)
    if support is not None and bool(getattr(support, "answer_supported", False)):
        return {}

    operational_reason = _clean_fragment(operational_reason_code, max_chars=120)
    evidence_path = extract_document_locator(question)
    profile = "project_document_answer" if evidence_path else "project_docs_answer"
    requirements = build_requirements(
        question,
        required_evidence_paths=(evidence_path,) if evidence_path else (),
        profile=profile,
    )
    proofability = diagnose_proofability(decision)
    proof_origin = str(proofability.get("origin") or "selection")
    proof_reasons = [str(value) for value in proofability.get("reason_codes") or []]

    result: dict[str, Any] = {
        "schema_version": RECOVERY_SCHEMA_VERSION,
        "documentation_supported": False,
        "investigation_allowed": True,
        "hard_stop": False,
    }

    if operational_reason in _OPERATIONAL_RECOVERY_REASONS:
        result.update({
            "origin": "operational",
            "reason_code": operational_reason,
            "disposition": "use_operational_recovery",
        })
        return result

    # An explicit exact document path is itself an independent support contract;
    # parser uncertainty is diagnostic there and must not shadow retrieval truth.
    if requirements.unresolved_parts and not evidence_path:
        origin = "parsing"
        reason_code = "question_parse_uncertain"
        detail_reasons = list(requirements.unresolved_parts)[:4]
    elif proof_origin == "retrieval":
        origin = "retrieval"
        reason_code = "retrieval_miss"
        detail_reasons = proof_reasons
    elif proof_origin == "eligibility":
        origin = "eligibility"
        reason_code = "evidence_ineligible"
        detail_reasons = proof_reasons
    elif proof_origin == "source_documentation":
        if "conflicting_authoritative_evidence" in proof_reasons:
            origin = "conflict"
            reason_code = "authoritative_evidence_conflict"
            detail_reasons = proof_reasons
            result.update({
                "origin": origin,
                "reason_code": reason_code,
                "disposition": "resolve_authoritative_conflict",
                "hard_stop": True,
                "detail_reasons": detail_reasons[:4],
            })
            return result
        if "fragmented_support_exceeds_bound" in proof_reasons:
            origin = "selection"
            reason_code = "bounded_selection_too_broad"
        else:
            origin = "source_documentation"
            reason_code = "documentation_gap"
        detail_reasons = proof_reasons
    else:
        origin = "selection"
        reason_code = "bounded_selection_failed"
        detail_reasons = proof_reasons

    result.update({
        "origin": origin,
        "reason_code": reason_code,
        "detail_reasons": detail_reasons[:4],
    })

    if origin in {"eligibility", "source_documentation"}:
        result["disposition"] = (
            "repair_evidence_state" if origin == "eligibility" else "search_local_source"
        )
        return result

    recognized = _requirement_spans(requirements, question)
    for hint in _exact_question_hints(requirements, question):
        if hint.casefold() not in {item.casefold() for item in recognized}:
            recognized.append(hint)
    if recognized:
        result["recognized_spans"] = recognized[:MAX_RECOGNIZED_SPANS]
    problems = _problem_spans(question, requirements)
    if problems:
        result["problem_spans"] = problems[:MAX_PROBLEM_SPANS]

    if _already_rephrased(question):
        result.update({
            "disposition": "search_local_source",
            "rephrase_exhausted": True,
        })
        return result

    suggestions = _suggested_questions(
        question,
        requirements,
        evidence_path=evidence_path,
    )
    if suggestions:
        result.update({
            "disposition": "rephrase_question",
            "suggested_questions": suggestions,
            "rephrase_exhausted": False,
        })
    else:
        result.update({
            "disposition": "search_local_source",
            "rephrase_exhausted": True,
        })
    return result


def recovery_action(
    diagnosis: dict[str, Any],
    *,
    project_path: str | None = None,
    scope: str | None = None,
    mode: str | None = None,
) -> dict[str, Any] | None:
    """Project a diagnosis to one non-automatic agent recovery action."""

    if not diagnosis or diagnosis.get("hard_stop"):
        return None
    disposition = str(diagnosis.get("disposition") or "")
    if disposition == "rephrase_question":
        suggestions = [
            str(value)[:320]
            for value in diagnosis.get("suggested_questions") or []
            if str(value).strip()
        ][:MAX_SUGGESTED_QUESTIONS]
        if not suggestions:
            return None
        arguments_patch: dict[str, Any] = {"question": suggestions[0]}
        for key, value in (("project_path", project_path), ("scope", scope), ("mode", mode)):
            if value:
                arguments_patch[key] = value
        return {
            "type": "rephrase_question",
            "tool": "get_docs_context",
            "handled_by": "coding_agent",
            "requires_confirmation": False,
            "reason": str(diagnosis.get("reason_code") or "question_parse_uncertain"),
            "agent_question": (
                "DocAtlas could not complete documentation proof for the original wording. "
                "Retry at most one suggested question without treating it as equivalent proof."
            ),
            "observations": [
                *[f"problem_span: {value}" for value in diagnosis.get("problem_spans") or []],
                *[f"recognized_span: {value}" for value in diagnosis.get("recognized_spans") or []],
            ][:6],
            "decision_options": [
                {"question": value, "preserves_source_words": True}
                for value in suggestions
            ],
            "arguments_patch": arguments_patch,
            "repeat_docs_context": True,
            "auto_execute": False,
        }
    if disposition == "search_local_source":
        terms = [
            str(value)[:160]
            for value in diagnosis.get("recognized_spans") or diagnosis.get("problem_spans") or []
            if str(value).strip()
        ][:8]
        return {
            "type": "search_local_source",
            "tool": "code_search",
            "handled_by": "coding_agent",
            "requires_confirmation": False,
            "reason": str(diagnosis.get("reason_code") or "documentation_proof_unavailable"),
            "query_terms": terms,
            "repeat_docs_context": False,
            "auto_execute": False,
        }
    return None


__all__ = [
    "RECOVERY_SCHEMA_VERSION",
    "build_recovery_diagnosis",
    "recovery_action",
]
