"""Late-bound semantic-density policy for patch evidence selection.

The selector shards intentionally split normalization, coverage, and fitting.
This module binds one shared policy into those shards after they are imported so
candidate-cap ranking, mandatory repair, and marginal fitting use the same
ordering. It adds no benchmark sentence literals: source-scoped obligations
are proved from source identity, behavioral scope, and normative local text.
"""
from __future__ import annotations

import itertools
import re
from typing import Any, Sequence

from docmancer.docs.application.evidence_models import (
    EvidenceCandidate,
    EvidenceRequirement,
    RequirementWitness,
)


_BEHAVIORAL_FACT_RE = re.compile(
    r"\b(?:must|shall|required|requires?|never|cannot|may\s+not|forbidden|prohibited|"
    r"is\s+reserved\s+for|is\s+allowed\s+only|only\s+(?:after|before|when|if)|"
    r"do\s+not|should\s+not)\b"
    r"|^\s*(?:[-*]\s+)?(?:use|call|delegate|reject|allow|block|keep|return|require)\b",
    re.IGNORECASE,
)
_HARD_NORMATIVE_RE = re.compile(
    r"\b(?:is\s+allowed\s+only|must\s+not|do\s+not|never|cannot|forbidden|prohibited|"
    r"only\s+(?:after|before|when|if))\b",
    re.IGNORECASE,
)
_CONFIG_VALUE_RE = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*\s*:\s*(?:true|false|null|none|[0-9]+)\b",
    re.IGNORECASE,
)
_GENERIC_SCOPE_TOKENS = frozenset({
    "application", "contract", "flow", "gate", "module", "policy",
})
_TOKEN_RE = re.compile(r"[\w.+:/-]+", re.UNICODE)


def _normalized_path(value: str) -> str:
    return str(value or "").strip().replace("\\", "/").rstrip("/").casefold()


def _scope_tokens(value: str) -> tuple[str, ...]:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(value or ""))
    return tuple(
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9_]+", expanded.replace("_", " "))
        if len(token) >= 3
    )


def _source_scoped_behavioral_match(
    requirement: EvidenceRequirement,
    unit_text: str,
    candidate: EvidenceCandidate,
) -> bool:
    wanted_source = _normalized_path(requirement.source_path or "")
    actual_source = _normalized_path(candidate.path_or_url or candidate.source_identity)
    if not wanted_source or not (
        actual_source == wanted_source
        or actual_source.endswith("/" + wanted_source)
        or wanted_source.endswith("/" + actual_source)
    ):
        return False
    if not _BEHAVIORAL_FACT_RE.search(unit_text):
        return False

    scope = requirement.subject or requirement.value
    scope_tokens = set(_scope_tokens(scope))
    if not scope_tokens:
        return False
    unit_tokens = set(_scope_tokens(unit_text))
    symbol_tokens = {
        token
        for symbol in candidate.symbols
        for token in _scope_tokens(symbol)
    }
    source_tokens = set(_scope_tokens(actual_source.rsplit("/", 1)[-1].rsplit(".", 1)[0]))
    domain_tokens = scope_tokens - _GENERIC_SCOPE_TOKENS
    if domain_tokens:
        return bool(domain_tokens & (unit_tokens | symbol_tokens | source_tokens))
    return bool(scope_tokens & (unit_tokens | symbol_tokens | source_tokens))


def _unit_semantic_score(text: str) -> int:
    """Rank local witnesses by contract density, not by shortest byte length."""

    if not _BEHAVIORAL_FACT_RE.search(text):
        return 0
    score = 2
    if _HARD_NORMATIVE_RE.search(text):
        score += 2
    # Exact boolean/numeric configuration values are especially useful to a
    # patching model and must survive over a shorter prose prohibition.
    if _CONFIG_VALUE_RE.search(text):
        score += 4
    return score


def critical_normative_fact_score(candidate: EvidenceCandidate) -> int:
    """Score semantic contract density without rewarding ordinary prose length."""

    return sum(
        _unit_semantic_score(segment.strip())
        for segment in re.split(r"(?<=[.!?])\s+|\n+", candidate.display_text)
        if segment.strip()
    )


def semantic_candidate_preference(candidate: EvidenceCandidate) -> tuple[Any, ...]:
    """Coverage/normative density/relevance/authority precede token cost."""

    return (
        -len(candidate.covered_requirement_ids),
        -critical_normative_fact_score(candidate),
        -len(candidate.symbols),
        -candidate.relevance_millis,
        0 if candidate.authority == "canonical" else 1,
        _version_rank(candidate.version_binding),
        0 if candidate.docs_snapshot_exact is True else 1,
        candidate.token_estimate,
        candidate.retrieval_rank,
        candidate.stable_id,
    )


def semantic_marginal_utility(
    candidate: EvidenceCandidate,
    selected_terms: set[str],
    mandatory: set[str],
) -> int:
    terms = {
        token.casefold()
        for token in _TOKEN_RE.findall(candidate.display_text)
        if len(token) > 2
    }
    novelty = min(80, len(terms - selected_terms) * 4)
    return (
        len(candidate.covered_requirement_ids & mandatory) * 1000
        + len(candidate.covered_requirement_ids) * 180
        + critical_normative_fact_score(candidate) * 140
        + min(100, max(0, candidate.relevance_millis // 10))
        + (120 if candidate.symbols else 0)
        + (100 if candidate.authority == "canonical" else 20)
        + (80 if _version_rank(candidate.version_binding) == 0 else 20)
        + (80 if candidate.docs_snapshot_exact is True else 0)
        + (80 if candidate.projected_text.strip() else 0)
        + novelty
        - (80 if candidate.navigation_only else 0)
    )


def semantic_repair_mandatory_selection(
    selected: Sequence[EvidenceCandidate],
    candidates: Sequence[EvidenceCandidate],
    mandatory: set[str],
    *,
    prefer_proof_completeness: bool = False,
) -> list[EvidenceCandidate]:
    """Repair a complete cover without trading normative facts for a few tokens."""

    if not selected or not mandatory:
        return list(selected)
    current = list(selected)
    current_ids = {item.stable_id for item in current}
    pool = [item for item in candidates if item.stable_id not in current_ids]

    def complete(rows: Sequence[EvidenceCandidate]) -> bool:
        coverage = set().union(*(item.covered_requirement_ids for item in rows)) if rows else set()
        return mandatory <= coverage

    def quality(rows: Sequence[EvidenceCandidate]) -> tuple[Any, ...]:
        completeness: tuple[Any, ...] = ()
        if prefer_proof_completeness:
            completeness = (-sum(
                witness.completeness_score
                for item in rows
                for witness in item.requirement_witnesses
                if witness.requirement_id in mandatory
            ),)
        return (
            *completeness,
            -sum(critical_normative_fact_score(item) for item in rows),
            -sum(item.relevance_millis for item in rows),
            sum(item.authority != "canonical" for item in rows),
            sum(_version_rank(item.version_binding) for item in rows),
            sum(item.token_estimate for item in rows),
            len(rows),
            tuple(sorted(item.stable_id for item in rows)),
        )

    best, best_quality = current, quality(current)
    removals = [
        combo
        for size in (1, 2)
        for combo in itertools.combinations(current, min(size, len(current)))
    ]
    additions = [
        combo
        for size in (1, 2)
        for combo in itertools.combinations(pool, min(size, len(pool)))
    ]
    for removed in removals:
        retained = [item for item in current if item not in removed]
        for added in additions:
            proposal = [*retained, *added]
            proposal_quality = quality(proposal)
            if complete(proposal) and proposal_quality < best_quality:
                best, best_quality = proposal, proposal_quality
    return best


def bind_semantic_density_policy() -> None:
    """Bind policy into all selector shards that resolve helpers at runtime."""

    from docmancer.docs.application import _evidence_selection_part01 as part01
    from docmancer.docs.application import _evidence_selection_part02 as part02
    from docmancer.docs.application import _evidence_selection_part03 as part03

    original_legacy_match = part02._legacy_requirement_matches_unit
    original_witness = part02._witness_for_requirement

    def source_aware_legacy_match(requirement, unit, candidate):
        if (
            requirement.kind == "behavioral_contract"
            and requirement.query_extraction_kind == "source_fact"
        ):
            if not unit.proposition:
                return False
            matches = _source_scoped_behavioral_match(requirement, unit.text, candidate)
            if matches and requirement.qualifiers:
                matches = all(
                    part02._QUALIFIER_PATTERNS[value].search(unit.text)
                    for value in requirement.qualifiers
                )
            return bool(matches)
        return original_legacy_match(requirement, unit, candidate)

    def source_aware_witness(requirement, candidate):
        if not (
            requirement.kind == "behavioral_contract"
            and requirement.query_extraction_kind == "source_fact"
        ):
            return original_witness(requirement, candidate)
        matching_units = [
            unit
            for unit in candidate.answer_units
            if unit.proposition
            and source_aware_legacy_match(requirement, unit, candidate)
        ]
        if not matching_units:
            return None
        matching_units.sort(key=lambda unit: (
            -_unit_semantic_score(unit.text),
            unit.char_start if unit.char_start is not None else 10**9,
            len(unit.text),
            unit.unit_id,
        ))
        unit = matching_units[0]
        semantic_score = _unit_semantic_score(unit.text)
        return RequirementWitness(
            requirement_id=requirement.requirement_id,
            unit_id=unit.unit_id,
            unit_kind=unit.kind,
            unit_text=unit.text,
            unit_char_start=unit.char_start,
            unit_char_end=unit.char_end,
            unit_content_hash=unit.content_sha256,
            subject_score=1,
            relation_score=2,
            value_score=max(1, semantic_score),
            completeness_score=3 + semantic_score,
        )

    part01._candidate_preference = semantic_candidate_preference
    part01._repair_mandatory_selection = semantic_repair_mandatory_selection
    part01._marginal_utility = semantic_marginal_utility
    part02._candidate_preference = semantic_candidate_preference
    part02._repair_mandatory_selection = semantic_repair_mandatory_selection
    part02._marginal_utility = semantic_marginal_utility
    part02._legacy_requirement_matches_unit = source_aware_legacy_match
    part02._witness_for_requirement = source_aware_witness
    part03._candidate_preference = semantic_candidate_preference
    part03._witness_for_requirement = source_aware_witness


def _version_rank(value: str) -> int:
    normalized = str(value or "").strip().casefold().replace("-", "_")
    if normalized in {"exact", "exact_version", "version_exact", "exact_version_indexed"}:
        return 0
    if "fallback" in normalized or normalized in {"latest", "best_effort", "unknown"}:
        return 2
    return 1


__all__ = [
    "bind_semantic_density_policy",
    "critical_normative_fact_score",
    "semantic_candidate_preference",
    "semantic_marginal_utility",
    "semantic_repair_mandatory_selection",
]
