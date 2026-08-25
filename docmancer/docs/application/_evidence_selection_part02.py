"""Implementation shard 2 for evidence_selection."""
from __future__ import annotations

from ._evidence_selection_shared import *  # noqa: F401,F403

from ._evidence_selection_part01 import _candidate_preference, _candidate_source_view, _jaccard_millis, _marginal_utility, _repair_mandatory_selection, _selection_terms
from .evidence_semantic_density import source_fact_unit_semantic_score, source_scoped_behavioral_match

def _scope_requirement_value(
    requirements: Sequence[EvidenceRequirement], kind: str,
) -> str | None:
    values = {item.value for item in requirements if item.kind == kind and item.mandatory}
    if len(values) > 1:
        raise ValueError(f"canonical requirements contain conflicting {kind} scope")
    return next(iter(values), None)


def _facet_requirement_matches(value: str, haystack: str) -> bool:
    kind, _, detail = value.partition(":")
    if kind == "comparison":
        left, separator, right = detail.partition(":")
        return bool(
            separator
            and requirement_value_visible(left, haystack)
            and requirement_value_visible(right, haystack)
            and (
                re.search(r"\b(?:while|whereas|but|instead|compare|difference|versus|vs\.?|unlike|does\s+not)\b", haystack)
                or re.search(r"\breturns?\b.*\b(?:runs|collects|schedules)\b", haystack)
            )
        )
    if kind == "result_access":
        entity, separator, _ = detail.partition(":")
        return bool(
            separator
            and requirement_value_visible(entity, haystack)
            and "result" in haystack
            and re.search(r"\b(?:obtain|get|retrieve|await)\b", haystack)
        )
    if kind == "request_handling":
        return any(
            re.search(r"\brequest\b|\bзапрос", sentence)
            and re.search(r"\b(?:handles?|process(?:es|ing)?|dispatch(?:es|ing)?|routes?|validates?|forwards?)\b", sentence)
            and re.search(r"\b(?:handler|router|server|tool|transport|service|registry)\b", sentence)
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack)
        )
    if kind == "architecture":
        component_pattern = (
            r"\b(?:server|handler|router|service|transport|registry|adapter|layer|module|"
            r"ui|application|domain|infrastructure)\b"
        )
        relation_pattern = (
            r"\b(?:routes?|dispatch(?:es)?|coordinates?|connects?|composes?|through|"
            r"состоит|связывает)\b|->"
        )
        return any(
            len(set(re.findall(component_pattern, sentence))) >= 2
            and re.search(relation_pattern, sentence)
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack)
        )
    if kind == "responsiveness":
        return any(
            re.search(r"\b(?:non[- ]blocking|asynchronous|async|does\s+not\s+block)\b", sentence)
            and re.search(r"\b(?:worker|background|event\s+loop|queue|thread|task)\b", sentence)
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack)
        )
    if kind in {"behavior", "usage", "workflow"}:
        patterns = {
            "behavior": r"\b(?:reports?|returns?|provides?|shows?|contains?|lists?|возвращает|показывает|сообщает|содержит|перечисляет)\b",
            "usage": r"\b(?:use|used|call|called|when|should|использовать|используется|применять|применяется|когда)\b",
            "workflow": r"\b(?:run|follow|then|after|before|retry|prepare|first|next|запустить|выполнить|затем|после|перед|повторить|сначала)\b",
        }
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", haystack):
            if not requirement_value_visible(detail, sentence):
                continue
            if re.search(
                r"\b(?:does|do|did|is|are|was|were|should|must|can|could|would|will)\s+not\b"
                r"|\b(?:never|cannot|can't|mustn't|shouldn't)\b"
                r"|\b(?:не\s+следует|не\s+нужно|нельзя|никогда\s+не)\b",
                sentence,
            ):
                continue
            entity_pattern = re.escape(detail.casefold())
            marker_pattern = patterns[kind]
            if kind == "behavior":
                relational_match = re.search(
                    rf"{entity_pattern}(?:\W+\w+){{0,6}}?\W+{marker_pattern}", sentence,
                )
            else:
                relational_match = re.search(
                    rf"(?:{entity_pattern}(?:\W+\w+){{0,6}}?\W+{marker_pattern}"
                    rf"|{marker_pattern}(?:\W+\w+){{0,6}}?\W+{entity_pattern})",
                    sentence,
                )
            if kind == "workflow":
                markers = re.findall(marker_pattern, sentence)
                has_sequence = re.search(
                    r"\b(?:then|after|before|first|next|затем|после|перед|сначала)\b",
                    sentence,
                )
                relational_match = bool(relational_match and len(markers) >= 2 and has_sequence)
            if relational_match:
                return True
        return False
    if kind == "recall_mechanism":
        return bool(re.search(r"\b(?:exact[- ]term|exact match|exact query)\b", haystack) and re.search(
            r"\b(?:recall|retrieve|retrieval|match|lookup)\b", haystack,
        ))
    if kind == "authority_invariant":
        return bool(re.search(r"\b(?:authority|scope)\b", haystack) and re.search(
            r"\b(?:unchanged|preserv(?:e|es|ed)|without\s+(?:widening|expanding|broadening)|does\s+not\s+(?:widen|expand|broaden))\b",
            haystack,
        ))
    return False


def _code_group_fragments(value: str) -> tuple[str, ...]:
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()
    if not isinstance(decoded, list):
        return ()
    return tuple(
        str(fragment).strip()
        for fragment in decoded
        if str(fragment).strip()
    )


def _candidate_code_blocks(candidate: EvidenceCandidate) -> tuple[str, ...]:
    metadata = candidate.original.get("metadata")
    snippets = metadata.get("code_snippets") if isinstance(metadata, Mapping) else None
    if not isinstance(snippets, (list, tuple)):
        snippets = ()
    blocks = [
        str(item.get("code") or "").strip()
        for item in snippets or ()
        if isinstance(item, Mapping) and str(item.get("code") or "").strip()
    ]
    if blocks:
        return tuple(blocks)
    return tuple(match.group(1).strip() for match in re.finditer(
        r"```[^\n]*\n(.*?)```", candidate.display_text, re.DOTALL,
    ) if match.group(1).strip())


def _code_group_requirement_matches(value: str, candidate: EvidenceCandidate) -> bool:
    fragments = _code_group_fragments(value)
    return bool(fragments) and any(
        all(fragment.casefold() in block.casefold() for fragment in fragments)
        for block in _candidate_code_blocks(candidate)
    )


def _legacy_requirement_matches_unit(
    requirement: EvidenceRequirement,
    unit: AnswerUnit,
    candidate: EvidenceCandidate,
) -> bool:
    text = unit.text.casefold()
    if not unit.proposition and requirement.kind not in {"code_group"}:
        return False
    if requirement.kind in {"target_declaration", "preserve_declaration"}:
        wanted = requirement.value.casefold().replace("\\", "/")
        source = candidate.source_identity.casefold().replace("\\", "/")
        matches = (
            any(symbol.casefold() == wanted for symbol in candidate.symbols)
            or source == wanted
            or source.endswith("/" + wanted)
        )
    elif requirement.kind == "behavioral_contract":
        if requirement.query_extraction_kind == "source_fact":
            matches = source_scoped_behavioral_match(requirement, unit.text, candidate)
        else:
            terms = {
                token for token in re.findall(r"[a-z0-9_]+", requirement.value.casefold())
                if token not in {"a", "an", "and", "for", "in", "of", "the", "to"}
            }
            matches = len(terms & set(re.findall(r"[a-z0-9_]+", text))) >= min(3, len(terms))
    elif requirement.kind == "cross_module_invariant":
        targets = [value.casefold() for value in requirement.value.splitlines() if value]
        matches = candidate.authority == "canonical" and any(
            _PATCH_FACT_RE.search(segment)
            and all(target in segment.casefold() for target in targets)
            for segment in re.split(r"(?<=[.!?])\s+", unit.text)
        )
    elif requirement.kind in {"exact_term", "entity"}:
        matches = requirement_value_visible(requirement.value, unit.text)
    elif requirement.kind == "facet":
        matches = _facet_requirement_matches(requirement.value, text)
    elif requirement.kind == "code_group":
        fragments = _code_group_fragments(requirement.value)
        matches = bool(fragments) and all(fragment.casefold() in text for fragment in fragments)
    elif requirement.kind == "canonical_policy":
        matches = bool(_PATCH_FACT_RE.search(unit.text))
    elif requirement.kind in {"evidence_path", "target_path", "project_identity", "module_id", "exact_version", "exact_snapshot"}:
        # These obligations are bound by source metadata.  They still need a
        # concrete visible proposition so a successful answer never cites a
        # heading-only or empty chunk.
        matches = unit.proposition
    elif requirement.kind == "unsupported_query":
        matches = False
    else:
        matches = requirement.value.casefold() in text
    if matches and requirement.qualifiers:
        matches = all(_QUALIFIER_PATTERNS[value].search(unit.text) for value in requirement.qualifiers)
    return bool(matches)


def _witness_for_requirement(
    requirement: EvidenceRequirement,
    candidate: EvidenceCandidate,
) -> RequirementWitness | None:
    obligation = requirement.as_proof_obligation()
    if obligation is not None:
        matched = best_local_proof(
            obligation,
            candidate.answer_units,
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
        source_fact = (
            requirement.kind == "behavioral_contract"
            and requirement.query_extraction_kind == "source_fact"
        )
        matching_units.sort(key=lambda unit: (
            -source_fact_unit_semantic_score(unit.text) if source_fact else 0,
            0 if unit.proposition else 1,
            len(unit.text),
            unit.char_start if unit.char_start is not None else 10**9,
            unit.unit_id,
        ))
        unit = matching_units[0]
        semantic_score = source_fact_unit_semantic_score(unit.text) if source_fact else 0
        proof = LocalProof(
            True,
            subject_score=1,
            relation_score=2 if source_fact else 1,
            value_score=max(1, semantic_score) if source_fact else 1,
            completeness_score=3 + semantic_score if source_fact else 3,
            reason="source_scoped_behavioral_fact" if source_fact else "legacy_local_unit",
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
    if result_kind != "patch_context":
        return tuple(requirements)
    additions = [
        EvidenceRequirement(
            requirement_id=f"canonical_policy:{candidate.stable_id}",
            kind="canonical_policy",
            value=candidate.stable_id,
            public_provenance="canonical_policy_requirement",
        )
        for candidate in candidates
        if candidate.authority == "canonical"
        and str(candidate.original.get("authority") or "").casefold() in {
            "source_of_truth", "project_rule", "explicit_agent_policy",
        }
        and _PATCH_FACT_RE.search(candidate.display_text)
        and any(
            requirement.kind != "canonical_policy"
            and _witness_for_requirement(requirement, candidate) is not None
            for requirement in requirements
        )
    ]
    unique = {item.requirement_id: item for item in (*requirements, *additions)}
    return tuple(unique[key] for key in sorted(unique))


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
            if _policy_polarity(candidate.display_text) != _policy_polarity(representative.display_text):
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
    lowered = value.casefold()
    if re.search(r"\b(?:must\s+not|do\s+not|never|forbidden|prohibited)\b", lowered):
        return "forbidden"
    if re.search(r"\b(?:must|required|shall)\b", lowered):
        return "required"
    return "neutral"


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
                0 if candidate.authority == "canonical" else 1,
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
            "authority": 1000 if candidate.authority == "canonical" else 250,
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
            "generic_source_penalty": int(candidate.authority != "canonical"),
            "ambiguity_penalty": int(candidate.navigation_only),
        })
        prior_terms.update(terms)
        prior_sources.add(source)
        if candidate.module_id:
            prior_modules.add(candidate.module_id)
        prior_symbols.update(symbols)
    return trace


def _authority_conflicts(candidates: Sequence[EvidenceCandidate]) -> set[str]:
    required: dict[str, set[str]] = {}
    forbidden: dict[str, set[str]] = {}
    for candidate in candidates:
        if candidate.authority != "canonical":
            continue
        for line in candidate.display_text.splitlines():
            normalized = " ".join(re.findall(r"[\w]+", line.casefold()))
            if "must not" in line.casefold() or "never" in line.casefold() or "forbidden" in line.casefold():
                key = re.sub(r"\b(?:must|not|never|forbidden|be)\b", " ", normalized)
                forbidden.setdefault(" ".join(key.split()), set()).add(candidate.stable_id)
            elif "must" in line.casefold() or "required" in line.casefold():
                key = re.sub(r"\b(?:must|required|be)\b", " ", normalized)
                required.setdefault(" ".join(key.split()), set()).add(candidate.stable_id)
    return {
        key for key in required.keys() & forbidden.keys() if key
    }

__all__=['_scope_requirement_value', '_facet_requirement_matches', '_code_group_fragments', '_candidate_code_blocks', '_code_group_requirement_matches', '_legacy_requirement_matches_unit', '_witness_for_requirement', '_with_canonical_policy_requirements', '_deduplicate', '_raw_candidate_binding', '_policy_polarity', '_overlap_millis', '_reserve_and_select', '_selected_feature_trace', '_authority_conflicts']
