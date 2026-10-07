"""Implementation shard 2 for evidence_selection."""
from __future__ import annotations

from ._evidence_selection_shared import *  # noqa: F401,F403

from ._evidence_selection_part01 import _candidate_preference, _candidate_source_view, _jaccard_millis, _marginal_utility, _repair_mandatory_selection, _selection_terms
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
        matching_units.sort(key=lambda unit: (
            len(unit.text),
            unit.char_start if unit.char_start is not None else 10**9,
            unit.unit_id,
        ))
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
            distinct_versions = bool(
                candidate.resolved_version
                and representative.resolved_version
                and candidate.resolved_version.casefold() != representative.resolved_version.casefold()
            )
            if distinct_versions:
                continue
            # Similarity or a shared parent cannot erase distinct quoted bytes,
            # including a negation, punctuation or an unrecognized condition.
            if candidate.display_text != representative.display_text:
                continue
            has_new_symbols = bool(set(candidate.symbols) - set(representative.symbols))
            if candidate.stable_id == representative.stable_id or (
                candidate.parent_logical_id
                and candidate.parent_logical_id == representative.parent_logical_id
                and candidate.content_sha256 == representative.content_sha256
                and not has_new_symbols
            ):
                duplicate = "exact_duplicate", representative
                break
            if (
                _overlap_millis(candidate, representative) >= config.overlap_threshold
                and not (candidate.covered_requirement_ids - representative.covered_requirement_ids)
                and not has_new_symbols
            ):
                duplicate = "overlap_duplicate", representative
                break
            if (
                _normalized_source(candidate.source_identity) == _normalized_source(representative.source_identity)
                and _jaccard_millis(candidate.display_text, representative.display_text, config.shingle_size)
                >= config.near_duplicate_threshold
                and not (candidate.covered_requirement_ids - representative.covered_requirement_ids)
                and not has_new_symbols
            ):
                duplicate = "near_duplicate", representative
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
    fit_reserve = (
        DOCS_SERIALIZATION_RESERVE_TOKENS
        if config.result_kind == "docs_answer"
        else config.wrapper_reserve_tokens
    )
    available = max(1, config.hard_tokens - fit_reserve)
    selected: list[EvidenceCandidate] = []
    remaining = set(mandatory)
    pool = list(candidates)
    omissions: list[Omission] = []
    # Compatibility-only docs projection: a single already-eligible witness
    # may be rendered when the caller did not supply a typed profile. Patch
    # selection and multi-candidate ranking continue through the normal utility
    # algorithm, so this cannot become a proof/readiness bypass.
    if (
        not mandatory
        and config.profile == "generic"
        and config.result_kind == "docs_answer"
        and len(pool) == 1
        and pool[0].fit_token_estimate <= available
    ):
        return [pool[0]], set(), []
    while remaining:
        options = [candidate for candidate in pool if candidate.covered_requirement_ids & remaining]
        if not options:
            break
        def mandatory_choice_key(candidate: EvidenceCandidate) -> tuple[Any, ...]:
            key: tuple[Any, ...] = (
                -len(candidate.covered_requirement_ids & remaining),
            )
            if prefer_proof_completeness:
                # A compositional QuestionPlan may have several witnesses that
                # satisfy the same mandatory facet.  Selection must prefer the
                # strongest local proof before compactness; otherwise a short
                # command example can hide a complete procedure summary from
                # the same source.  Legacy v1-v3 selection keeps its frozen
                # ordering by leaving this flag false.
                key += (-sum(
                    witness.completeness_score
                    for witness in candidate.requirement_witnesses
                    if witness.requirement_id in remaining
                ),)
            return (*key,
                _version_rank(candidate.version_binding),
                0 if candidate.docs_snapshot_exact is True else 1,
                candidate.token_estimate,
                candidate.retrieval_rank,
                candidate.stable_id,
            )

        best = min(options, key=mandatory_choice_key)
        selected.append(best)
        pool.remove(best)
        remaining -= best.covered_requirement_ids
    selected = _repair_mandatory_selection(
        selected,
        candidates,
        mandatory,
        prefer_proof_completeness=prefer_proof_completeness,
    )
    covered_after_repair = set().union(*(
        item.covered_requirement_ids for item in selected
    )) if selected else set()
    remaining = mandatory - covered_after_repair
    selected_ids = {item.stable_id for item in selected}
    pool = [item for item in candidates if item.stable_id not in selected_ids]
    if sum(item.fit_token_estimate for item in selected) > available:
        remaining.add("mandatory_evidence_does_not_fit")
        for candidate in candidates:
            omissions.append(Omission(candidate.stable_id, "budget"))
        return [], remaining, omissions

    spent = sum(item.fit_token_estimate for item in selected)
    selected_sources = {_normalized_source(item.source_identity) for item in selected}
    source_counts: dict[str, int] = {}
    for item in selected:
        key = _normalized_source(item.source_identity)
        source_counts[key] = source_counts.get(key, 0) + 1
    selected_terms = _selection_terms(selected)
    if config.result_kind == "docs_answer" and mandatory and not remaining:
        omissions.extend(Omission(candidate.stable_id, "dominated") for candidate in pool)
        return selected, remaining, omissions
    while pool:
        scored: list[tuple[tuple[Any, ...], EvidenceCandidate, int]] = []
        selected_coverage = set().union(*(
            item.covered_requirement_ids for item in selected
        )) if selected else set()
        selected_symbols = {symbol for item in selected for symbol in item.symbols}
        selected_cost = sum(item.token_estimate for item in selected)
        for candidate in pool:
            if (
                candidate.covered_requirement_ids
                and candidate.covered_requirement_ids <= selected_coverage
                and candidate.token_estimate >= selected_cost
                and not (set(candidate.symbols) - selected_symbols)
            ):
                omissions.append(Omission(candidate.stable_id, "dominated"))
                continue
            source_key = _normalized_source(candidate.source_identity)
            is_mandatory = bool(candidate.covered_requirement_ids & mandatory)
            if not is_mandatory and source_key not in selected_sources and len(selected_sources) >= config.max_sources:
                continue
            if not is_mandatory and source_counts.get(source_key, 0) >= config.max_items_per_source:
                continue
            utility = _marginal_utility(candidate, selected_terms, set())
            ratio = int(utility * 100 / max(1, candidate.token_estimate))
            scored.append(((-ratio, -utility, *_candidate_preference(candidate)), candidate, ratio))
        omitted_ids = {item.stable_id for item in omissions}
        pool = [item for item in pool if item.stable_id not in omitted_ids]
        if not scored:
            break
        _, best, utility_ratio = min(scored, key=lambda row: row[0])
        pool.remove(best)
        source_key = _normalized_source(best.source_identity)
        if utility_ratio < config.marginal_utility_threshold:
            omissions.append(Omission(best.stable_id, "zero_marginal_utility"))
            continue
        if spent + best.fit_token_estimate > available:
            omissions.append(Omission(best.stable_id, "budget"))
            continue
        selected.append(best)
        spent += best.fit_token_estimate
        selected_sources.add(source_key)
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        selected_terms = _selection_terms(selected)
        if spent >= min(available, config.target_tokens - config.wrapper_reserve_tokens):
            break
    selected_ids = {item.stable_id for item in selected}
    omitted_ids = {item.stable_id for item in omissions}
    for candidate in candidates:
        if candidate.stable_id in selected_ids or candidate.stable_id in omitted_ids:
            continue
        source_key = _normalized_source(candidate.source_identity)
        reason: OmissionReason = (
            "source_cap"
            if source_counts.get(source_key, 0) >= config.max_items_per_source
            or (source_key not in selected_sources and len(selected_sources) >= config.max_sources)
            else "dominated"
        )
        omissions.append(Omission(candidate.stable_id, reason))
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
