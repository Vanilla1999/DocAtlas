"""Select checked documentation evidence against the real delivery budget.

The input is the merged, live-source-checked pool, not a retrieval lane. Query
terms only come from the original question and explicit host lookups. Source
metadata never contributes a lexical match. Selection retains whole source
rows, including their exact citations, text, hashes and coordinates.
An explicit document locator can route a checked source independently of body
words; the existing source-reference verifier must bind that locator first.

Coherent neighboring rows are considered together: several clauses can share
the same query words. A large section may instead contribute complete checked
windows. Common words have less weight by their frequency in the checked pool.
Query relevance stays fixed for complementary sections; body-content similarity
discounts redundant sections without a second penalty for repeated query words.
None of this establishes answer completeness.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
import json
import math
import os
import re

from docmancer.docs.domain.original_body_discovery import experimental_context_max_tokens
from docmancer.retrieval.lexical_terms import lexical_terms, query_terms, explicit_source_locators
from docmancer.docs.domain.query_reference_binding import prepare_reference_probe

from .context_json import serialize_context_json
from .context_query_probes import authoritative_queries, literal_query_probe
from .experimental_context_finalization import _rebuild
from .model_visible_projection import _refresh_estimate
from .projection_tokenizer import projection_token_count
from .query_trace import query_trace_enabled
from .standalone_text_view import COMPACT_TEXT_MAX_TOKENS, render_standalone_text


POLICY = "joint_checked_body_mmr_v1"
_CLI_LITERAL = re.compile(r"(?<!\w)--[A-Za-z][A-Za-z0-9_-]*(?!\w)")
_TRACE_ROW_LIMIT = 512


class _SelectionObservation:
    """Bounded independent ledger, never consulted by the selector."""

    def __init__(self, retrieval: dict, rows: list[dict]) -> None:
        self.state = None
        self.rows = []
        if not query_trace_enabled():
            return
        try:
            self.rows = [{"evidence_id": row.get("evidence_id"),
                          "line_start": row.get("line_start"), "line_end": row.get("line_end"),
                          "decision": "not_considered"} for row in rows[:_TRACE_ROW_LIMIT]]
            self.state = {"row_count": len(rows), "row_limit": _TRACE_ROW_LIMIT,
                          "omitted_rows": max(0, len(rows) - len(self.rows)), "rows": self.rows}
            retrieval.setdefault("retrieval_diagnostics", {}).setdefault(
                "docs_context_projection", {})["joint_selection_observation"] = self.state
        except Exception:
            self.state = None
            self.rows = []

    def decision(self, item: _Unit, decision: str,
                 priority: Callable[[_Unit], tuple[float, float, int]], **details: object) -> None:
        if self.state is None:
            return
        try:
            indices = item.indices
            if not any(index < len(self.rows) for index in indices):
                return
            score = priority(item)
            for index in indices:
                if index < len(self.rows):
                    row = self.rows[index]
                    if "first_decision" not in row:
                        row.update(first_decision=decision, first_unit_rows=len(indices),
                                   first_selected_before=details.get("selected_before"),
                                   first_gain_per_cost=score[0], first_relevance=score[1],
                                   first_cost_bytes=item.cost,
                                   first_redundancy=score[1] - score[0] * math.sqrt(item.cost))
                    row.update(decision=decision, gain_per_cost=score[0],
                               relevance=score[1], cost_bytes=item.cost,
                               redundancy=score[1] - score[0] * math.sqrt(item.cost),
                               unit_rows=len(indices), **details)
        except Exception:
            self.state["diagnostic_error"] = True

    def selected(self, rows: list[dict]) -> None:
        if self.state is None:
            return
        try:
            ids = {row.get("evidence_id") for row in rows}
            for row in self.rows:
                row["joint_output"] = row["evidence_id"] in ids
        except Exception:
            self.state["diagnostic_error"] = True


@dataclass(frozen=True)
class _Unit:
    group: int
    indices: tuple[int, ...]
    features: frozenset[tuple[str, str]]
    locator_queries: frozenset[str]
    terms: frozenset[str]
    cost: int
    vector_norm: float


def _source_section(row: dict, snapshot: dict) -> str:
    source = snapshot[row["evidence_id"]]["source"]
    reference = source.get("_reference_evidence") or {}
    return json.dumps([
        row.get("project_identity"), row.get("path_or_url"), row.get("scope"),
        row.get("authority"), row.get("version_binding"), row.get("section"),
        source.get("_source_snapshot_sha256"), source.get("_source_catalog_hash"),
        source.get("generation_id"), reference.get("source"),
    ], ensure_ascii=False, sort_keys=True)


def _groups(rows: list[dict], snapshot: dict) -> list[tuple[int, ...]]:
    """Keep gaps and distinct source/scope/version bindings separate."""
    sections: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        sections.setdefault(_source_section(row, snapshot), []).append(index)
    groups: list[tuple[int, ...]] = []
    for key in sorted(sections):
        current: list[int] = []
        end = -1
        for index in sorted(sections[key], key=lambda i: (
            rows[i]["line_start"], rows[i]["line_end"], rows[i]["evidence_id"],
        )):
            row = rows[index]
            if current and row["line_start"] > end + 1:
                groups.append(tuple(current))
                current = []
            current.append(index)
            end = max(end, row["line_end"])
        if current:
            groups.append(tuple(current))
    return groups


def _bound_locator_queries(row: dict, snapshot: dict, queries: dict) -> frozenset[str]:
    """Recheck literal document nominations without manufacturing body credit.

    Matching a path string in a selected top-N cannot prove uniqueness or
    scope. Use the request's prepared reference plan and existing verifier,
    whose source binding came from the complete allowed snapshot. This ranking
    route never alters retrieval_query_matches or the query credit ceiling.
    """
    source = snapshot[row["evidence_id"]]["source"]
    plans = source.get("_reference_plans") or {}
    routed = set()
    for query_id, query in queries.items():
        if not explicit_source_locators(query["text"]):
            continue
        plan = plans.get(query["text"]) or {}
        mentions = {
            ref["mention"]["mention_id"] for ref in plan.get("references") or ()
            if ref.get("role") == "source_locator" and ref.get("state") == "resolved"
            and (ref.get("mention") or {}).get("explicit") is True
            and (ref.get("mention") or {}).get("syntax_role") == "source_locator"
        }
        if not mentions:
            continue
        checked, reason = prepare_reference_probe(
            literal_query_probe(query), candidate={**source, **row},
            evidence_text=row["snippet"],
        )
        if reason is None and any(
            binding.get("role") == "source_locator" and binding.get("mention_id") in mentions
            for binding in checked.get("reference_bindings") or ()
        ):
            routed.add(query_id)
    return frozenset(routed)


def _text_fits(text: str, limit: int) -> bool:
    body = text.encode("utf-8")
    # The cheap bound also avoids tokenizing a packet already known to be large.
    return len(body) <= 4 * limit and projection_token_count(body) <= limit


def _delivery_fits(payload: dict, limit: int) -> bool:
    """Use the selected MCP text route, with its actual representation guards.

    Source URIs and the selection/quality envelope must already be attached.
    The compact encoder checks model-view, standalone and assembly limits;
    canonical JSON is the very same serializer used by the legacy text lane.
    A compatible canonical fallback is allowed exactly as at the MCP boundary.
    """
    if (os.environ.get("DOCATLAS_MCP_TEXT_FALLBACK") == "1"
            and os.environ.get("DOCATLAS_MCP_COMPACT_TEXT") == "1"):
        rendered = render_standalone_text(payload)
        if rendered.text is not None:
            return _text_fits(rendered.text, limit)
    elif os.environ.get("DOCATLAS_MCP_MODEL_VIEW") == "1":
        from .model_context_view import ModelViewError, canonical, encode_model_result
        try:
            rendered = encode_model_result(payload)
        except ModelViewError:
            return False
        if rendered is not None:
            return _text_fits(canonical(rendered[0]), limit)
    return _text_fits(serialize_context_json(payload), limit)


def _selected_packet(payload: dict, snapshot: dict, retrieval: dict, rows: list[dict], *,
                     selection: dict) -> tuple[dict, dict]:
    projected, receipts = _rebuild(payload, snapshot, retrieval, rows,
                                   reason="joint_context_selection")
    omitted = selection["candidate_rows"] - len(rows)
    reasons = ["coverage_unverified"] if rows else []
    if omitted:
        reasons.append("joint_selection_partial")
    projected["source_selection"] = {
        **selection, "selected_rows": len(rows), "omitted_rows": omitted,
    }
    projected["context_quality"] = {
        "status": "unverified" if rows else "unavailable", "reasons": reasons,
    }
    if rows:
        projected["status"] = "truncated" if omitted or payload.get("status") == "truncated" else "ok"
    else:
        limited = selection["budget_limited"] or selection["reference_limited"]
        projected["reason_code"] = ("source_context_budget_limited" if limited
                                    else "no_relevant_source_context")
        projected["missing"] = [
            "No complete checked source window fit the delivery and reference budgets."
            if limited else
            "No checked source body was selected for the explicit questions; completeness is unassessed."
        ]
    _refresh_estimate(projected)
    return projected, receipts


def finalize_joint_context_delivery(payload: dict, snapshot: dict, retrieval: dict) -> tuple[dict, dict]:
    """Reprice the final bound packet without acquiring or issuing more sources."""
    cap = experimental_context_max_tokens()
    selection = payload.get("source_selection") or {}
    if cap is None or selection.get("policy") != POLICY:
        return payload, snapshot
    limit = min(cap, COMPACT_TEXT_MAX_TOKENS)
    result, bound = payload, snapshot
    while result.get("sources") and not _delivery_fits(result, limit):
        # Retract whole rows from the last added group if the final envelope
        # changed. Recompute attribution; source fields remain indivisible.
        result, bound = _selected_packet(result, bound, retrieval, result["sources"][:-1],
                                         selection={**selection, "budget_limited": True})
    return result, bound


def select_joint_context(payload: dict, snapshot: dict, retrieval: dict, *,
                         max_source_references: int | None = None) -> tuple[dict, dict]:
    """Choose a relevant subset of the merged pool; never trim a source row.

    Called only by the native, compression-off route after source continuation
    locators are attached, before registering the selected reference batch.
    The explicit section-compression selector retains its own policy.
    """
    rows = payload.get("sources") or []
    cap = experimental_context_max_tokens()
    if not rows or cap is None:
        return payload, snapshot
    observation = _SelectionObservation(retrieval, rows)
    limit = min(cap, COMPACT_TEXT_MAX_TOKENS)
    queries = authoritative_queries(retrieval.get("documentation_query_plan") or {})
    # A missing authoritative plan is an upstream contract failure, not license
    # to reconstruct a question from retrieved text or generated probes.
    if not queries:
        raise ValueError("joint_context_selection_requires_authoritative_queries")
    semantic_mode = os.environ.get("DOCATLAS_EXPERIMENT_JOINT_RELEVANCE", "off")
    if semantic_mode not in {"off", "mini"}:
        raise ValueError("DOCATLAS_EXPERIMENT_JOINT_RELEVANCE must be off or mini")
    semantic_scores = None
    if semantic_mode == "mini":
        from .experimental_selection_modes import score_joint_relevance
        semantic_scores, semantic_receipt = score_joint_relevance(
            queries, rows, os.environ.get("DOCATLAS_EXPERIMENT_MINI_PATH", ""),
        )
        if observation.state is not None:
            observation.state["semantic_relevance"] = semantic_receipt
            for index, row in enumerate(observation.rows):
                row["semantic_lane_scores"] = {
                    key: values[index] for key, values in semantic_scores.items()
                }
    literals = sorted({value.group() for query in queries.values()
                       for value in _CLI_LITERAL.finditer(query["text"])})
    literal_patterns = {"literal:" + value.casefold(): re.compile(
        r"(?<!\w)" + re.escape(value) + r"(?!\w)", re.IGNORECASE,
    ) for value in literals}

    def body_terms(text: str) -> frozenset[str]:
        # The shared tokenizer already preserves whole underscore identifiers.
        # Only punctuation-bearing CLI options need an extra exact feature;
        # an identifier must not gain a second copy of the same lexical credit.
        return frozenset((*lexical_terms(text), *(key for key, pattern in literal_patterns.items()
                                                if pattern.search(text))))

    terms_by_query = {key: frozenset((*query_terms(value["text"]), *(
        "literal:" + match.group().casefold() for match in _CLI_LITERAL.finditer(value["text"])
    ))) for key, value in queries.items()}
    row_terms = [body_terms(row["snippet"]) for row in rows]
    frequency = Counter(term for terms in row_terms for term in terms)
    # Smoothed information content needs no language-specific stopword list.
    # These weights are ranking features only. Even the best relative body
    # match cannot claim coverage of an absent requested identifier or relation.
    information = {term: math.log1p((len(rows) - count + 0.5) / (count + 0.5))
                   for term, count in frequency.items()}
    absent_information = math.log1p((len(rows) + 0.5) / 0.5)
    feature_weight: dict[tuple[str, str], float] = {}
    for key, terms in terms_by_query.items():
        total = sum(information.get(term, absent_information) for term in sorted(terms))
        if total:
            feature_weight.update({(key, term): information.get(term, absent_information) / total
                                   for term in terms})
    row_features = [frozenset((key, term) for key, terms in terms_by_query.items()
                             for term in terms & body) for body in row_terms]
    row_locators = [_bound_locator_queries(row, snapshot, queries) for row in rows]
    grouped = _groups(rows, snapshot)

    def unit(group: int, indices: tuple[int, ...]) -> _Unit:
        return _Unit(
            group, indices,
            frozenset(feature for index in indices for feature in row_features[index]),
            frozenset(key for index in indices for key in row_locators[index]),
            frozenset(term for index in indices for term in row_terms[index]),
            max(1, sum(len(json.dumps(rows[index], ensure_ascii=False).encode("utf-8"))
                       for index in indices)),
            math.sqrt(sum(information[term] ** 2 for term in sorted(
                {term for index in indices for term in row_terms[index]}))),
        )

    whole = [unit(group, indices) for group, indices in enumerate(grouped)]
    pending = {item.indices: item for item in whole if item.features or item.locator_queries}
    eligible = {index for item in pending.values() for index in item.indices}
    selected: list[int] = []
    selected_set: set[int] = set()
    selected_groups: set[int] = set()
    selected_units: list[_Unit] = []
    selected_references: set[str] = set()
    rejected: set[int] = set()
    reference_rejected: set[int] = set()
    result, bound = payload, snapshot

    # Relative relevance is computed independently for every explicit query.
    # Its scale is the best body match in this same checked pool, never an
    # asserted semantic coverage label or an oracle-dependent threshold.
    best_query_mass = {
        key: max((sum(feature_weight[feature] for feature in sorted(item.features)
                      if feature[0] == key) for item in whole), default=0.0)
        for key in queries
    }

    def packet(indices: list[int], *, budget_limited: bool) -> tuple[dict, dict]:
        return _selected_packet(payload, snapshot, retrieval, [rows[index] for index in indices], selection={
            "policy": POLICY, "scope": "source_checked_merged_candidates",
            "query_count": len(queries), "candidate_rows": len(rows),
            "eligible_rows": len(eligible), "budget_limited": budget_limited,
            "reference_limited": bool(reference_rejected - set(indices)),
        })

    def adjacent(item: _Unit) -> bool:
        return any(
            rows[index]["line_start"] <= rows[other]["line_end"] + 1
            and rows[other]["line_start"] <= rows[index]["line_end"] + 1
            for index in item.indices for other in grouped[item.group] if other in selected_set
        )

    def similarity(left: _Unit, right: _Unit) -> float:
        if not left.vector_norm or not right.vector_norm:
            return 0.0
        return min(1.0, sum(information[term] ** 2 for term in sorted(left.terms & right.terms))
                   / (left.vector_norm * right.vector_norm))

    while pending:
        def priority(item: _Unit) -> tuple[float, float, int]:
            completing = item.group in selected_groups and adjacent(item)
            features = item.features or (whole[item.group].features if completing else frozenset())
            if not features and not item.locator_queries:
                return (0.0, 0.0, -min(item.indices))
            mass = Counter()
            for feature in sorted(features):
                mass[feature[0]] += feature_weight[feature]
            # An exact source nomination is a separate routing signal, not
            # a match in the body. It keeps locator-only reads possible while
            # normal attribution is independently rebuilt below.
            if semantic_scores is None:
                relevance = sum(max(
                    mass[key] / best_query_mass[key] if best_query_mass[key] else 0.0,
                    1.0 if key in item.locator_queries else 0.0,
                ) for key in queries) / len(queries)
            else:
                indices = whole[item.group].indices if completing else item.indices
                relevance = sum(max(
                    max(semantic_scores[key][index] for index in indices),
                    1.0 if key in item.locator_queries else 0.0,
                ) for key in queries) / len(queries)
            # This is an MMR-style choice: equal scales for query relevance and
            # content redundancy, not a hard one-hit set-cover stopping rule.
            # Siblings of a partly selected coherent section are complementary
            # continuation, so they are compared against other sections only.
            redundancy = max((similarity(item, previous) for previous in selected_units
                              if previous.group != item.group), default=0.0)
            gain = relevance - redundancy
            return (gain / math.sqrt(item.cost), relevance, -min(item.indices))

        candidate = max(pending.values(), key=priority)
        if priority(candidate)[0] <= 0:
            if observation.state is not None:
                for remaining in pending.values():
                    observation.decision(remaining, "nonpositive_gain", priority)
            break
        del pending[candidate.indices]
        trial_indices = [*selected, *candidate.indices]
        # Every supported view includes every original snippet. This lower
        # bound is safe before building/tokenizing an impossible large packet.
        text_bytes = sum(len(rows[index]["snippet"].encode("utf-8")) for index in trial_indices)
        references = {str(rows[index]["source_uri"]) for index in candidate.indices
                      if rows[index].get("source_uri")}
        references_fit = (max_source_references is None
                          or len(selected_references | references) <= max_source_references)
        trial = receipts = None
        fits = False
        if text_bytes <= 4 * limit and references_fit:
            trial, receipts = packet(trial_indices, budget_limited=bool(rejected - set(trial_indices)))
            fits = _delivery_fits(trial, limit)
        if not fits:
            if observation.state is not None:
                observation.decision(candidate, "delivery_budget" if references_fit else "reference_limit", priority,
                                     selected_before=len(selected), trial_text_bytes=text_bytes,
                                     fit_check=("reference_limit" if not references_fit else
                                                "text_lower_bound" if text_bytes > 4 * limit else "rendered_packet"))
            if references_fit:
                rejected.update(candidate.indices)
            else:
                reference_rejected.update(candidate.indices)
            if len(candidate.indices) > 1:
                # A section is not silently clipped. Its original checked rows
                # compete again under the same joint objective and wire budget.
                for index in candidate.indices:
                    pending[(index,)] = unit(candidate.group, (index,))
            continue
        selected.extend(candidate.indices)
        if observation.state is not None:
            observation.decision(candidate, "selected", priority, selected_before=len(selected) - len(candidate.indices))
        selected_set.update(candidate.indices)
        selected_groups.add(candidate.group)
        selected_units.append(candidate)
        selected_references.update(references)
        result, bound = trial, receipts

    # Reprice the truthful final omissions envelope too. No URI, attribution,
    # diagnostics, or selection field is appended after this final wire check.
    result, bound = packet(selected, budget_limited=bool(rejected - selected_set))
    result, bound = finalize_joint_context_delivery(result, bound, retrieval)
    observation.selected(result.get("sources") or [])
    return result, bound
