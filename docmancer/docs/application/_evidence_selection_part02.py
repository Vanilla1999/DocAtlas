"""Implementation shard 2 for evidence_selection."""
from __future__ import annotations

from ._evidence_selection_shared import *  # noqa: F401,F403

from ._evidence_selection_part01 import _candidate_source_view
from ._evidence_selection_part01 import _candidate_window_valid, _candidate_lifecycle_valid, _unit_matches_display

def _scope_requirement_value(
    requirements: Sequence[EvidenceRequirement], kind: str,
) -> str | None:
    values = {item.value for item in requirements if item.kind == kind and item.mandatory}
    if len(values) > 1:
        raise ValueError(f"canonical requirements contain conflicting {kind} scope")
    return next(iter(values), None)


def _facet_requirement_matches(value: str, haystack: str) -> bool:
    # Lexical relation vocabulary is not entailment. Supplied legacy facets
    # remain mandatory and uncovered rather than receiving fabricated proof.
    return False


def _code_group_fragments(value: str) -> tuple[str, ...]:
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()
    if not isinstance(decoded, list) or not decoded:
        return ()
    if any(not isinstance(fragment, str) or not fragment.strip() for fragment in decoded):
        return ()
    return tuple(fragment.strip() for fragment in decoded)


def _candidate_code_blocks(candidate: EvidenceCandidate) -> tuple[str, ...]:
    # Compatibility inspection only; hidden metadata/parent content is not visible.
    return tuple(match.group(1).strip() for match in re.finditer(
        r"```[^\n]*\n(.*?)```", candidate.display_text, re.DOTALL,
    ) if match.group(1).strip())


def _code_group_requirement_matches(value: str, candidate: EvidenceCandidate) -> bool:
    return _witness_for_requirement(EvidenceRequirement("code-group", "code_group", value), candidate) is not None


def _literal_visible(value: str, text: str) -> bool:
    return bool(value) and re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text) is not None


def _legacy_requirement_matches_unit(
    requirement: EvidenceRequirement,
    unit: AnswerUnit,
    candidate: EvidenceCandidate,
) -> bool:
    if not _unit_matches_display(candidate, unit) or requirement.qualifiers:
        return False
    if requirement.kind in {"exact_term", "entity"}:
        return _literal_visible(requirement.value, unit.text)
    if requirement.kind == "code_group":
        fragments = _code_group_fragments(requirement.value)
        blocks = [unit.text] if unit.kind in {"code_block", "code_declaration"} else []
        if unit.kind == "key_value" and re.fullmatch(
            r"(?:const|let|var|final)\s+[A-Za-z_]\w*\s*=\s*\S.*", unit.text,
        ):
            blocks.append(unit.text)
        blocks.extend(match.group(2) for match in re.finditer(r"(`+)([^`\n]+)\1", unit.text))
        return bool(fragments) and any(all(_literal_visible(fragment, block) for fragment in fragments) for block in blocks)
    if requirement.kind == "required_fact":
        # A supplied exact quote is a mechanical match, not a behavioral claim.
        return bool(requirement.value) and unit.text == requirement.value
    return False


def _witness_for_requirement(
    requirement: EvidenceRequirement,
    candidate: EvidenceCandidate,
) -> RequirementWitness | None:
    if requirement.qualifiers or not _candidate_window_valid(candidate) or not _candidate_lifecycle_valid(requirement, candidate):
        return None
    obligation = requirement.as_proof_obligation()
    if obligation is not None:
        matched = best_local_proof(
            obligation,
            tuple(unit for unit in candidate.answer_units if _unit_matches_display(candidate, unit)),
            source=_candidate_source_view(candidate),
            representation_bounded=candidate.answer_units_representation_bounded,
        )
        if matched is None:
            return None
        unit, proof = matched
    else:
        matching_units = [
            unit for unit in candidate.answer_units
            if _legacy_requirement_matches_unit(requirement, unit, candidate)
        ]
        if not matching_units:
            return None
        unit = matching_units[0]
        proof = LocalProof(
            True,
            subject_score=1,
            relation_score=1,
            value_score=1,
            completeness_score=3,
            reason="visible_literal_only",
        )
    return RequirementWitness(
        requirement_id=requirement.requirement_id,
        unit_id=unit.unit_id,
        unit_kind=unit.kind,
        unit_text=unit.text,
        unit_char_start=unit.char_start,
        unit_char_end=unit.char_end,
        unit_content_hash=unit.content_sha256,
        subject_score=proof.subject_score,
        relation_score=proof.relation_score,
        value_score=proof.value_score,
        completeness_score=proof.completeness_score,
    )


def _with_canonical_policy_requirements(
    requirements: Sequence[EvidenceRequirement],
    candidates: Sequence[EvidenceCandidate],
    result_kind: str,
) -> tuple[EvidenceRequirement, ...]:
    # Normative vocabulary does not invent a policy obligation or witness.
    return tuple(requirements)


def _deduplicate(
    candidates: Sequence[EvidenceCandidate],
    config: SelectionConfig,
    requirements: Sequence[EvidenceRequirement],
) -> tuple[list[EvidenceCandidate], list[Omission]]:
    selected: list[EvidenceCandidate] = []
    omissions: list[Omission] = []
    for candidate in candidates:
        duplicate: tuple[OmissionReason, EvidenceCandidate] | None = None
        for representative in selected:
            # Only interchangeable evidence rows may be discarded.
            def semantic_row(row: EvidenceCandidate) -> EvidenceCandidate:
                return replace(
                    row, retrieval_rank=0, component_ranks=(), relevance_millis=0,
                    token_estimate=0, fit_token_estimate=0, reported_token_estimate=None,
                )
            if (
                semantic_row(candidate) == semantic_row(representative)
                and _candidate_source_view(candidate) == _candidate_source_view(representative)
            ):
                duplicate = "exact_duplicate", representative
                break
        if duplicate:
            omissions.append(Omission(candidate.stable_id, duplicate[0], duplicate[1].stable_id))
        else:
            selected.append(candidate)
    return selected, omissions


def _raw_candidate_binding(item: Mapping[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
    display = _display_text(item)
    score = next((
        value for value in (
            item.get("score"), item.get("relevance_score"),
            metadata.get("score"), metadata.get("relevance_score"),
        )
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    ), None)
    return {
        "stable_id": str(
            item.get("stable_chunk_id") or item.get("stable_child_id")
            or metadata.get("stable_chunk_id") or item.get("stable_id") or ""
        ),
        "path_or_url": _source_path(item),
        "parent_logical_id": str(
            item.get("parent_logical_id") or metadata.get("parent_logical_id") or ""
        ),
        "display_content_sha256": hashlib.sha256(display.encode("utf-8")).hexdigest(),
        "supplied_display_content_hash": str(item.get("display_content_hash") or ""),
        "retrieval_rank": _positive_int(
            item.get("retrieval_rank") if item.get("retrieval_rank") is not None else item.get("rank"),
            default=10_000,
        ),
        "relevance_millis": int(round(float(score) * 1000)) if score is not None else 0,
        "symbols": sorted(_symbols(item)),
        "exact_terms": sorted(
            str(value)
            for value in (
                item.get("exact_terms")
                if isinstance(item.get("exact_terms"), (list, tuple, set))
                else [item.get("exact_terms")] if item.get("exact_terms") else []
            )
        ),
        "project_identity": str(item.get("project_identity") or ""),
        "module_id": str(item.get("module_id") or ""),
        "doc_scope": str(item.get("doc_scope") or ""),
    }


def _policy_polarity(value: str) -> str:
    """Compatibility adapter: prose polarity is unknown, not neutral proof."""
    return "unknown"


def _overlap_millis(left: EvidenceCandidate, right: EvidenceCandidate) -> int:
    if not left.parent_logical_id or left.parent_logical_id != right.parent_logical_id:
        return 0
    if None in {left.char_start, left.char_end, right.char_start, right.char_end}:
        return 0
    intersection = max(0, min(left.char_end, right.char_end) - max(left.char_start, right.char_start))
    denominator = min(left.char_end - left.char_start, right.char_end - right.char_start)
    return int(intersection * 1000 / denominator) if denominator > 0 else 0


def _reserve_and_select(
    candidates: Sequence[EvidenceCandidate],
    mandatory: set[str],
    config: SelectionConfig,
    *,
    prefer_proof_completeness: bool = False,
) -> tuple[list[EvidenceCandidate], set[str], list[Omission]]:
    if config.result_kind == "patch_context":
        # Preserve distinct admitted rows in acquisition order. Mandatory
        # evidence still gates readiness; lexical novelty does not gate bytes.
        selected = list(candidates)
        covered = set().union(*(item.covered_requirement_ids for item in selected)) if selected else set()
        return selected, mandatory - covered, []
    fit_reserve = (
        DOCS_SERIALIZATION_RESERVE_TOKENS
        if config.result_kind == "docs_answer"
        else config.wrapper_reserve_tokens
    )
    available = max(1, config.hard_tokens - (fit_reserve or 0)) if config.hard_tokens is not None else None
    selected: list[EvidenceCandidate] = []
    remaining = set(mandatory)
    omissions: list[Omission] = []
    spent = 0
    for candidate in candidates:
        if available is not None and spent + candidate.fit_token_estimate > available:
            omissions.append(Omission(candidate.stable_id, "budget"))
            continue
        selected.append(candidate)
        spent += candidate.fit_token_estimate
        remaining -= candidate.covered_requirement_ids
    return selected, remaining, omissions


def _selected_feature_trace(
    candidates: Sequence[EvidenceCandidate], mandatory: set[str]
) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    prior_terms: set[str] = set()
    prior_sources: set[str] = set()
    prior_modules: set[str] = set()
    prior_symbols: set[str] = set()
    for candidate in candidates:
        terms = {token.casefold() for token in _TOKEN_RE.findall(candidate.display_text) if len(token) > 2}
        source = _normalized_source(candidate.source_identity)
        symbols = set(candidate.symbols)
        trace.append({
            "stable_id": candidate.stable_id,
            "retrieval_relevance": candidate.relevance_millis,
            "exact_term_coverage": len(candidate.covered_requirement_ids),
            "mandatory_requirement_coverage": len(candidate.covered_requirement_ids & mandatory),
            "version_exactness": 1000 if _version_rank(candidate.version_binding) == 0 else 0,
            "usable_snippet": 1000 if candidate.projected_text.strip() else 0,
            "new_source_fact_terms": len(terms - prior_terms),
            "new_module_coverage": int(bool(candidate.module_id and candidate.module_id not in prior_modules)),
            "new_target_symbols": len(symbols - prior_symbols),
            "new_source": int(bool(source and source not in prior_sources)),
            "novelty_millis": int(len(terms - prior_terms) * 1000 / max(1, len(terms))),
            "token_cost": candidate.token_estimate,
            "expansion_cost": 0,
            "stale_risk": int(candidate.freshness.casefold() == "stale"),
            "ambiguity_penalty": int(candidate.navigation_only),
        })
        prior_terms.update(terms)
        prior_sources.add(source)
        if candidate.module_id:
            prior_modules.add(candidate.module_id)
        prior_symbols.update(symbols)
    return trace


__all__=['_scope_requirement_value', '_facet_requirement_matches', '_code_group_fragments', '_candidate_code_blocks', '_code_group_requirement_matches', '_legacy_requirement_matches_unit', '_witness_for_requirement', '_with_canonical_policy_requirements', '_deduplicate', '_raw_candidate_binding', '_policy_polarity', '_overlap_millis', '_reserve_and_select', '_selected_feature_trace']
