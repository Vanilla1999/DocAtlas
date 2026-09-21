"""Private admission decisions; callers recompute guards and witnesses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping


@dataclass(frozen=True, slots=True)
class HardGuards:
    allowed: bool
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.allowed and not self.reasons:
            raise ValueError("failed guards require a concrete rejection reason")


@dataclass(frozen=True, slots=True)
class LocalWitnessDecision:
    status: Literal["matched", "absent", "unknown"]
    need_id: str
    source_key: str
    spans: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    admitted: bool
    route: Literal["rejected", "typed_local", "legacy_strict"]
    reason: str
    matched_need_ids: tuple[str, ...] = ()


def choose_admission(guards: HardGuards, *, legacy_qualified: bool,
                     witness: LocalWitnessDecision) -> AdmissionDecision:
    if not guards.allowed:
        return AdmissionDecision(False, "rejected", guards.reasons[0])
    if witness.status == "matched":
        return AdmissionDecision(True, "typed_local", "verified_local_demand", (witness.need_id,))
    if witness.status == "absent":
        return AdmissionDecision(False, "rejected", "missing_local_demand")
    return AdmissionDecision(legacy_qualified, "legacy_strict", "unverified_legacy_semantics")


def choose_need_admission(probe: Mapping[str, Any], *, query_id: str, text: str,
                          legacy_qualified: bool, missing_exact: tuple[str, ...]
                          ) -> tuple[AdmissionDecision, LocalWitnessDecision]:
    """Rebuild the supported need and body proof, never deserialize an approval.

    Called only after source/reference/subject policy checks. Parent identities
    remain the separate audited-parent attribution gate; they do not veto an
    independently supported child need.
    """
    import hashlib
    from .admission_local_binding import default_local_witness
    from .question_retrieval_needs import retrieval_needs

    status: Literal["matched", "absent", "unknown"] = "unknown"
    spans: tuple[tuple[int, int], ...] = ()
    question = str(probe.get("reference_body_query") or probe.get("query_text") or "")
    current = retrieval_needs(question)
    from .admission_grammar import NEW_RELATIONS, parse_admission_frame
    from .admission_relations import relation_local_witness
    frame = parse_admission_frame(question)
    if frame is not None and frame.operator in NEW_RELATIONS:
        proof, spans = relation_local_witness(frame, text)
        status = "unknown" if proof is None else "matched" if proof else "absent"
        if probe.get("query_origin") == "retrieval_need" and (
                str(probe.get("need_relation") or "") != frame.operator
                or str(probe.get("need_subject") or "").casefold() != frame.subject.casefold()):
            status, spans = "absent", ()
    # Preserve the separately validated default primitive. New relational
    # frames above have their own current-body proof; unknown forms stay strict.
    if (probe.get("query_origin") == "retrieval_need"
            and len(current) == 1 and current[0].relation == "default"
            and str(probe.get("need_relation") or "") == "default"
            and current[0].subject.casefold() == str(probe.get("need_subject") or "").casefold()):
        proof, spans = default_local_witness({**probe, "text": probe.get("query_text"),
                                             "query_id": query_id}, text)
        status = "unknown" if proof is None else "matched" if proof else "absent"
    witness = LocalWitnessDecision(status, query_id,
        hashlib.sha256(text.encode("utf-8")).hexdigest(), spans)
    guards = HardGuards(not missing_exact, ("missing_exact_terms",) if missing_exact else ())
    return choose_admission(guards, legacy_qualified=legacy_qualified, witness=witness), witness
