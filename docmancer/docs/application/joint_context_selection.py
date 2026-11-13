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

from docmancer.docs.domain.delivery_limits import delivery_token_ceiling
from docmancer.docs.domain.original_body_discovery import (
    experimental_context_max_tokens, experimental_selector_settings,
)
from docmancer.retrieval.lexical_terms import (
    character_ngrams, explicit_source_locators, lexical_terms, query_terms,
)
from docmancer.docs.domain.query_reference_binding import prepare_reference_probe

from .context_json import serialize_context_json
from .context_continuation import continuation_fingerprint, continuation_metadata
from .context_query_probes import authoritative_queries, literal_query_probe
from .experimental_context_finalization import _rebuild
from .experimental_pool_pruning import otsu_upper, pool_prune_mode, prune_checked_pool
from .experimental_qwen_checked_pool import PoolTrace, enabled as paired_qwen_enabled, score_rows as paired_score_rows
from .experimental_qwen_pool_units import (
    prune_study_pool, initial_study_units, discard_overlapping_units,
)
from .experimental_qwen_profile import (
    JOINT_POOL_PRUNE_DEFAULT, JOINT_EXPERIMENT_CHOICES as _EXPERIMENT_CHOICES,
    joint_experiment as _experiment,
    study_options as _study_options, validated_minimal_context_enabled,
    validate_paired_context_budget, validate_paired_native_settings,
)
from .model_visible_projection import _refresh_estimate
from .projection_tokenizer import projection_token_count
from .query_trace import query_trace_enabled
from .standalone_text_view import render_standalone_text


POLICY = "joint_checked_body_mmr_v1"
FOCUSED_MAX_TOKENS = 2400


def _delivery_limit(retrieval: dict, cap: int) -> int:
    return min(cap, delivery_token_ceiling(),
               FOCUSED_MAX_TOKENS if retrieval.get("_focused_source_path") else cap)

# Research flags, read per call and off by default (pool pruning: see its
# entry); results in
# eval/blind_project_context/STEP3_DICTIONARY_FREE_RU.md.
#   DOCATLAS_EXPERIMENT_JOINT_TERMS=char4  query/body match on overlapping
#       character 4-grams (McNamee & Mayfield 2004); redundancy stays on words.
#   DOCATLAS_EXPERIMENT_JOINT_PRIORITY=gain  greedy order by marginal gain
#       alone (MMR); the default divides it by sqrt(row bytes).
#   DOCATLAS_EXPERIMENT_JOINT_FUSION=max_shared_scale  CombMAX over explicit
#       queries on one pool-wide scale; the default averages per-query scales.
#   DOCATLAS_EXPERIMENT_POOL_PRUNE=off|heading|body|heading_or_body|vote|
#       own_heading_or_body  keep only whole sections that dictionary-free
#       views keep before selecting. Unset means ``body`` here (accepted by
#       the blind gate, STEP4_POOL_PRUNING_RU.md, STEP7_CONTEXT7_PATH_RU.md)
#       and ``off`` in the MiniLM section selector
#       (experimental_pool_pruning.py; STEP5_PRE_SELECTION_FILTER_RU.md).
#   DOCATLAS_EXPERIMENT_JOINT_RELEVANCE=dense|dense_hybrid  multilingual-E5
#       row/query cosine (experimental_dense_relevance.py) instead of, or
#       averaged with, the lexical lane exactly like mini|hybrid do with the
#       cross-encoder; model directory in DOCATLAS_EXPERIMENT_DENSE_PATH.
#   DOCATLAS_EXPERIMENT_JOINT_CUT=otsu_mean|otsu_union  before the greedy
#       loop keep only the upper Otsu class of whole sections by relevance:
#       the mean relative relevance over queries, or per query and then the
#       union over queries (STEP7_CONTEXT7_PATH_RU.md). No number is added.
def _cost_scale(cost: int, priority_mode: str) -> float:
    return 1.0 if priority_mode == "gain" else math.sqrt(cost)


_CLI_LITERAL = re.compile(r"(?<!\w)--[A-Za-z][A-Za-z0-9_-]*(?!\w)")
_TRACE_ROW_LIMIT = 512


class _SelectionObservation:
    """Bounded independent ledger, never consulted by the selector."""

    def __init__(self, retrieval: dict, rows: list[dict],
                 cost_scale: Callable[[int], float] = math.sqrt) -> None:
        self.state = None
        self.rows = []
        self.cost_scale = cost_scale
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
                                   first_redundancy=score[1] - score[0] * self.cost_scale(item.cost))
                    row.update(decision=decision, gain_per_cost=score[0],
                               relevance=score[1], cost_bytes=item.cost,
                               redundancy=score[1] - score[0] * self.cost_scale(item.cost),
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
    continuation = payload.get("more_context")
    if continuation is not None:
        # Price the continuation envelope on every trial and every retraction,
        # not after the last fit check. Rebuild does not preserve extra fields.
        projected["more_context"] = continuation_metadata(
            continuation["portion"], continuation["continuation_token"],
            selection["candidate_rows"], len(rows),
        )
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
    limit = _delivery_limit(retrieval, cap)
    result, bound = payload, snapshot
    while result.get("sources") and not _delivery_fits(result, limit):
        # Retract whole rows from the last added group if the final envelope
        # changed. Recompute attribution; source fields remain indivisible.
        result, bound = _selected_packet(result, bound, retrieval, result["sources"][:-1],
                                         selection={**selection, "budget_limited": True})
    return result, bound


def _whole_pool_fits(payload: dict, snapshot: dict, retrieval: dict, rows: list[dict], limit: int,
                     query_count: int, max_source_references: int | None) -> bool:
    """Would every checked row, unselected, already fit the delivery envelope?"""
    references = {str(row["source_uri"]) for row in rows if row.get("source_uri")}
    if max_source_references is not None and len(references) > max_source_references:
        return False
    if sum(len(row["snippet"].encode("utf-8")) for row in rows) > 4 * limit:
        return False
    whole, _ = _selected_packet(payload, snapshot, retrieval, rows, selection={
        "policy": POLICY, "scope": "source_checked_merged_candidates",
        "query_count": query_count, "candidate_rows": len(rows),
        "eligible_rows": len(rows), "pruned_rows": 0,
        "budget_limited": False, "reference_limited": False,
    })
    return _delivery_fits(whole, limit)


def _continuation_settings() -> dict:
    """Bind stable host choices that affect selection or its wire pricing."""
    from docmancer.docs.domain.context_presentation import presentation_settings
    study, pool_study = _study_options()
    return {
        **study.continuation_settings(),
        **({"qwen_pool_study": pool_study.receipt()} if pool_study.enabled else {}),
        **presentation_settings(),
        **{name: _experiment(name) for name in _EXPERIMENT_CHOICES},
        "DOCATLAS_EXPERIMENT_POOL_PRUNE": pool_prune_mode(JOINT_POOL_PRUNE_DEFAULT),
        "selector": experimental_selector_settings(),
        # Do not change default continuation identities when the experiment is off.
        **({"paired_qwen": "checked-snippet-v1",
            "paired_model_path": os.environ.get("DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH")}
           if paired_qwen_enabled() else {}),
        **{name: os.environ.get(name) for name in (
            "DOCATLAS_EXPERIMENT_JOINT_RELEVANCE", "DOCATLAS_EXPERIMENT_MINI_PATH",
            "DOCATLAS_EXPERIMENT_DENSE_PATH", "DOCATLAS_MCP_TEXT_FALLBACK",
            "DOCATLAS_MCP_COMPACT_TEXT", "DOCATLAS_MCP_MODEL_VIEW", "DOCATLAS_CONTEXT_ASSEMBLY",
            "DOCATLAS_EXPERIMENT_ACQUISITION_E5", "DOCATLAS_EXPERIMENT_E5_MODEL_DIR",
            "DOCATLAS_EXPERIMENT_E5_CACHE",
        )},
    }


def select_joint_context(
    payload: dict, snapshot: dict, retrieval: dict, *,
    max_source_references: int | None = None, portion: int = 1,
    continuation_token: str | None = None,
    request_binding: dict | None = None,
    finalize_packet: Callable[[dict, dict], tuple[dict, dict]] | None = None,
) -> tuple[dict, dict]:
    """Select a portion from the same live checked pool, without repeated rows.

    Later portions require the fingerprint issued for the unchanged question,
    request scope/targets, source snapshot and host settings. They replay complete earlier selections,
    including the optional host binding/finalization step, and subtract only
    rows actually delivered. The fingerprint is not an authorization token.

    ``finalize_packet`` must only bind already attached source locators and
    finalize the packet; it must not acquire or add evidence. No unbounded
    numeric loop is used: each replay removes rows or stops on no progress.
    ``request_binding`` carries validated request arguments excluding the
    portion number and continuation token, so equal pools cannot hide a change
    of the requested scope, version or target.
    """
    study, pool_study = _study_options()
    if type(portion) is not int or portion < 1:
        raise ValueError("invalid_context_portion")
    minimal = validated_minimal_context_enabled()
    if minimal:
        from .minimal_context_selection import select_minimal_context
        return select_minimal_context(
            payload, snapshot, retrieval, portion=portion,
            continuation_token=continuation_token, request_binding=request_binding,
            finalize_packet=finalize_packet,
        )
    cap = experimental_context_max_tokens()
    validate_paired_context_budget(cap)
    if cap is None:
        if portion != 1 or continuation_token is not None:
            raise ValueError("portion_unavailable")
        return finalize_packet(payload, snapshot) if finalize_packet is not None else (payload, snapshot)
    if portion > 1 and continuation_token is None:
        raise ValueError("context_continuation_required")
    rows = payload.get("sources") or []
    focus = retrieval.get("_focused_source_path")
    if focus:
        # Narrow only after live source admission; the locator lookup acquired
        # the document through the ordinary scoped and generation-bound path.
        rows = [row for row in rows if row.get("path_or_url") == focus]
        payload, snapshot = _selected_packet(payload, snapshot, retrieval, rows, selection={
            "policy": POLICY, "scope": "source_checked_merged_candidates",
            "query_count": len(authoritative_queries(retrieval.get("documentation_query_plan") or {})),
            "candidate_rows": len(rows), "eligible_rows": len(rows), "pruned_rows": 0,
            "budget_limited": False, "reference_limited": False,
        })
    if not rows and portion == 1 and continuation_token is None:
        if os.environ.get("DOCATLAS_EXPERIMENT_PAIRED_TRACE"):
            trace = PoolTrace(retrieval, cap, _delivery_limit(retrieval, cap), max_source_references, portion)
            if study.mode is not None:
                trace.emit("qwen_study_settings", selection=study.trace_receipt(), pool=pool_study.receipt())
            for stage in ("raw_checked", "post_prune", "eligible"):
                trace.manifest(stage, [], snapshot, empty_pool=True)
            trace.emit("selection_output", final_rows=[], final_indices=[],
                       stage="empty_checked_pool_refusal_preserved")
        # Keep an existing source/consent/operational refusal intact. It never
        # advertises a next portion or acquires evidence through this helper.
        return finalize_packet(payload, snapshot) if finalize_packet is not None else (payload, snapshot)
    token = continuation_fingerprint(
        payload, snapshot, retrieval, policy=POLICY, settings=_continuation_settings(),
        limit=_delivery_limit(retrieval, cap), max_source_references=max_source_references,
        request_binding=request_binding,
    )
    if continuation_token is not None and continuation_token != token:
        raise ValueError("stale_context_continuation")

    def finish(result: dict, bound: dict) -> tuple[dict, dict]:
        if finalize_packet is not None:
            result, bound = finalize_packet(result, bound)
        return result, bound

    remaining = rows
    current = 1
    while remaining:
        page_input = {
            **payload, "sources": remaining,
            "more_context": continuation_metadata(current, token, len(remaining), 0),
        }
        result, bound = _select_portion(
            page_input, snapshot, retrieval, max_source_references=max_source_references,
        )
        result, bound = finish(result, bound)
        delivered = result.get("sources") or []
        identities = {row["evidence_id"] for row in delivered}
        available = {row["evidence_id"] for row in remaining}
        if len(identities) != len(delivered) or not identities <= available:
            raise ValueError("invalid_context_continuation")
        expected = continuation_metadata(current, token, len(remaining), len(delivered))
        if result.get("more_context") != expected:
            # A host finalizer may retract rows. Update the envelope before
            # repricing; finalization can only remove more, so it cannot cycle.
            result["more_context"] = expected
            _refresh_estimate(result)
            result, bound = finalize_joint_context_delivery(result, bound, retrieval)
            identities = {row["evidence_id"] for row in result.get("sources") or ()}
        if current == portion:
            return result, bound
        if not identities:
            # Nothing was delivered, so repeating this pool cannot advance.
            # Preserve the real budget/relevance failure and remaining count.
            result["more_context"] = continuation_metadata(portion, token, len(remaining), 0)
            _refresh_estimate(result)
            return result, bound
        remaining = [row for row in remaining if row["evidence_id"] not in identities]
        current += 1

    # Even a huge requested portion reaches here after at most len(rows)
    # nonempty pages. Exhaustion is an empty response, never the first page.
    result, bound = _selected_packet(
        {**payload, "more_context": continuation_metadata(portion, token, 0, 0)},
        snapshot, retrieval, [], selection={
            "policy": POLICY, "scope": "source_checked_merged_candidates",
            "query_count": len(authoritative_queries(retrieval.get("documentation_query_plan") or {})),
            "candidate_rows": 0, "eligible_rows": 0, "pruned_rows": 0,
            "budget_limited": False, "reference_limited": False,
        },
    )
    result["reason_code"] = "context_portion_exhausted"
    result["missing"] = ["No further checked source rows remain for this question and snapshot."]
    _refresh_estimate(result)
    return finish(result, bound)


def _select_portion(payload: dict, snapshot: dict, retrieval: dict, *,
                    max_source_references: int | None = None) -> tuple[dict, dict]:
    """Choose a relevant subset of the merged pool; never trim a source row.

    Called only by the native, compression-off route after source continuation
    locators are attached, before registering the selected reference batch.
    The explicit section-compression selector retains its own policy.
    """
    study, pool_study = _study_options()
    rows = payload.get("sources") or []
    cap = experimental_context_max_tokens()
    if not rows or cap is None:
        return payload, snapshot
    terms_mode = _experiment("DOCATLAS_EXPERIMENT_JOINT_TERMS")
    priority_mode = _experiment("DOCATLAS_EXPERIMENT_JOINT_PRIORITY")
    fusion_mode = _experiment("DOCATLAS_EXPERIMENT_JOINT_FUSION")
    cut_mode = _experiment("DOCATLAS_EXPERIMENT_JOINT_CUT")
    limit = _delivery_limit(retrieval, cap)
    queries = authoritative_queries(retrieval.get("documentation_query_plan") or {})
    # A missing authoritative plan is an upstream contract failure, not license
    # to reconstruct a question from retrieved text or generated probes.
    if not queries:
        raise ValueError("joint_context_selection_requires_authoritative_queries")
    paired = paired_qwen_enabled()
    validate_paired_native_settings((terms_mode, priority_mode, fusion_mode, cut_mode))
    paired_trace = PoolTrace(retrieval, cap, limit, max_source_references,
                             (payload.get("more_context") or {}).get("portion", 1))
    if study.mode is not None:
        paired_trace.emit("qwen_study_settings", selection=study.trace_receipt(), pool=pool_study.receipt())
    paired_trace.manifest("raw_checked", rows, snapshot,
                          native_settings={name: _experiment(name) for name in _EXPERIMENT_CHOICES},
                          prune_mode=pool_prune_mode(JOINT_POOL_PRUNE_DEFAULT),
                          relevance_mode=os.environ.get("DOCATLAS_EXPERIMENT_JOINT_RELEVANCE", "off"))
    statistic_rows = rows
    candidate_count = len(rows)
    # Whole-section pool pruning (``body`` unless the flag names another mode;
    # ``off`` keeps the whole pool). The selector then considers only the kept
    # sections, in pool order; term rarity below still counts every row.
    # Pruning only settles competition for the delivery budget: a checked pool
    # that fits whole is never pruned, in any mode (STEP7_CONTEXT7_PATH_RU.md).
    if _whole_pool_fits(payload, snapshot, retrieval, rows, limit, len(queries), max_source_references):
        prune_receipt = None
    else:
        if pool_study.pruning != "control":
            # A separately named study, not a silent relaxation of paired B.
            # No extra locator rescue: only intersection vs union/off changes.
            payload, prune_receipt = prune_study_pool(
                payload, snapshot, queries, settings=pool_study,
                default_mode=JOINT_POOL_PRUNE_DEFAULT,
            )
        else:
            payload, prune_receipt = prune_checked_pool(payload, snapshot, queries,
                                                        default_mode=JOINT_POOL_PRUNE_DEFAULT)
    rows = payload.get("sources") or []
    pruned_count = candidate_count - len(rows)
    paired_trace.manifest("post_prune", rows, snapshot, pruning_receipt=prune_receipt)
    observation = _SelectionObservation(retrieval, rows, lambda cost: _cost_scale(cost, priority_mode))
    if observation.state is not None and prune_receipt is not None:
        observation.state["pool_pruning"] = prune_receipt
    semantic_mode = os.environ.get("DOCATLAS_EXPERIMENT_JOINT_RELEVANCE", "off")
    if semantic_mode not in {"off", "mini", "hybrid", "dense", "dense_hybrid"}:
        raise ValueError("DOCATLAS_EXPERIMENT_JOINT_RELEVANCE must be off, mini, hybrid, dense or dense_hybrid")
    if semantic_mode != "off" and (terms_mode, fusion_mode) != ("word", "mean"):
        raise ValueError("DOCATLAS_EXPERIMENT_JOINT_TERMS/FUSION apply to lexical relevance only")
    semantic_scores = None
    if semantic_mode in {"mini", "hybrid"}:
        from .experimental_selection_modes import score_joint_relevance
        semantic_scores, semantic_receipt = score_joint_relevance(
            queries, rows, os.environ.get("DOCATLAS_EXPERIMENT_MINI_PATH", ""),
        )
    elif semantic_mode in {"dense", "dense_hybrid"}:
        from .experimental_dense_relevance import score_joint_dense
        semantic_scores, semantic_receipt = score_joint_dense(
            queries, rows, os.environ.get("DOCATLAS_EXPERIMENT_DENSE_PATH", ""),
        )
    if semantic_scores is not None:
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
        words = lexical_terms(text) if terms_mode == "word" else character_ngrams(text)
        return frozenset((*words, *(key for key, pattern in literal_patterns.items()
                                    if pattern.search(text))))

    terms_by_query = {key: frozenset((
        *(query_terms(value["text"]) if terms_mode == "word" else character_ngrams(value["text"])), *(
            "literal:" + match.group().casefold() for match in _CLI_LITERAL.finditer(value["text"])
        ))) for key, value in queries.items()}
    row_terms = [body_terms(row["snippet"]) for row in rows]
    # After pool pruning, word rarity stays a statistic of the whole checked
    # pool: pruning removes candidates, not evidence about how common a term is.
    statistic_terms = row_terms if statistic_rows is rows else [
        body_terms(row["snippet"]) for row in statistic_rows]
    frequency = Counter(term for terms in statistic_terms for term in terms)
    pool_size = len(statistic_rows)
    # Smoothed information content needs no language-specific stopword list.
    # These weights are ranking features only. Even the best relative body
    # match cannot claim coverage of an absent requested identifier or relation.
    information = {term: math.log1p((pool_size - count + 0.5) / (count + 0.5))
                   for term, count in frequency.items()}
    absent_information = math.log1p((pool_size + 0.5) / 0.5)
    feature_weight: dict[tuple[str, str], float] = {}
    for key, terms in terms_by_query.items():
        total = sum(information.get(term, absent_information) for term in sorted(terms))
        if total:
            feature_weight.update({(key, term): information.get(term, absent_information) / total
                                   for term in terms})
    row_features = [frozenset((key, term) for key, terms in terms_by_query.items()
                             for term in terms & body) for body in row_terms]
    row_locators = [_bound_locator_queries(row, snapshot, queries) for row in rows]
    # Content redundancy compares whole words in both modes. Shared character
    # n-grams of unrelated words would otherwise read as duplicated content.
    if terms_mode == "word":
        similarity_terms, similarity_information = row_terms, information
    else:
        similarity_terms = [frozenset(lexical_terms(row["snippet"])) for row in rows]
        similarity_statistics = similarity_terms if statistic_rows is rows else [
            frozenset(lexical_terms(row["snippet"])) for row in statistic_rows]
        similarity_information = {
            term: math.log1p((pool_size - count + 0.5) / (count + 0.5))
            for term, count in Counter(term for terms in similarity_statistics for term in terms).items()
        }
    grouped = _groups(rows, snapshot)

    def unit(group: int, indices: tuple[int, ...]) -> _Unit:
        return _Unit(
            group, indices,
            frozenset(feature for index in indices for feature in row_features[index]),
            frozenset(key for index in indices for key in row_locators[index]),
            frozenset(term for index in indices for term in similarity_terms[index]),
            max(1, sum(len(json.dumps(rows[index], ensure_ascii=False).encode("utf-8"))
                       for index in indices)),
            math.sqrt(sum(similarity_information[term] ** 2 for term in sorted(
                {term for index in indices for term in similarity_terms[index]}))),
        )

    whole = [unit(group, indices) for group, indices in enumerate(grouped)]
    if pool_study.units != "control":
        candidates, unit_receipt = initial_study_units(whole, rows, unit, settings=pool_study)
        paired_trace.emit("qwen_study_units", **unit_receipt)
        eligible_groups = {item.group for item in whole if item.features or item.locator_queries}
        # Preserve native group eligibility, including complementary zero-overlap
        # rows that can become useful after an adjacent sibling is selected.
        pending = {item.indices: item for item in candidates if item.group in eligible_groups}
    else:
        pending = {item.indices: item for item in whole if item.features or item.locator_queries}
    eligible = {index for item in pending.values() for index in item.indices}
    paired_trace.manifest("eligible", [row for index, row in enumerate(rows) if index in eligible],
                          snapshot, post_prune_indices=sorted(eligible),
                          groups=[{"group": item.group, "indices": list(item.indices),
                                   "eligible": item.indices in pending} for item in whole])
    # Score new checked-snippet inputs once with the unchanged original question.
    # Eligibility, grouping, pruning and all query lanes remain the default ones.
    paired_scores = paired_score_rows(retrieval, rows, snapshot, paired_trace) if paired else None
    if paired_scores is not None and study.mode is not None:
        # Raw scorer/cache/receipt values remain intact; transform selection only.
        paired_scores = study.transform_scores(paired_scores)
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
    # Each query's mass is already a share of that query's own information,
    # so one pool-wide scale keeps the queries comparable (research flag).
    shared_scale = max(best_query_mass.values(), default=0.0)

    if cut_mode != "off" and semantic_scores is None and fusion_mode == "mean":
        # Research flag: keep only the upper Otsu class of whole sections by
        # the same relative relevance the greedy loop uses (no redundancy yet).
        # Otsu's split needs no parameter; equal scores keep every section.
        def lane(item: _Unit, key: str) -> float:
            mass = sum(feature_weight[feature] for feature in item.features if feature[0] == key)
            return max(mass / best_query_mass[key] if best_query_mass[key] else 0.0,
                       1.0 if key in item.locator_queries else 0.0)

        def upper(scores: dict[int, float]) -> set[int]:
            ranked = sorted(((value, group) for group, value in scores.items() if value > 0), reverse=True)
            return {group for _, group in ranked[:otsu_upper([value for value, _ in ranked])]}

        candidates = [item for item in pending.values()]
        if cut_mode == "otsu_mean":
            kept_groups = upper({item.group: sum(lane(item, key) for key in queries) / len(queries)
                                 for item in candidates})
        else:
            kept_groups = set().union(*(upper({item.group: lane(item, key) for item in candidates})
                                        for key in queries))
        if kept_groups:
            pending = {indices: item for indices, item in pending.items() if item.group in kept_groups}
            if observation.state is not None:
                observation.state["relevance_cut"] = {"mode": cut_mode, "sections_before": len(candidates),
                                                      "sections_kept": len(kept_groups)}

    def packet(indices: list[int], *, budget_limited: bool) -> tuple[dict, dict]:
        return _selected_packet(payload, snapshot, retrieval, [rows[index] for index in indices], selection={
            "policy": POLICY, "scope": "source_checked_merged_candidates",
            "query_count": len(queries), "candidate_rows": candidate_count,
            "pruned_rows": pruned_count,
            "eligible_rows": len(eligible), "budget_limited": budget_limited,
            "reference_limited": bool(reference_rejected - set(indices)),
        })

    def adjacent(item: _Unit) -> bool:
        return any(
            rows[index]["line_start"] <= rows[other]["line_end"] + 1
            and rows[other]["line_start"] <= rows[index]["line_end"] + 1
            for index in item.indices for other in grouped[item.group] if other in selected_set
        )

    # A unit's terms and norm are functions of its row indices, so a pair's
    # similarity never changes during this call; every greedy step reuses it.
    similarities: dict[tuple[tuple[int, ...], tuple[int, ...]], float] = {}

    def similarity(left: _Unit, right: _Unit) -> float:
        key = (left.indices, right.indices)
        value = similarities.get(key)
        if value is None:
            if not left.vector_norm or not right.vector_norm:
                value = 0.0
            else:
                value = min(1.0, sum(similarity_information[term] ** 2
                                     for term in sorted(left.terms & right.terms))
                            / (left.vector_norm * right.vector_norm))
            similarities[key] = value
        return value

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
            if paired_scores is not None:
                # No old section score is transferred to a split window: reduce
                # exactly this unit's row scores, including for completing units.
                original_score = max(paired_scores[index] for index in item.indices)
                relevance = sum(max(original_score, 1.0 if key in item.locator_queries else 0.0)
                                for key in queries) / len(queries)
            elif semantic_scores is None and fusion_mode == "max_shared_scale":
                relevance = max(max(
                    mass[key] / shared_scale if shared_scale else 0.0,
                    1.0 if key in item.locator_queries else 0.0,
                ) for key in queries)
            elif semantic_scores is None:
                relevance = sum(max(
                    mass[key] / best_query_mass[key] if best_query_mass[key] else 0.0,
                    1.0 if key in item.locator_queries else 0.0,
                ) for key in queries) / len(queries)
            elif semantic_mode in {"mini", "dense"}:
                indices = whole[item.group].indices if completing else item.indices
                relevance = sum(max(
                    max(semantic_scores[key][index] for index in indices),
                    1.0 if key in item.locator_queries else 0.0,
                ) for key in queries) / len(queries)
            else:
                indices = whole[item.group].indices if completing else item.indices
                relevance = sum(max(
                    0.5 * (mass[key] / best_query_mass[key] if best_query_mass[key] else 0.0)
                    + 0.5 * max(semantic_scores[key][index] for index in indices),
                    1.0 if key in item.locator_queries else 0.0,
                ) for key in queries) / len(queries)
            # This MMR-style choice subtracts content redundancy without a hard
            # one-hit set-cover stop. Its signals are not calibrated probabilities.
            # Siblings of a partly selected coherent section are complementary
            # continuation, so they are compared against other sections only.
            redundancy = max((similarity(item, previous) for previous in selected_units
                              if previous.group != item.group), default=0.0)
            gain = study.marginal_gain(relevance, redundancy)
            return (gain / _cost_scale(item.cost, priority_mode), relevance, -min(item.indices))

        candidate = max(pending.values(), key=priority)
        if study.should_stop(priority(candidate)[0]):
            if paired_trace.path:
                for remaining in pending.values():
                    paired_trace.decision(remaining, "nonpositive_gain", priority(remaining),
                                          selected_before=len(selected))
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
            if paired_trace.path:
                paired_trace.decision(candidate, "delivery_budget" if references_fit else "reference_limit",
                                      priority(candidate), selected_before=len(selected),
                                      split_into_single_rows=(len(candidate.indices) > 1 and pool_study.units == "control"))
            if observation.state is not None:
                observation.decision(candidate, "delivery_budget" if references_fit else "reference_limit", priority,
                                     selected_before=len(selected), trial_text_bytes=text_bytes,
                                     fit_check=("reference_limit" if not references_fit else
                                                "text_lower_bound" if text_bytes > 4 * limit else "rendered_packet"))
            if references_fit:
                rejected.update(candidate.indices)
            else:
                reference_rejected.update(candidate.indices)
            if len(candidate.indices) > 1 and pool_study.units == "control":
                # A section is not silently clipped. Its original checked rows
                # compete again under the same joint objective and wire budget.
                for index in candidate.indices:
                    pending[(index,)] = unit(candidate.group, (index,))
            continue
        if paired_trace.path:
            paired_trace.decision(candidate, "selected", priority(candidate), selected_before=len(selected))
        selected.extend(candidate.indices)
        if observation.state is not None:
            observation.decision(candidate, "selected", priority, selected_before=len(selected) - len(candidate.indices))
        selected_set.update(candidate.indices)
        if pool_study.units != "control":
            pending = discard_overlapping_units(pending, selected_set)
        selected_groups.add(candidate.group)
        selected_units.append(candidate)
        selected_references.update(references)
        result, bound = trial, receipts

    # Reprice the truthful final omissions envelope too. No URI, attribution,
    # diagnostics, or selection field is appended after this final wire check.
    result, bound = packet(selected, budget_limited=bool(rejected - selected_set))
    result, bound = finalize_joint_context_delivery(result, bound, retrieval)
    observation.selected(result.get("sources") or [])
    if paired_trace.path:
        final_ids = {row["evidence_id"] for row in result.get("sources") or []}
        paired_trace.emit("selection_output", greedy_indices=selected,
                          final_indices=[index for index in selected if rows[index]["evidence_id"] in final_ids],
                          final_rows=result.get("sources") or [],
                          final_normalized_rows=[
                              {key: value for key, value in row.items() if key not in {"evidence_id", "source_uri"}}
                              for row in result.get("sources") or []],
                          stage="native_portion_after_fitter_before_host_finalization")
    return result, bound
