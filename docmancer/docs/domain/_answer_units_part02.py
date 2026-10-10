"""Bounded literal equality and negative residual proof compatibility adapters."""
from __future__ import annotations

from ._answer_units_shared import *  # noqa: F401,F403

from ._answer_units_part01 import (
    AnswerUnit,
    LocalProof,
    _bounded_clauses,
    _contains_term,
    _context_score,
    _effect_relation_valid,
    _normal,
    _purpose_clause,
    _subject_present,
    _subject_spans,
    _word_distance,
)


def _certification_semantic_text(text: str) -> str:
    # Kept for ABI only: this text is never used for semantic certification.
    return text


def _attribute_aliases(attribute: str | None) -> tuple[str, ...]:
    return (attribute,) if attribute else ()


def _attribute_present(attribute: str | None, text: str) -> bool:
    return any(_contains_term(alias, text) for alias in _attribute_aliases(attribute))


def _inventory_anchor(text: str, item_kind: str | None = None) -> re.Match[str] | None:
    return None


def _inventory_facts(
    text: str, *, item_kind: str | None = None,
) -> tuple[int | None, tuple[str, ...], bool]:
    return None, (), False


def _contract_fact_disclaimer(text: str) -> bool:
    # Unknown prose always retains the negative guard, regardless of wording.
    return True


def _contract_fact_relation_valid(text: str) -> bool:
    return False


def _subject_token_overlap(subject: str, text: str) -> int:
    return 0


def _value_score(value_kind: str, text: str, *, cardinality: int | None = None) -> int:
    # Typed values alone do not establish subject/value binding.
    return 0


def _subject_before_pattern(subject: str, pattern: re.Pattern[str], text: str, *, words: int = 8) -> bool:
    return False


def _comparison_predicate_name(value: str) -> str:
    return value


def _comparison_predicates(obligation: ProofObligation, text: str) -> tuple[set[str], set[str]]:
    return set(), set()


def _explicit_comparison_is_local(obligation: ProofObligation, text: str) -> bool:
    return False


def _predicate_has_local_value(match: re.Match[str], clause: str) -> bool:
    return False


def _predicate_is_negated(match: re.Match[str], clause: str) -> bool:
    """Negative ABI adapter: unknown predicate cannot grant approval."""
    return True


def _definition_clause(obligation: ProofObligation, text: str) -> str | None:
    return None


def _behavior_clause(obligation: ProofObligation, text: str) -> tuple[str, bool] | None:
    return None


def _behavior_qualifiers_present(obligation: ProofObligation, clause: str) -> bool:
    return False


def _source_document_behavior_clause(
    obligation: ProofObligation, text: str, source_text: str,
) -> tuple[str, bool] | None:
    return None


def _special_relation_valid(relation: str | None, text: str) -> bool:
    return False


def _unit_identity_valid(unit: AnswerUnit, source: Mapping[str, Any]) -> bool:
    """Validate deterministic local identity and any explicitly supplied content.

    Without source content this is local equality, not source certification.
    Source metadata is never a fallback for missing literal subjects.
    """
    if unit.source_field is not None or unit.char_start is None or unit.char_end is None:
        return False
    if unit.char_start < 0 or unit.char_end - unit.char_start != len(unit.text):
        return False
    digest = hashlib.sha256(unit.text.encode("utf-8")).hexdigest()
    identity = hashlib.sha256(
        f"{unit.kind}\0{unit.char_start}\0{unit.char_end}\0{unit.text}".encode("utf-8")
    ).hexdigest()
    if unit.content_sha256 != digest or unit.unit_id != f"unit-{identity[:20]}":
        return False
    for field in ("content", "text"):
        if field in source:
            content = source[field]
            if not isinstance(content, str) or content[unit.char_start:unit.char_end] != unit.text:
                return False
            # Do not accept a forged substring cut out of another declaration.
            line_start = content.rfind("\n", 0, unit.char_start) + 1
            line_end = content.find("\n", unit.char_end)
            if line_end < 0:
                line_end = len(content)
            if content[line_start:unit.char_start].strip() or content[unit.char_end:line_end].strip():
                return False
    return True


def _explicit_literal_value_proof(
    obligation: ProofObligation, unit: AnswerUnit,
    *, representation_bounded: bool = True,
) -> LocalProof | None:
    """Certify only exact single-line typed key/value equality, never NL meaning."""
    if (
        obligation.kind != "exact_fact"
        or obligation.expected_value is None
        or obligation.relation is not None
        or obligation.target is not None
        or obligation.context is not None
        or obligation.subject_kind not in {"config_key", "env_var", "code_symbol"}
        or obligation.value_kind not in {
            "text", "status", "version_range", "duration", "number", "boolean", "path",
        }
        or unit.source_field is not None
        or unit.kind not in {"key_value", "code_declaration"}
        or "\n" in unit.text or "\r" in unit.text
        or (representation_bounded and len(unit.text) >= MAX_ANSWER_UNIT_CHARS)
        or not _unit_identity_valid(unit, {})
    ):
        return None
    key_value_re = _KEY_VALUE_RE if representation_bounded else _UNBOUNDED_KEY_VALUE_RE
    declaration = key_value_re.fullmatch(unit.text)
    if declaration is None:
        return None
    key, value = declaration.groups()
    expected_key = obligation.subject
    if obligation.attribute is not None:
        expected_key += "." + obligation.attribute
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "`\"'":
        value = value[1:-1]
    if key.strip() != expected_key or value != obligation.expected_value:
        return None
    return LocalProof(True, 3, 3, 3, 9, "explicit_literal_value_only")


def local_proof_for_obligation(
    obligation: ProofObligation,
    unit: AnswerUnit,
    *,
    source: Mapping[str, Any] | None = None,
    representation_bounded: bool = True,
) -> LocalProof:
    """Preserve lifecycle boundaries; a supplied proposition grants no authority."""
    source = source or {}
    lifecycle = str(
        source.get("lifecycle_status") or source.get("project_doc_lifecycle_status") or "active"
    ).casefold()
    if obligation.lifecycle_intent == "current" and lifecycle not in {"", "active", "current"}:
        return LocalProof(False, reason="historical_source_for_current_obligation")
    if obligation.lifecycle_intent == "historical" and lifecycle in {"", "active", "current"}:
        return LocalProof(False, reason="current_source_for_historical_obligation")
    literal_proof = _explicit_literal_value_proof(
        obligation, unit, representation_bounded=representation_bounded,
    )
    if literal_proof is not None:
        if not _unit_identity_valid(unit, source):
            return LocalProof(False, reason="literal_source_span_mismatch")
        return literal_proof
    if not unit.proposition:
        return LocalProof(False, reason="structural_context_not_proposition")
    if obligation.kind == "exact_fact":
        return LocalProof(False, reason="explicit_literal_value_not_bound")
    return LocalProof(False, reason="semantic_detector_removed")


def best_local_proof(
    obligation: ProofObligation,
    units: Iterable[AnswerUnit],
    *,
    source: Mapping[str, Any] | None = None,
    representation_bounded: bool = True,
) -> tuple[AnswerUnit, LocalProof] | None:
    matches: list[tuple[AnswerUnit, LocalProof]] = []
    for index, unit in enumerate(units):
        if representation_bounded and index >= MAX_ANSWER_UNITS:
            # An overflowing supplied packet is unresolved, not partially approved.
            return None
        proof = local_proof_for_obligation(
            obligation, unit, source=source, representation_bounded=representation_bounded,
        )
        if proof.valid:
            matches.append((unit, proof))
    if not matches:
        return None
    matches.sort(key=lambda pair: (
        -pair[1].completeness_score,
        0 if pair[0].proposition else 1,
        len(pair[0].text),
        pair[0].char_start if pair[0].char_start is not None else 10**9,
        pair[0].unit_id,
    ))
    return matches[0]


__all__ = ['_attribute_aliases', '_attribute_present', '_inventory_anchor', '_inventory_facts', '_subject_token_overlap', '_value_score', '_subject_before_pattern', '_special_relation_valid', 'local_proof_for_obligation', 'best_local_proof']
