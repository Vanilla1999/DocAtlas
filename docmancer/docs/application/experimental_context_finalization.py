"""Host-only source recheck and bounded final MCP context, without retrieval.

The source-native default applies its explicit cap to the complete JSON text
returned by Docs MCP, using the offline codec and UTF-8 proxy.
Source rows are indivisible; only already-admitted native windows are fallback
representations.  No source text, question, or stored metadata enables this path.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
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
from .projection_decision_trace import ProjectionFlowTrace
from .projection_tokenizer import projection_token_count
from .context_json import serialize_context_json


_SEED_KEY = "_experimental_native_context"


def _mark_unassessed(payload: dict) -> None:
    """Admission/source validity is never semantic sufficiency or query credit."""
    veto = payload.get("delivery_decision")
    if not payload.get("sources") and isinstance(veto, dict) and veto.get("deliverable") is False:
        # An operational denial contains no candidate context to assess. Keep
        # its source/consent cause and confirmation fields ahead of optional
        # admission annotations, including under a small final DTO budget.
        payload.pop("context_unassessed", None)
        payload.pop("admission_contract", None)
        _refresh_estimate(payload)
        return
    payload.update(context_unassessed=True, admission_contract="source_only_heuristic_removal_v1")
    if payload.get("sources"):
        payload["context_quality"] = {"status": "unverified", "reasons": ["coverage_unverified"]}
    _refresh_estimate(payload)


def project_native_rank_context(*, retrieval: dict, max_tokens: int | None = None,
                                selection_diagnostics: dict | None = None,
                                _allow_context_hints: bool = False) -> tuple[dict, dict]:
    """Render checked whole acquired windows; no semantic ranking or variants.

    The coordinator dispatches here only on S/ALL before the legacy core. The
    ordinary recheck and terminal JSON budget still run after decoration.
    """
    from .experimental_candidate_selection import native_rank_selection_active
    from .model_visible_projection import (
        _docs_source, _snapshot_entry, _explicit_delivery_block,
        _request_input_limit_failures, _requires_exact_snapshot, project_insufficient,
    )
    from .context_query_probes import authoritative_queries
    from .docs_context_projection import _requalify_visible_source
    from docmancer.docs.domain.lifecycle_policy import lifecycle_intent
    from docmancer.docs.domain.literal_context_admission import recheck_source_valid_candidate

    if not native_rank_selection_active() or experimental_context_max_tokens() is None:
        return project_insufficient(
            kind="docs_context", missing=["live_source_read_required"],
            recommended_next_action=None, max_tokens=max_tokens,
        ), {}
    blocked = _explicit_delivery_block(retrieval, kind="docs_context", max_tokens=max_tokens)
    if blocked is not None:
        return blocked, {}
    plan = dict(retrieval.get("documentation_query_plan") or {})
    question = str(plan.get("original_question") or retrieval.get("question") or "")
    failures = _request_input_limit_failures(question, retrieval)
    if failures:
        payload = project_insufficient(kind="docs_context", missing=failures,
                                       recommended_next_action=None, max_tokens=max_tokens)
        payload["reason_code"] = "request_input_limit_exceeded"
        _refresh_estimate(payload)
        return payload, {}
    queries = authoritative_queries(plan)
    plan.update(queries=list(queries.values()), query_ids=list(queries),
                public_query_ids=list(queries), _component_contract=[],
                component_scope_complete=False, assigned_requirement_ids=[],
                broad_context_only=True)
    texts = {key: str(value.get("text") or "") for key, value in queries.items()}
    expected = retrieval.get("project_identity")
    requirements = retrieval.get("requirements") or {}
    intent = (requirements.get("lifecycle_intent") if isinstance(requirements, dict) else None) or lifecycle_intent(question)
    rows, snapshot, seen = [], {}, set()
    for candidate in retrieval.get("context_pack") or ():
        if not isinstance(candidate, dict) or candidate.get("source_class") != "project_doc":
            continue
        if _requires_exact_snapshot(retrieval) and candidate.get("docs_snapshot_exact") is not True:
            continue
        original = {**candidate, "_expected_project_identity": expected,
                    "_lifecycle_intent": intent, "_independent_query_plan": plan}
        body = original.get("content") or original.get("display_text") or ""
        if not isinstance(body, str) or not body:
            continue
        receipt = recheck_source_valid_candidate(
            question=question, evidence_text=body, candidate=original,
            expected_project_identity=expected, lifecycle_intent=intent,
        )
        if receipt is None:
            continue
        # This identity is issued by the current source check, not a predicted
        # owner or text-similarity key. Distinct occurrences retain distinct IDs.
        key = receipt["native_discovery_binding_sha256"]
        if key in seen:
            continue
        row = _docs_source(original, display_snippet=body,
                           evidence_id="ev-" + hashlib.sha256(key.encode()).hexdigest()[:16])
        if row is None:
            continue
        window = receipt["body_window"]
        row.update(snippet=body, project_identity=original.get("project_identity"),
                   line_start=window["line_start"], line_end=window["line_end"],
                   authority=str(original.get("authority") or "supporting"),
                   scope=str(original.get("doc_scope") or "project"),
                   catalog_role=str(original.get("catalog_role") or ""),
                   _assigned_requirement_ids=[])
        # Lexical attribution stays diagnostic, not an admission/ranking gate.
        visible = _requalify_visible_source({
            **original, **row, "_qualification_candidate": original,
        }, query_text=texts)
        row.update(retrieval_query_ids=visible["retrieval_query_ids"],
                   retrieval_query_matches=visible["retrieval_query_matches"])
        rows.append(row)
        snapshot[row["evidence_id"]] = _snapshot_entry(original, row)
        seen.add(key)
    decision = context_selection_decision(rows, tuple(queries))
    payload = _payload(rows, decision=decision, query_plan=plan)
    _mark_unassessed(payload)
    snapshot = {row["evidence_id"]: _snapshot_entry(snapshot[row["evidence_id"]]["source"], row)
                for row in payload.get("sources") or ()}
    if rows:
        payload["context_quality"] = {"status": "unverified", "reasons": ["coverage_unverified"]}
    _refresh_estimate(payload)
    errors = validate_model_visible_projection(payload, snapshot=snapshot)
    if errors:
        raise ValueError("native-rank projection is invalid: " + "; ".join(errors))
    return payload, snapshot


def experimental_context_cost(payload: dict[str, Any]) -> int:
    """Account for the actual non-ASCII-escaped MCP text, including whitespace.

    This is the named offline o200k_base codec, not a claim about a host model's
    full chat prompt, billing, or repeated history.  The independently measurable
    UTF-8/4 ceiling is enforced as well.
    """
    wire = serialize_context_json(payload).encode("utf-8")
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
    _mark_unassessed(payload)
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
        _mark_unassessed(result)
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
    _mark_unassessed(result)
    return result, bound


def _restore_checked_native_context(payload: dict, snapshot: dict, retrieval: dict,
                                    kept: list[dict], receipts: dict[str, dict], *,
                                    question: str, expected: str | None,
                                    flow: ProjectionFlowTrace) -> tuple[list[dict], dict, dict]:
    """Recover original core windows after rejecting optional rewrites.

    Every window must pass its own current source/request check. Only exact
    checked intervals in the same source identity can suppress a duplicate;
    matching words, scores and the rejected draft never confer permission.
    This runs before terminal budgeting, never inside a budget trial.
    """
    from docmancer.docs.domain.literal_context_admission import recheck_source_valid_candidate
    from ._model_visible_docs_support import _snapshot_entry

    bound = {row["evidence_id"]: snapshot[row["evidence_id"]] for row in kept}
    covered = [
        (bound[row["evidence_id"]]["source"]["_reference_evidence"]["source"],
         receipts[row["evidence_id"]]["body_window"])
        for row in kept
    ]
    recovered = []
    ledger = {"checked": 0, "restored": 0, "already_covered": 0, "rejected": 0}
    alternatives = (retrieval.get(_SEED_KEY) or {}).get("alternatives") or ()
    for ordinal, (native, native_bound) in enumerate(alternatives):
        candidate = native_bound.get("source")
        if not isinstance(candidate, dict):
            ledger["rejected"] += 1
            flow.row_outcome("native_restore.row", row=native, candidate=candidate,
                             row_ordinal=ordinal, outcome="rejected", reason="missing_snapshot")
            continue
        ledger["checked"] += 1
        receipt = None
        for attempt_ordinal, derivation in enumerate((None, "contained_span"), start=1):
            rejection = {} if flow.enabled else None
            try:
                receipt = recheck_source_valid_candidate(
                    question=question, evidence_text=native["snippet"], candidate=candidate,
                    expected_project_identity=expected,
                    lifecycle_intent=candidate.get("_lifecycle_intent", "current"),
                    derivation=derivation, rejection_diagnostics=rejection,
                )
            except Exception as exc:
                flow.recheck("native_restore.attempt", row=native, candidate=candidate,
                             native=candidate, receipt=None, rejection=rejection,
                             row_ordinal=ordinal, attempt_ordinal=attempt_ordinal,
                             derivation=derivation or "native", error_type=type(exc).__name__)
                raise
            flow.recheck("native_restore.attempt", row=native, candidate=candidate,
                         native=candidate, receipt=receipt, rejection=rejection,
                         row_ordinal=ordinal, attempt_ordinal=attempt_ordinal,
                         derivation=derivation or "native")
            if receipt is not None:
                break
        if receipt is None:
            ledger["rejected"] += 1
            flow.row_outcome("native_restore.row", row=native, candidate=candidate,
                             row_ordinal=ordinal, outcome="rejected", reason="native_recheck_rejected")
            continue
        identity = candidate["_reference_evidence"]["source"]
        window = receipt["body_window"]
        if any(identity == source and prior["char_start"] <= window["char_start"]
               < window["char_end"] <= prior["char_end"] for source, prior in covered):
            ledger["already_covered"] += 1
            flow.row_outcome("native_restore.row", row=native, candidate=candidate,
                             row_ordinal=ordinal, outcome="already_covered",
                             reason="checked_retained_interval")
            continue
        row = deepcopy(native)
        # An unissued locator from another representation must not survive.
        row.pop("source_uri", None)
        original_id = row["evidence_id"]
        suffix = 0
        while row["evidence_id"] in bound:
            material = json.dumps([original_id, identity, window["char_start"],
                                   window["char_end"], suffix], sort_keys=True)
            row["evidence_id"] = "ev-" + hashlib.sha256(material.encode()).hexdigest()[:16]
            suffix += 1
        bound[row["evidence_id"]] = _snapshot_entry(candidate, row)
        recovered.append(row)
        covered.append((identity, window))
        ledger["restored"] += 1
        flow.row_outcome("native_restore.row", row=row, candidate=candidate,
                         row_ordinal=ordinal, outcome="restored", reason="checked_native_context")
    # Preserve draft order for surviving rows and direct replacements. Missing
    # coalesced core members follow in their original core order, without fusion.
    available = {row["evidence_id"]: row for row in [*kept, *recovered]}
    ordered = []
    for row in payload.get("sources") or ():
        selected = available.pop(row["evidence_id"], None)
        if selected is not None:
            ordered.append(selected)
    ordered.extend(available.values())
    return ordered, bound, ledger


def recheck_experimental_context(payload: dict, snapshot: dict, retrieval: dict, *,
                                 restore_native: bool = True,
                                 _trace_stage: str = "recheck") -> tuple[dict, dict]:
    """Validate native/derived source lineage after the last structural rewrite."""
    from .experimental_candidate_selection import native_rank_selection_active
    _mark_unassessed(payload)
    flow = ProjectionFlowTrace(retrieval)
    call_sequence = flow.boundary(_trace_stage + ".input", payload, snapshot, active=True)
    from docmancer.docs.domain.literal_context_admission import recheck_source_valid_candidate
    from .joint_context_lineage import _occurrence
    native_rank = native_rank_selection_active()
    if native_rank:
        restore_native = False

    state = retrieval.get(_SEED_KEY) or {}
    originals = state.get("originals") or ()
    plan = retrieval.get("documentation_query_plan") or {}
    question = str(plan.get("original_question") or retrieval.get("question") or "")
    expected = retrieval.get("project_identity")
    kept = []
    retained_receipts = {}
    rejected = []
    routes: dict[str, int] = {}
    for row_ordinal, row in enumerate(payload.get("sources") or ()):
        original = (snapshot.get(row.get("evidence_id")) or {}).get("source")
        if not isinstance(original, dict):
            rejected.append({"evidence_id": row.get("evidence_id"), "reason": "missing_snapshot"})
            flow.row_outcome(_trace_stage + ".row", row=row, candidate=original,
                             call_sequence=call_sequence, row_ordinal=row_ordinal, attempts=0,
                             outcome="rejected", axis="source_admissible", reason="missing_snapshot")
            continue
        params = {
            "question": question, "evidence_text": row["snippet"], "candidate": original,
            "expected_project_identity": expected,
            "lifecycle_intent": original.get("_lifecycle_intent", "current"),
        }
        attempts = 0

        def attempt(*, native_candidate=None, derivation=None, seed_ordinal=None):
            # This wraps the same single check at each existing call site.
            # Trace-off creates no rejection carrier, source copy or span hash.
            nonlocal attempts
            rejection = {} if flow.enabled else None
            if flow.enabled:
                attempts += 1
            try:
                result = recheck_source_valid_candidate(
                    **params, native_candidate=native_candidate, derivation=derivation,
                    rejection_diagnostics=rejection,
                )
            except Exception as exc:
                flow.recheck(_trace_stage + ".attempt", row=row, candidate=original,
                             native=native_candidate if native_candidate is not None else original,
                             receipt=None, rejection=rejection, call_sequence=call_sequence,
                             row_ordinal=row_ordinal, attempt_ordinal=attempts,
                             derivation=derivation or "native", seed_ordinal=seed_ordinal,
                             error_type=type(exc).__name__)
                raise
            flow.recheck(_trace_stage + ".attempt", row=row, candidate=original,
                         native=native_candidate if native_candidate is not None else original,
                         receipt=result, rejection=rejection, call_sequence=call_sequence,
                         row_ordinal=row_ordinal, attempt_ordinal=attempts,
                         derivation=derivation or "native", seed_ordinal=seed_ordinal)
            return result

        receipt = attempt()
        if receipt is None:
            # A native crop needs no structural expansion or document-size
            # allowance. In particular, do not inherit the joint expander's
            # 256 Ki-character limit for this already-admitted core operation.
            receipt = attempt(derivation="contained_span")
        seed_source_mismatches = seed_span_unavailable = seed_bounds_invalid = 0
        occurrence_available = None
        if receipt is None and not native_rank:
            # Core crops can keep the native reference envelope in their
            # snapshot. Classify the verified visible occurrence, not that
            # wider reference; A still independently validates the relation.
            occurrence = _occurrence(row, snapshot)
            a, z = occurrence[1:] if occurrence is not None else (None, None)
            occurrence_available = occurrence is not None
            for seed_ordinal, seed in enumerate(originals):
                if _source_key(seed) != _source_key(original):
                    if flow.enabled:
                        seed_source_mismatches += 1
                    continue
                seed_ref = seed.get("_reference_evidence") or {}
                x, y = seed_ref.get("char_start"), seed_ref.get("char_end")
                if not all(type(v) is int for v in (a, z, x, y)):
                    if flow.enabled:
                        seed_span_unavailable += 1
                    continue
                raw = seed_ref.get("raw_document") or ""
                if not 0 <= x < y <= len(raw):
                    if flow.enabled:
                        seed_bounds_invalid += 1
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
                receipt = attempt(native_candidate=seed, derivation=derivation, seed_ordinal=seed_ordinal)
                if receipt is not None:
                    break
        if receipt is not None:
            kept.append(row)
            retained_receipts[row["evidence_id"]] = receipt
            route = str(receipt.get("route") or receipt.get("reason") or "rechecked")
            routes[route] = routes.get(route, 0) + 1
        else:
            rejected.append({"evidence_id": row.get("evidence_id"),
                             "reason": "source_or_request_lineage_rejected"})
        flow.row_outcome(_trace_stage + ".row", row=row, candidate=original,
                         call_sequence=call_sequence, row_ordinal=row_ordinal, attempts=attempts,
                         outcome="retained" if receipt is not None else "rejected",
                         reason=(receipt.get("route") if receipt is not None else "source_or_request_lineage_rejected"),
                         seed_count=len(originals), seed_source_mismatches=seed_source_mismatches,
                         seed_span_unavailable=seed_span_unavailable, seed_bounds_invalid=seed_bounds_invalid,
                         occurrence_available=occurrence_available)
    diagnostics = retrieval.setdefault("retrieval_diagnostics", {}).setdefault(
        "docs_context_projection", {})
    diagnostics["experimental_source_recheck"] = {
        "checked": len(kept) + len(rejected), "retained": len(kept),
        "rejected": rejected[:64], "routes": routes,
    }
    if not rejected:
        flow.boundary(_trace_stage + ".output", payload, snapshot, active=True, call_sequence=call_sequence)
        return payload, snapshot
    if restore_native:
        kept, snapshot, restored = _restore_checked_native_context(
            payload, snapshot, retrieval, kept, retained_receipts,
            question=question, expected=expected, flow=flow,
        )
        diagnostics["experimental_native_restore"] = restored
    result, bindings = _rebuild(payload, snapshot, retrieval, kept, reason="structure_unverified")
    errors = validate_model_visible_projection(result, snapshot=bindings)
    if errors:
        raise ValueError("experimental source recheck produced an invalid projection: " + "; ".join(errors))
    flow.boundary(_trace_stage + ".output", result, bindings, active=True, call_sequence=call_sequence)
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
    from .experimental_candidate_selection import native_rank_selection_active
    native_rank = native_rank_selection_active()
    _mark_unassessed(payload)
    flow = ProjectionFlowTrace(retrieval)
    active = cap is not None and payload.get("kind") == "docs_context"
    flow.boundary("budget.input", payload, snapshot, active=active)
    if cap is None or payload.get("kind") != "docs_context":
        flow.boundary("budget.output", payload, snapshot, active=False)
        return payload, snapshot
    diagnostics = retrieval.setdefault("retrieval_diagnostics", {}).setdefault(
        "docs_context_projection", {})
    if native_rank:
        from .joint_context_lineage import _occurrence
        unique, seen = [], set()
        for row in payload.get("sources") or ():
            occurrence = _occurrence(row, snapshot)
            source = (snapshot.get(row.get("evidence_id")) or {}).get("source") or {}
            member = (source.get("_reference_evidence") or {}).get("member_binding")
            key = (occurrence, json.dumps(member, sort_keys=True), row.get("snippet"))
            if occurrence is not None and key in seen:
                continue
            if occurrence is not None:
                seen.add(key)
            unique.append(row)
        removed = len(payload.get("sources") or ()) - len(unique)
        diagnostics["native_exact_dedupe"] = {"removed": removed}
        if removed:
            payload, snapshot = _rebuild(payload, snapshot, retrieval, unique, reason="exact_occurrence_dedupe")
    before = experimental_context_cost(payload)
    ledger = diagnostics.setdefault("experimental_budget", {})
    ledger.update(limit=cap, input_cost=before, measure="max(o200k_base,utf8_bytes_div4)_mcp_json",
                  attempts=0, omitted_evidence_ids=[], native_fallbacks=0)
    if before <= cap:
        ledger.update(output_cost=before, source_count=len(payload.get("sources") or ()))
        flow.boundary("budget.output", payload, snapshot, active=True)
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
        if not native_rank:
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
            checked, checked_bound = recheck_experimental_context(
                trial, trial_bound, retrieval, restore_native=False,
                _trace_stage="budget_trial_recheck")
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
    flow.boundary("budget.output", current, current_bound, active=True)
    return current, current_bound


def check_experimental_context_budget(payload: dict) -> None:
    """Assert the complete DTO again after optional resource registration."""
    cap = experimental_context_max_tokens()
    if cap is not None and payload.get("kind") == "docs_context" and experimental_context_cost(payload) > cap:
        raise ValueError("experimental final context exceeds the host budget")
