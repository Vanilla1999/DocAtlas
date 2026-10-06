"""Bounded recovery guidance for failed project-document evidence proof.

Recovery is diagnostic-only: it never changes canonical evidence selection or
turns an unsupported documentation answer into a supported one. It preserves
bounded original diagnostic fragments and typed non-automatic recovery, without
synthesizing a different question or certifying paraphrase equivalence.
"""
from __future__ import annotations

import re
from typing import Any

from docmancer.docs.application.evidence_requirements import build_requirements
from docmancer.docs.application.proofability import diagnose_proofability
from docmancer.retrieval.query_planning import extract_document_locator

RECOVERY_SCHEMA_VERSION = 1
MAX_PROBLEM_SPANS = 2
MAX_RECOGNIZED_SPANS = 6
MAX_SUGGESTED_QUESTIONS = 2

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
    """Bound the original request for diagnostics, without inferred clauses.

    Requirement spans cannot establish semantic coverage of a clause. This
    fragment is display/retry guidance only, never a generated retrieval lane.
    """
    text = question.strip()[:220]
    return [text] if text else []


def _suggested_questions(
    question: str,
    requirements: Any,
    *,
    evidence_path: str | None,
) -> list[str]:
    """Compatibility adapter: diagnostic fragments never synthesize a question."""
    return []


def build_recovery_diagnosis(
    question: str,
    selection: Any,
    *,
    operational_reason_code: str | None = None,
    projection: dict[str, Any] | None = None,
    retrieval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Explain one failed docs proof and return a bounded recovery contract.

    The returned mapping is safe to expose to an agent.  It is intentionally
    independent of selector authorization: ``documentation_supported`` remains
    false for every recovery state.
    """

    decision = _selection_decision(selection)
    if decision is None and projection is None:
        return {}
    support = getattr(decision, "support_decision", None)
    if projection is None and support is not None and bool(getattr(support, "answer_supported", False)):
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

    if projection is not None:
        if projection.get("context_available"):
            return {}
        candidates = (retrieval or {}).get("context_pack") or ()
        qualified = any(
            isinstance(source, dict) and any(
                isinstance(trace, dict) and trace.get("qualified") is True
                for trace in (source.get("retrieval_query_matches") or {}).values()
            ) for source in candidates
        )
        diagnostics = ((retrieval or {}).get("retrieval_diagnostics") or {}).get("docs_context_projection")
        if isinstance(diagnostics, dict):
            qualified = bool(diagnostics.get("qualified_variants"))
        reason = (
            "no_candidates" if not candidates else
            "bounded_selection_failed" if qualified and diagnostics and diagnostics.get("budget_rejections") else
            "visible_evidence_lost" if qualified else "evidence_rejected"
        )
        result.update({
            "origin": "retrieval" if not candidates else "selection" if qualified else "eligibility",
            "reason_code": reason,
            "disposition": "search_local_source",
            "problem_spans": _problem_spans(question, requirements),
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

    # Uncertain proof permits bounded investigation, never a synthesized retry.
    result["disposition"] = "search_local_source"
    return result


def projection_recovery_action(
    question: str, selection: Any, *, projection: dict[str, Any],
    retrieval: dict[str, Any], request: dict[str, Any],
    operational_reason_code: str | None = None,
) -> dict[str, Any] | None:
    """Bind non-operational recovery to the already computed projection."""
    diagnosis = build_recovery_diagnosis(
        question, selection, projection=projection, retrieval=retrieval,
        operational_reason_code=operational_reason_code,
    )
    if not diagnosis:
        return None
    retrieval.update({
        "recovery_origin": diagnosis["origin"],
        "recovery_reason_code": diagnosis["reason_code"],
        "recovery_disposition": diagnosis["disposition"],
    })
    return recovery_action(diagnosis, project_path=request.get("project_path"), scope=request.get("scope"))


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
        # A legacy/supplied diagnosis cannot restore semantic retry authority.
        return None
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
