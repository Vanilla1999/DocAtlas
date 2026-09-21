"""Local proof checks for internal question-derived retrieval needs."""
from __future__ import annotations

import re
from typing import Any, Mapping

from docmancer.docs.domain.answer_units import best_local_proof, extract_answer_units
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
    text = " ".join(str(query.get(key) or "") for key in ("need_context", "text"))
    match = re.search(
        r"\b(?:if|when)\s+(.+?)\s+is\s+(not\s+enabled|disabled|enabled)\b",
        text,
        re.I,
    )
    if match is None:
        return None
    entity = " ".join(match.group(1).split()).strip(" ,:;()")
    state = " ".join(match.group(2).casefold().split())
    relations = ("disabled", "not enabled") if state in {"disabled", "not enabled"} else ("enabled",)
    return entity, relations


def _need_obligations(query: Mapping[str, Any]) -> tuple[ProofObligation, ...]:
    relation = str(query.get("need_relation") or "")
    subject = str(query.get("need_subject") or "").strip()
    text = str(query.get("text") or "")
    query_id = str(query.get("query_id") or "retrieval-need")
    if not subject:
        return ()
    if relation == "exception":
        return (
            ProofObligation(
                obligation_id=query_id + ":raise",
                kind="exact_fact", subject="raise", value_kind="code", mandatory=False,
            ),
            ProofObligation(
                obligation_id=query_id + ":exception",
                kind="exact_fact", subject="exception", value_kind="code", mandatory=False,
            ),
        )
    if relation == "requirement":
        rows: list[ProofObligation] = []
        if re.search(r"\b(?:count|number|many)\b", text, re.I):
            rows.append(ProofObligation(
                obligation_id=query_id + ":number",
                kind="exact_fact", subject=subject, value_kind="number", mandatory=False,
            ))
        for marker in ("must", "required", "need"):
            rows.append(ProofObligation(
                obligation_id=query_id + ":" + marker,
                kind="relation", subject=subject, relation=marker, mandatory=False,
            ))
        return tuple(rows)
    if relation == "behavior":
        state = _state_condition(query)
        if state is None:
            return ()
        entity, relations = state
        return tuple(ProofObligation(
            obligation_id=f"{query_id}:state:{index}",
            kind="relation", subject=entity, relation=value, mandatory=False,
        ) for index, value in enumerate(relations, start=1))
    return ()


def retrieval_need_local_witness(
    query: Mapping[str, Any], text: str, *, source: Mapping[str, Any] | None = None,
) -> bool | None:
    """Return typed local proof, or None when a need has no typed proof model."""
    if str(query.get("need_relation") or "") == "default":
        return default_local_witness(query, text)[0]
    obligations = _need_obligations(query)
    if not obligations:
        return None
    source = source or {}
    if not _subject_bound(query, text, source):
        return False
    units = tuple(
        unit for unit in extract_answer_units(text, include_soft_wrapped_prose=True)
        if unit.proposition
    )
    relation = str(query.get("need_relation") or "")
    for obligation in obligations:
        match = best_local_proof(obligation, units, source=source)
        if match is None:
            continue
        if relation == "behavior":
            # A state mention alone is not an answer to "what happens". Require
            # the same local sentence to carry a consequent after the condition.
            state_text = match[0].text
            if re.search(
                r"\b(?:if|when)\b.+?\b(?:disabled|not\s+enabled|enabled)\b\s*,\s*\S+",
                state_text,
                re.I,
            ) is None:
                continue
        return True
    return False


def apply_retrieval_need_witness(
    query: Mapping[str, Any], trace: Mapping[str, Any], text: str, *,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Retain compatibility vetoes; guarded promotion is owned by qualify_evidence.

    This adapter cannot promote an arbitrary serialized trace. All retrieval and
    crop paths obtain the same freshly guarded decision from the domain owner.
    """
    result = dict(trace)
    if query.get("query_origin") != "retrieval_need" or result.get("qualified") is not True:
        return result
    proof = retrieval_need_local_witness(query, text, source=source)
    if proof is False:
        result.update(qualified=False, qualification_reason="missing_need_local_witness")
    elif proof is True:
        result["need_local_witness"] = True
    return result


__all__ = ["apply_retrieval_need_witness", "retrieval_need_local_witness"]
