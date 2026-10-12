"""Host-only source recheck and bounded final MCP context, without retrieval.

The ordinary default has no new cap.  Experimental limits apply to the complete
JSON text returned by Docs MCP, using its existing offline codec and UTF-8 proxy.
Source rows are indivisible; only already-admitted native windows are fallback
representations.  No source text, question, or stored metadata enables this path.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from typing import Any

from docmancer.docs.domain.original_body_discovery import (
    experimental_context_max_tokens,
    source_valid_candidate_admission_active,
)
from ._docs_context_payload import _payload
from .context_selection import context_selection_decision
from .model_visible_projection import _refresh_estimate, validate_model_visible_projection
from .projection_tokenizer import projection_token_count


_SEED_KEY = "_experimental_native_context"


def experimental_context_cost(payload: dict[str, Any]) -> int:
    """Account for the actual non-ASCII-escaped MCP text, including whitespace.

    This is the named offline o200k_base codec, not a claim about a host model's
    full chat prompt, billing, or repeated history.  The independently measurable
    UTF-8/4 ceiling is enforced as well.
    """
    wire = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return max(math.ceil(len(wire) / 4), projection_token_count(wire))


def _source_key(candidate: dict) -> tuple:
    ref = candidate.get("_reference_evidence") or {}
    source = ref.get("source") or {}
    scope = source.get("scope") or {}
    return (source.get("document_id"), source.get("canonical_path"),
            source.get("content_sha256"), scope.get("project_id"), scope.get("snapshot_id"))


def capture_experimental_context(retrieval: dict, payload: dict, snapshot: dict) -> None:
    """Retain live canonical operands before finalizers change their spans.

    These copies are not grants: the terminal source check verifies the current
    discovery ledger and canonical policies again.  Native row alternatives are
    only rows already admitted by the ordinary core projection.
    """
    if (experimental_context_max_tokens() is None
            and not source_valid_candidate_admission_active()):
        return
    originals = []
    seen = set()
    candidates = [
        (snapshot.get(row.get("evidence_id")) or {}).get("source")
        for row in payload.get("sources") or () if isinstance(row, dict)
    ]
    candidates.extend(retrieval.get("context_pack") or ())
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        ref = candidate.get("_reference_evidence")
        if not isinstance(ref, dict):
            continue
        key = (*_source_key(candidate), ref.get("char_start"), ref.get("char_end"))
        if key in seen:
            continue
        seen.add(key)
        originals.append(deepcopy(candidate))
    alternatives = [
        (deepcopy(row), deepcopy(snapshot[row["evidence_id"]]))
        for row in payload.get("sources") or ()
        if isinstance(row, dict) and row.get("evidence_id") in snapshot
    ]
    retrieval[_SEED_KEY] = {"originals": originals, "alternatives": alternatives}


def _rebuild(payload: dict, snapshot: dict, retrieval: dict, rows: list[dict], *,
             reason: str) -> tuple[dict, dict]:
    """Recompute attribution after choosing whole source rows; never copy proof."""
    if not rows and not payload.get("sources"):
        # An existing operational refusal is not a failed source selection.
        # Preserve its typed delivery/confirmation veto and original cause;
        # a smaller envelope must not turn them into a generic budget failure.
        result = deepcopy(payload)
        result["read_next"] = []
        result.pop("recommended_next_action", None)
        if result.get("reason_code") and result.get("missing") == [result["reason_code"]]:
            result.pop("missing")  # The same reason remains in its typed field.
        _refresh_estimate(result)
        return result, {}

    from .docs_context_projection import _requalify_visible_source

    bound = {row["evidence_id"]: deepcopy(snapshot[row["evidence_id"]]) for row in rows}
    plan = retrieval.get("documentation_query_plan") or {}
    texts = {str(query.get("query_id") or ""): str(query.get("text") or "")
             for query in plan.get("queries") or () if isinstance(query, dict)}
    credit_ceiling = set(payload.get("covered_query_ids") or ())
    attributed = []
    for row in rows:
        original = bound[row["evidence_id"]]["source"]
        visible = _requalify_visible_source({
            **original, **row, "_qualification_candidate": original,
            "_expected_project_identity": row.get("project_identity"),
            "_independent_query_plan": plan,
        }, query_text=texts)
        # Snapshot source traces can predate the actual projected crop. A
        # smaller packet must not resurrect their hidden credit. Retain only
        # existing public attribution freshly checked against this visible row.
        matches = {key: value for key, value in visible["retrieval_query_matches"].items()
                   if key in credit_ceiling and value.get("qualified") is True
                   and value.get("admission_only") is not True}
        attributed.append({
            **row,
            "retrieval_query_ids": list(matches),
            "retrieval_query_matches": matches,
            # No assignment proof is transferable from an omitted/replaced
            # representation without its full source-local witness recheck.
            "_assigned_requirement_ids": [],
        })
    requested = tuple(dict.fromkeys((
        *(payload.get("covered_query_ids") or ()),
        *(payload.get("missing_query_ids") or ()),
    )))
    decision = context_selection_decision(attributed, requested)
    result = _payload(attributed, decision=decision, query_plan=plan)
    # Discard unissued recovery metadata when its source representation changed.
    # It must not retain references or apparent coverage of omitted evidence.
    result["read_next"] = []
    if rows:
        result["status"] = "truncated"
        result["context_quality"] = {
            "status": "unverified", "reasons": ["coverage_unverified", reason],
        }
    else:
        result["missing"] = [
            "Source context did not fit the experimental budget."
            if reason == "budget_limited" else
            "No source context survived the final source and request checks."
        ]
        result["context_quality"] = {"status": "unavailable", "reasons": [reason]}
    _refresh_estimate(result)
    return result, bound


def recheck_experimental_context(payload: dict, snapshot: dict, retrieval: dict) -> tuple[dict, dict]:
    """Validate native/derived source lineage after the last structural rewrite."""
    if not source_valid_candidate_admission_active():
        return payload, snapshot
    from docmancer.docs.domain.literal_context_admission import recheck_source_valid_candidate
    from .joint_context_lineage import _occurrence

    state = retrieval.get(_SEED_KEY) or {}
    originals = state.get("originals") or ()
    plan = retrieval.get("documentation_query_plan") or {}
    question = str(plan.get("original_question") or retrieval.get("question") or "")
    expected = retrieval.get("project_identity")
    kept = []
    rejected = []
    routes: dict[str, int] = {}
    for row in payload.get("sources") or ():
        original = (snapshot.get(row.get("evidence_id")) or {}).get("source")
        if not isinstance(original, dict):
            rejected.append({"evidence_id": row.get("evidence_id"), "reason": "missing_snapshot"})
            continue
        params = {
            "question": question, "evidence_text": row["snippet"], "candidate": original,
            "expected_project_identity": expected,
            "lifecycle_intent": original.get("_lifecycle_intent", "current"),
        }
        receipt = recheck_source_valid_candidate(**params)
        if receipt is None:
            # A native crop needs no structural expansion or document-size
            # allowance. In particular, do not inherit the joint expander's
            # 256 Ki-character limit for this already-admitted core operation.
            receipt = recheck_source_valid_candidate(**params, derivation="contained_span")
        if receipt is None:
            # Core crops can keep the native reference envelope in their
            # snapshot. Classify the verified visible occurrence, not that
            # wider reference; A still independently validates the relation.
            occurrence = _occurrence(row, snapshot)
            a, z = occurrence[1:] if occurrence is not None else (None, None)
            for seed in originals:
                if _source_key(seed) != _source_key(original):
                    continue
                seed_ref = seed.get("_reference_evidence") or {}
                x, y = seed_ref.get("char_start"), seed_ref.get("char_end")
                if not all(type(v) is int for v in (a, z, x, y)):
                    continue
                raw = seed_ref.get("raw_document") or ""
                if not 0 <= x < y <= len(raw):
                    continue
                seed_start, seed_end = x, y
                while x < y and raw[x].isspace():
                    x += 1
                while y > x and raw[y - 1].isspace():
                    y -= 1
                derivation = (
                    "containing_span" if a <= x < y <= z else
                    "contained_span" if seed_start <= a < z <= seed_end else "supplementary_block"
                )
                receipt = recheck_source_valid_candidate(
                    **params, native_candidate=seed, derivation=derivation)
                if receipt is not None:
                    break
        if receipt is not None:
            kept.append(row)
            route = str(receipt.get("route") or receipt.get("reason") or "rechecked")
            routes[route] = routes.get(route, 0) + 1
        else:
            rejected.append({"evidence_id": row.get("evidence_id"),
                             "reason": "source_or_request_lineage_rejected"})
    diagnostics = retrieval.setdefault("retrieval_diagnostics", {}).setdefault(
        "docs_context_projection", {})
    diagnostics["experimental_source_recheck"] = {
        "checked": len(kept) + len(rejected), "retained": len(kept),
        "rejected": rejected[:64], "routes": routes,
    }
    if not rejected:
        return payload, snapshot
    result, bindings = _rebuild(payload, snapshot, retrieval, kept, reason="structure_unverified")
    errors = validate_model_visible_projection(result, snapshot=bindings)
    if errors:
        raise ValueError("experimental source recheck produced an invalid projection: " + "; ".join(errors))
    return result, bindings


def _native_alternatives(row: dict, snapshot: dict, retrieval: dict):
    """Reuse smaller already-admitted windows; do not generate new text/spans."""
    current = (snapshot.get(row["evidence_id"]) or {}).get("source")
    if not isinstance(current, dict):
        return
    for native, bound in (retrieval.get(_SEED_KEY) or {}).get("alternatives") or ():
        original = bound.get("source")
        if (isinstance(original, dict) and _source_key(original) == _source_key(current)
                and native.get("snippet") and native["snippet"] in row["snippet"]):
            yield deepcopy(native), deepcopy(bound)


def enforce_experimental_context_budget(payload: dict, snapshot: dict,
                                        retrieval: dict) -> tuple[dict, dict]:
    """Select complete source rows under the host cap at the terminal boundary.

    Preserve the finalizer order; try each final representation, then its
    already-admitted native windows.  There is no semantic scorer, new retrieval,
    recursive finalization, arbitrary text crop, or model call.
    """
    cap = experimental_context_max_tokens()
    if cap is None or payload.get("kind") != "docs_context":
        return payload, snapshot
    diagnostics = retrieval.setdefault("retrieval_diagnostics", {}).setdefault(
        "docs_context_projection", {})
    before = experimental_context_cost(payload)
    ledger = diagnostics.setdefault("experimental_budget", {})
    ledger.update(limit=cap, input_cost=before, measure="max(o200k_base,utf8_bytes_div4)_mcp_json",
                  attempts=0, omitted_evidence_ids=[], native_fallbacks=0)
    if before <= cap:
        ledger.update(output_cost=before, source_count=len(payload.get("sources") or ()))
        return payload, snapshot

    rows = list(payload.get("sources") or ())
    selected: list[dict] = []
    bound = {}
    omitted = []
    current, current_bound = _rebuild(payload, {}, retrieval, [], reason="budget_limited")
    for row in rows:
        if any(item["evidence_id"] == row["evidence_id"] for item in selected):
            continue
        options = [(deepcopy(row), deepcopy(snapshot[row["evidence_id"]]))]
        options.extend(_native_alternatives(row, snapshot, retrieval))
        accepted_current = False
        for index, (option, binding) in enumerate(options):
            if any(item["evidence_id"] == option["evidence_id"] for item in selected):
                continue
            trial_bound = {**bound, option["evidence_id"]: binding}
            trial, trial_bound = _rebuild(
                payload, trial_bound, retrieval, [*selected, option], reason="budget_limited")
            ledger["attempts"] += 1
            if experimental_context_cost(trial) > cap:
                continue
            if validate_model_visible_projection(trial, snapshot=trial_bound):
                continue
            # Native alternatives were admitted before finalizers, but broad
            # mode must still recheck their active request-bound provenance.
            checked, checked_bound = recheck_experimental_context(trial, trial_bound, retrieval)
            if len(checked.get("sources") or ()) != len(trial.get("sources") or ()):
                continue
            selected.append(option)
            bound = trial_bound
            current, current_bound = checked, checked_bound
            accepted_current = True
            if index == 0:
                break
            ledger["native_fallbacks"] += 1
        if not accepted_current:
            omitted.append(row["evidence_id"])

    cost = experimental_context_cost(current)
    if cost > cap:
        # An impossible budget is a host configuration failure, not permission
        # to publish an oversized successful source packet.
        raise ValueError("experimental context budget cannot fit the required empty envelope")
    errors = validate_model_visible_projection(current, snapshot=current_bound)
    if errors:
        raise ValueError("experimental budget produced an invalid projection: " + "; ".join(errors))
    ledger.update(output_cost=cost, omitted_evidence_ids=omitted[:64],
                  omitted_source_count=len(omitted), source_count=len(selected),
                  read_next_omitted=bool(payload.get("read_next")))
    return current, current_bound


def check_experimental_context_budget(payload: dict) -> None:
    """Assert the complete DTO again after optional resource registration."""
    cap = experimental_context_max_tokens()
    if cap is not None and payload.get("kind") == "docs_context" and experimental_context_cost(payload) > cap:
        raise ValueError("experimental final context exceeds the host budget")
