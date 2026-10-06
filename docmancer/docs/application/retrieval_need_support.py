"""Fresh default witnesses and unknown legacy retrieval-need compatibility."""
from __future__ import annotations

import re
from typing import Any, Mapping

from docmancer.docs.domain.project_answer_contract import ProofObligation
from docmancer.docs.domain.admission_local_binding import default_local_witness
from docmancer.docs.domain.technical_tokens import technical_term_pattern


def _subject_bound(query: Mapping[str, Any], text: str, source: Mapping[str, Any]) -> bool:
    subject = str(query.get("need_subject") or "").strip()
    if not subject:
        return False
    context = "\n".join((
        text,
        str(source.get("verified_owner") or ""),
    ))
    return re.search(technical_term_pattern(subject, exact=False), context, re.I) is not None


def _state_condition(query: Mapping[str, Any]) -> tuple[str, tuple[str, ...]] | None:
    return None


def _need_obligations(query: Mapping[str, Any]) -> tuple[ProofObligation, ...]:
    # Legacy prose relations have no explicit typed obligation contract.
    return ()


def retrieval_need_local_witness(
    query: Mapping[str, Any], text: str, *, source: Mapping[str, Any] | None = None,
) -> bool | None:
    """Return typed local proof, or None when a need has no typed proof model."""
    if str(query.get("need_relation") or "") == "default":
        return default_local_witness(query, text)[0]
    return None


def apply_retrieval_need_witness(
    query: Mapping[str, Any], trace: Mapping[str, Any], text: str, *,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Veto need traces without a fresh witness; never promote rejected traces.

    This compatibility adapter is not a source/provenance or answer-authority
    gate. Unknown proof is not permission to retain inherited need credit.
    """
    result = dict(trace)
    if query.get("query_origin") != "retrieval_need":
        return result
    for key in (
        "need_local_witness", "admission_route", "matched_need_ids",
        "need_witness_spans", "need_witness_source_key", "_admission_demands",
        "context_eligible", "context_need_ids", "_need_context",
    ):
        result.pop(key, None)
    if result.get("qualified") is not True:
        result["qualified"] = False
        result.setdefault("qualification_reason", "unqualified_need_trace")
        return result
    if (not isinstance(text, str) or not text.strip()
            or (source is not None and not isinstance(source, Mapping))):
        result.update(qualified=False, qualification_reason="invalid_need_witness_input")
        return result
    proof = retrieval_need_local_witness(query, text, source=source)
    if proof is not True:
        result.update(qualified=False, qualification_reason="missing_need_local_witness")
    else:
        result["need_local_witness"] = True
    return result


__all__ = ["apply_retrieval_need_witness", "retrieval_need_local_witness"]
