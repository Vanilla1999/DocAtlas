"""Explicit complete-scan candidate; calibrated membership precedes pricing.

Only host configuration selects this policy. No score grants authorization or
answer sufficiency. A missing policy is a labelled diagnostic full scan, never
an implicit relevance threshold.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from docmancer.docs.domain.minimal_context_config import EMERGENCY_TOKENS
from docmancer.docs.domain.context_links import OFF, context_link_expansion
from .complete_context_scoring import WINDOW_RECIPE, GATED_WINDOW_RECIPE, FIT_WINDOW_RECIPE, score_complete_units
from .experimental_selection_modes import MINI_REVISION, JointSemanticRelevanceError
from .context_continuation import continuation_fingerprint, continuation_metadata
from .context_json import serialize_context_json
from .experimental_context_finalization import _rebuild
from .model_visible_projection import _refresh_estimate, _snapshot_entry, validate_model_visible_projection
from .projection_tokenizer import projection_token_count
from .standalone_text_view import render_standalone_text
from . import context_evidence_scoring as evidence_scoring
from . import reference_closure_contract as reference_closure


POLICY = "complete_calibrated_context_v1"
STRUCTURAL_RECIPE = "minimal-structure-v1"
EVIDENCE_STRUCTURAL_RECIPE = evidence_scoring.STRUCTURAL_RECIPE
_OBSERVER = ContextVar("minimal_context_observer", default=None)


def scoring_recipe() -> str:
    recipe = os.environ.get("DOCATLAS_MINIMAL_CONTEXT_RECIPE", WINDOW_RECIPE)
    if recipe not in {WINDOW_RECIPE, GATED_WINDOW_RECIPE, FIT_WINDOW_RECIPE, evidence_scoring.RECIPE, reference_closure.RECIPE}:
        raise ValueError("minimal_context_unknown_scoring_recipe")
    return recipe


@contextmanager
def observe_minimal_context():
    """Capture same-call scores outside the model-visible/protocol response.

    This observer never supplies inputs to selection, changes membership or
    performs additional model/retrieval calls. Labels remain evaluator-owned.
    """
    observations = []
    token = _OBSERVER.set(observations)
    try:
        yield observations
    finally:
        _OBSERVER.reset(token)


def load_policy() -> tuple[dict | None, str]:
    path = os.environ.get("DOCATLAS_MINIMAL_CONTEXT_POLICY")
    if not path:
        return None, "diagnostic-unverified"
    location = Path(path)
    if not location.is_absolute():
        raise ValueError("minimal_context_policy_requires_absolute_path")
    data = location.read_bytes()
    policy = json.loads(data)
    expected = {"schema_version": 1, "recipe": scoring_recipe(),
                "model_revision": MINI_REVISION, "structural_recipe": STRUCTURAL_RECIPE,
                 "lanes": "original_translation_max"}
    if scoring_recipe() == reference_closure.RECIPE:
        expected = {"schema_version": 4, "recipe": reference_closure.RECIPE,
                    "model_id": evidence_scoring.MODEL_ID, "model_revision": evidence_scoring.REVISION,
                    "structural_recipe": reference_closure.STRUCTURAL_RECIPE, "lanes": "exact_original_only",
                    "scoring_contract_sha256": evidence_scoring.CONTRACT_SHA256,
                    "contract_sha256": reference_closure.CONTRACT_SHA256,
                    "calibration_recipe": reference_closure.CALIBRATION_RECIPE}
    elif scoring_recipe() == evidence_scoring.RECIPE:
        expected = {"schema_version": 3, "recipe": evidence_scoring.RECIPE,
                    "model_id": evidence_scoring.MODEL_ID, "model_revision": evidence_scoring.REVISION,
                    "structural_recipe": EVIDENCE_STRUCTURAL_RECIPE,
                    "lanes": "exact_original_only", "contract_sha256": evidence_scoring.CONTRACT_SHA256,
                    "calibration_recipe": evidence_scoring.CALIBRATION_RECIPE}
    elif policy.get("schema_version") == 2:
        expected.update(schema_version=2,
                        calibration_recipe="final-closure-all-useful-breakpoints-v3",
                        recipe=GATED_WINDOW_RECIPE)
        if scoring_recipe() != GATED_WINDOW_RECIPE:
            raise ValueError("minimal_context_policy_recipe_mismatch")
    if any(policy.get(key) != value for key, value in expected.items()):
        raise ValueError("minimal_context_policy_recipe_mismatch")
    threshold = policy.get("threshold")
    if type(threshold) not in (int, float) or not math.isfinite(threshold):
        raise ValueError("minimal_context_policy_invalid_threshold")
    if not isinstance(policy.get("calibration_sha256"), str) or len(policy["calibration_sha256"]) != 64:
        raise ValueError("minimal_context_policy_missing_calibration_digest")
    return policy, hashlib.sha256(data).hexdigest()


def stop_packet(payload: dict, snapshot: dict, retrieval: dict, reason: str, **details) -> tuple[dict, dict]:
    result, bound = _rebuild(payload, snapshot, retrieval, [], reason=reason)
    result.update(status="insufficient_evidence", reason_code=reason,
                  context_quality={"status": "unavailable", "reasons": [reason]},
                  source_selection={"policy": POLICY, **details})
    if reason in {"scan_incomplete", "context_emergency_stop"}:
        # A failed scan/delivery is not a successful search with no evidence.
        # Keep its receipt and reason, but make the failure visible to ordinary
        # MCP clients as isError too; an unchanged retry must not hide it.
        result.update(status="error", hard_stop=True)
    result.pop("more_context", None)
    result["missing"] = [reason]
    _refresh_estimate(result)
    return result, bound


def delivery_size(packet: dict) -> int:
    """Price the whole supported rendering, not a byte/4 approximation."""
    rendered = render_standalone_text(packet)
    text = rendered.text if rendered.text is not None else serialize_context_json(packet)
    return projection_token_count(text.encode("utf-8"))


def _wire_tokens(packet: dict) -> int:
    """Q6 budget cost of the exact minimal-mode MCP text.

    Mirrors _mcp_tool_result: standalone rendering when it exists, otherwise
    canonical JSON. Both token and UTF-8 byte bounds apply.
    """
    from docmancer.docs.application.model_context_view import canonical as _canonical
    rendered = render_standalone_text(packet)
    text = rendered.text if rendered.text is not None else _canonical(packet)
    raw = text.encode("utf-8")
    return max(projection_token_count(raw), (len(raw) + 3) // 4)


def _research_delivery_budget() -> int | None:
    """Opt-in experiment-branch delivery budget for the minimal-context path.

    Unset by default: production minimal-context behaviour is unchanged. When
    set, it must be a positive integer no larger than the emergency ceiling.
    """
    raw = os.environ.get("DOCATLAS_EXPERIMENT_MINIMAL_DELIVERY_BUDGET_TOKENS")
    if raw is None or raw == "":
        return None
    try:
        budget = int(raw)
    except ValueError as exc:
        raise ValueError("DOCATLAS_EXPERIMENT_MINIMAL_DELIVERY_BUDGET_TOKENS must be an integer") from exc
    if not 1 <= budget <= EMERGENCY_TOKENS:
        raise ValueError("DOCATLAS_EXPERIMENT_MINIMAL_DELIVERY_BUDGET_TOKENS must be in [1, 50000]")
    return budget


def _scored_units_with_cache(original, structure, model_path, diagnostics):
    """Reuse per-unit scores of the pinned scorer across calls.

    Experiment-branch-only (DOCATLAS_EXPERIMENT_EVIDENCE_SCORE_CACHE). The
    scorer is strictly per-unit: each unit is one independent (original,
    document) model forward with batch=1 and no cross-unit normalization, so
    a unit with an identical prompt yields the identical score regardless of
    which other units accompany it in the call. For every unit already
    recorded in the cache no forward is made; the remaining units go through
    the untouched pinned scorer in one call. Model asset verification runs on
    every call, exactly like the pinned path. The returned receipt is
    truthful: model_pairs/model_forwards count only forwards actually made
    this call, score_cache_hits counts units served from the cache, and the
    SHA-256 of every receipt that produced cached scores is listed.
    Selection semantics are unchanged.
    """
    from .context_evidence_structure import EvidenceDocuments

    cache_dir = os.environ.get("DOCATLAS_EXPERIMENT_EVIDENCE_SCORE_CACHE")
    unit_ids = tuple(unit.identity for unit in structure.units)
    documents = EvidenceDocuments(structure)
    if not cache_dir:
        return evidence_scoring.score_evidence_units(
            original, unit_ids, documents, model_path, diagnostics=diagnostics)
    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    evidence_scoring.verify_assets(model_path)

    def unit_key(identity):
        blob = json.dumps({
            "original": original,
            "model_id": evidence_scoring.MODEL_ID,
            "revision": evidence_scoring.REVISION,
            "contract_sha256": evidence_scoring.CONTRACT_SHA256,
            "document": documents.document(identity),
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    keys = {unit.identity: unit_key(unit.identity) for unit in structure.units}
    scores, missing, source_digests = [], [], set()
    for unit in structure.units:
        path = cache_root / f"{keys[unit.identity]}.json"
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            entry = None
        if isinstance(entry, dict) and entry.get("score_key") == keys[unit.identity] \
                and isinstance(entry.get("score"), float):
            scores.append({"identity": unit.identity, "score": entry["score"]})
            source_digests.add(entry.get("receipt_sha256", ""))
        else:
            missing.append(unit.identity)
    fresh_scores, fresh_receipt = [], None
    if missing:
        fresh_scores, fresh_receipt = evidence_scoring.score_evidence_units(
            original, tuple(missing), documents, model_path, diagnostics=diagnostics)
        for row in fresh_scores:
            identity = row["identity"]
            score = row["score"]
            receipt_sha = hashlib.sha256(evidence_scoring.canonical(fresh_receipt).encode()).hexdigest()
            # Unique temp per writer: overlapping identical misses must never share
            # one tmp path. os.replace is atomic, so a concurrent reader of the final
            # entry sees either the old complete file or the new complete file.
            tmp = cache_root / f"{keys[identity]}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
            try:
                tmp.write_text(json.dumps({
                    "score_key": keys[identity], "score": score,
                    "receipt_sha256": receipt_sha, "source_receipt": fresh_receipt,
                }, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, cache_root / f"{keys[identity]}.json")
            finally:
                tmp.unlink(missing_ok=True)
            source_digests.add(receipt_sha)
    scores.extend(fresh_scores)
    scores.sort(key=lambda row: unit_ids.index(row["identity"]))
    if fresh_receipt is not None:
        receipt = dict(fresh_receipt)
        receipt["units"] = len(unit_ids)
        receipt["score_cache_hits"] = len(unit_ids) - len(missing)
        receipt["diagnostics_omitted"] = receipt.get("diagnostics_omitted", 0) + (len(unit_ids) - len(missing)) if not diagnostics else receipt.get("diagnostics_omitted", 0)
    else:
        receipt = {"recipe": evidence_scoring.RECIPE, "contract_sha256": evidence_scoring.CONTRACT_SHA256,
                   "status": "complete", "units": len(unit_ids), "model_pairs": 0, "model_forwards": 0,
                   "model_input_tokens": 0, "planned_input_tokens": 0, "preflight_units": 0,
                   "model_loads": 0, "runtime_cache_hits": 0, "score_cache_hits": len(unit_ids),
                   "diagnostics_recorded": 0, "diagnostics_omitted": len(unit_ids),
                   "inference_seconds": 0.0}
    receipt["score_cache_dir"] = str(cache_root)
    receipt["score_cache_source_receipt_sha256s"] = sorted(d for d in source_digests if d)
    return scores, receipt


def model_closure_receipt(closure: dict) -> dict:
    """Keep actionable literal gaps, not the host's full successful-edge trace.

    Historical closures are returned unchanged. Unfollowed links are not a list
    of all question-relevant conditions, so even zero pending links cannot certify
    answer completeness. No source aliases or lookup dictionaries are introduced.
    """
    expansion = closure.get("reference_expansion")
    if not expansion:
        return closure
    return {
        "selected_units": closure["selected_units"],
        "delivered_spans": closure["delivered_spans"],
        "coverage": "unverified",
        "reference_expansion": {key: expansion[key] for key in (
            "recipe", "max_hops", "added_spans", "examined_references",
            "followed_references", "satisfied_references", "pending_references",
        )},
        "incomplete_dependencies": [
            {key: item[key] for key in (
                "path", "char_start", "char_end", "target", "origin", "navigation",
                "reason", "target_path", "target_char_start", "target_char_end",
                "missing_descendants",
            ) if key in item}
            for item in closure.get("incomplete_dependencies", ())
        ],
    }


def _fit_research_budget(payload, snapshot, retrieval, *, structure, selected,
                         scores, scoring, policy_digest, policy, token,
                         link_expansion, reference_mode, evidence_mode,
                         observations, work_observation, budget, finalize_packet):
    """Diagnostic-only unit pruning; price only complete finalized packets.

    Rebuild from the checked original pool on every iteration. A dependency row
    is never independently removed, and an empty budget result is not a semantic
    rejection. This is not a same-pool controlled selector comparison.
    """
    from .minimal_context_structure import close_selection, recheck_structural_row
    from .source_continuation import attach_source_continuation_locators

    current = set(selected)
    ranked = sorted((row for row in scores if row["identity"] in current),
                    key=lambda row: (row["score"], row["identity"]))
    dropped = []

    def finish(result, bound):
        if finalize_packet is not None:
            result, bound = finalize_packet(result, bound)
        return result, bound

    def gate(result, bound):
        # Never return an oversized packet, even when the failure envelope alone
        # exceeds the requested budget. The caller must surface this failure;
        # it is not a successful empty search.
        measured = _wire_tokens(result)
        if measured > budget:
            raise RuntimeError(
                f"minimal_context_delivery_budget_exceeded: {measured} > {budget}")
        if work_observation is not None:
            work_observation["delivery_status"] = "returned"
        return result, bound

    while True:
        try:
            rows, bound, closure = close_selection(
                structure, current, payload, snapshot, retrieval,
                **({"reference_expansion": link_expansion} if link_expansion != OFF else {}))
        except (ValueError, OSError) as exc:
            result, bound = stop_packet(
                payload, snapshot, retrieval, "scan_incomplete",
                failed_stage="structural_source_check", error=str(exc))
            result, bound = finish(result, bound)
            return gate(result, bound)
        closure = {**closure, "delivery_budget_tokens": budget,
                   "budget_limited": bool(dropped), "omitted_units": len(dropped)}
        diagnostics = retrieval.setdefault("retrieval_diagnostics", {})
        diagnostics["minimal_context_budget"] = {
            "delivery_budget_tokens": budget, "dropped_units": list(dropped)}
        diagnostics["minimal_context"] = {
            **({"scores": scores} if not evidence_mode or observations is not None else {}),
            "receipt": scoring, "policy_sha256": policy_digest, "closure": closure}
        if reference_mode and closure["incomplete_dependencies"]:
            result, bound = stop_packet(
                payload, snapshot, retrieval, "dependency_incomplete",
                failed_stage="reference_closure", receipt=scoring, closure=closure,
                scan_complete=True)
            result.update(status="error", hard_stop=True)
            _refresh_estimate(result)
            result, bound = finish(result, bound)
            return gate(result, bound)

        result, bound = _rebuild(payload, bound, retrieval, rows, reason=POLICY)
        bound = {row["evidence_id"]: {
            **_snapshot_entry(bound[row["evidence_id"]]["source"], row),
            **{key: bound[row["evidence_id"]][key]
               for key in ("structural_native_candidate", "structural_recipe")
               if key in bound[row["evidence_id"]]},
        } for row in result.get("sources", ())}
        result["source_selection"] = {
            "policy": POLICY, "calibration_sha256": policy_digest,
            "calibration_status": "diagnostic_unverified" if policy is None else "empirical",
            "candidate_units": len(scores), "selected_units": len(current),
            "delivered_rows": len(rows), "scan_complete": True,
            "model_pairs": scoring["model_pairs"], "closure": model_closure_receipt(closure),
            "delivery_budget_tokens": budget, "budget_limited": bool(dropped),
            "omitted_units": len(dropped),
        }
        if link_expansion != OFF:
            result["source_selection"]["calibration_scope"] = "selected_units_before_link_expansion"
        result["context_quality"] = {
            "status": "unverified" if rows else "unavailable",
            "reasons": ["coverage_unverified"]}
        if closure.get("incomplete_dependencies"):
            result["context_quality"]["reasons"].append("incomplete_structural_dependency")
        if rows:
            result["status"] = "ok"
        elif dropped:
            result.update(status="insufficient_evidence", reason_code="context_budget_exhausted",
                          missing=["No selected structural unit could be delivered within the budget."])
            result["context_quality"]["reasons"] = ["context_budget_exhausted"]
        elif not selected and policy is not None:
            result.update(status="insufficient_evidence", reason_code="no_relevant_source_context",
                          missing=["No structural unit met the frozen empirical relevance threshold."])
        else:
            result.update(status="insufficient_evidence", reason_code="no_deliverable_source_context",
                          missing=["Structural closure produced no deliverable source context."])
        result["more_context"] = continuation_metadata(1, token, len(rows), len(rows))
        root = str(retrieval.get("_source_continuation_project_root") or "")
        if root and rows:
            attach_source_continuation_locators(result, bound, root=root, max_tokens=EMERGENCY_TOKENS)
        _refresh_estimate(result)
        result, bound = finish(result, bound)

        # A finalizer refusal is not permission to retry with fewer sources.
        if result.get("hard_stop") or result.get("status") == "error":
            return gate(result, bound)
        # Finalization is part of the priced candidate, never a post-gate edit.
        if _wire_tokens(result) > budget and current:
            victim = next(row for row in ranked if row["identity"] in current)
            current.remove(victim["identity"])
            dropped.append({"identity": victim["identity"], "score": victim["score"]})
            continue
        try:
            for row in result.get("sources", ()):
                recheck_structural_row(row, bound[row["evidence_id"]], retrieval)
        except (ValueError, OSError) as exc:
            result, bound = stop_packet(
                result, bound, retrieval, "scan_incomplete",
                failed_stage="terminal_structural_recheck", error=str(exc))
            result, bound = finish(result, bound)
            return gate(result, bound)
        errors = validate_model_visible_projection(result, snapshot=bound)
        if errors:
            result, bound = stop_packet(
                result, bound, retrieval, "scan_incomplete",
                failed_stage="delivery_validation", errors=errors)
            result, bound = finish(result, bound)
        return gate(result, bound)


def select_minimal_context(payload: dict, snapshot: dict, retrieval: dict, *,
                           portion: int, continuation_token: str | None,
                           request_binding: dict | None, finalize_packet=None) -> tuple[dict, dict]:
    from .minimal_context_structure import build_units, close_selection, recheck_structural_row
    from .source_continuation import attach_source_continuation_locators

    policy, policy_digest = load_policy()
    link_expansion = context_link_expansion()
    reference_mode = scoring_recipe() == reference_closure.RECIPE
    evidence_mode = scoring_recipe() in {evidence_scoring.RECIPE, reference_closure.RECIPE}
    structural_recipe = (reference_closure.STRUCTURAL_RECIPE if reference_mode else
                         EVIDENCE_STRUCTURAL_RECIPE if evidence_mode else STRUCTURAL_RECIPE)
    request = request_binding or {}
    original = (retrieval.get("documentation_query_plan") or {}).get("original_question")
    if not isinstance(original, str) or not original.strip():
        raise ValueError("minimal_context_requires_original_question")
    lanes = [original]
    translation = request.get("search_question")
    if translation and translation != original and not evidence_mode:
        lanes.append(translation)
    settings = {"policy_sha256": policy_digest, "model_revision": MINI_REVISION,
                "recipe": scoring_recipe(), "structural_recipe": STRUCTURAL_RECIPE,
                 "lanes": "original_translation_max", "presentation": "standalone-adaptive-v1"}
    from docmancer.docs.domain.context_presentation import LITERAL_V2, literal_presentation_enabled
    if literal_presentation_enabled():
        settings["presentation"] = LITERAL_V2
    if link_expansion != OFF:
        # Off adds no key: historical continuation fingerprints remain intact.
        from .bounded_context_links import CONTRACT_SHA256
        settings["reference_expansion"] = link_expansion
        settings["reference_expansion_contract_sha256"] = CONTRACT_SHA256
    if evidence_mode:
        settings.update(model_revision=evidence_scoring.REVISION, structural_recipe=structural_recipe,
                        model_id=evidence_scoring.MODEL_ID, contract_sha256=evidence_scoring.CONTRACT_SHA256,
                        lanes="exact_original_only")
        if reference_mode:
            settings.update(contract_sha256=reference_closure.CONTRACT_SHA256,
                            scoring_contract_sha256=evidence_scoring.CONTRACT_SHA256)
        if portion > 1 or not payload.get("sources"):
            try:
                evidence_scoring.verify_assets(os.environ.get("DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH", ""))
            except (ValueError, OSError) as exc:
                return stop_packet(payload, snapshot, retrieval, "scan_incomplete",
                                   failed_stage="model_provenance", error=str(exc))
    token = continuation_fingerprint(payload, snapshot, retrieval, policy=POLICY,
                                     settings=settings, limit=EMERGENCY_TOKENS,
                                     max_source_references=None, request_binding=request)
    if continuation_token is not None and continuation_token != token:
        raise ValueError("stale_context_continuation")
    if portion > 1:
        if continuation_token is None:
            raise ValueError("context_continuation_required")
        result, bound = stop_packet(payload, snapshot, retrieval, "context_portion_exhausted")
        result["more_context"] = continuation_metadata(portion, token, 0, 0)
        _refresh_estimate(result)
        return result, bound
    if not payload.get("sources"):
        return payload, snapshot
    focus = retrieval.get("_focused_source_path")
    if focus:
        rows = [row for row in payload["sources"] if row.get("path_or_url") == focus]
        payload, snapshot = _rebuild(payload, snapshot, retrieval, rows, reason=POLICY)
    observations = _OBSERVER.get()
    work_observation = None

    def record_work(receipt):
        nonlocal work_observation
        if observations is not None and work_observation is None:
            if reference_mode:
                receipt = {**receipt, "selection_recipe": reference_closure.RECIPE,
                           "closure_contract_sha256": reference_closure.CONTRACT_SHA256}
            work_observation = {"receipt": receipt, "policy_sha256": policy_digest,
                                "delivery_status": "not_confirmed"}
            observations.append(work_observation)

    try:
        structure = build_units(payload, snapshot, retrieval,
                                **({"recipe": structural_recipe} if evidence_mode else {}))
        if evidence_mode:
            scores, scoring = _scored_units_with_cache(
                original, structure,
                os.environ.get("DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH", ""),
                _OBSERVER.get() is not None)
            if reference_mode:
                scoring = {**scoring, "selection_recipe": reference_closure.RECIPE,
                           "closure_contract_sha256": reference_closure.CONTRACT_SHA256}
        else:
            scores, scoring = score_complete_units(lanes, structure.units,
                                               os.environ.get("DOCATLAS_EXPERIMENT_MINI_PATH", ""),
                                               own_body_gate=scoring_recipe() == GATED_WINDOW_RECIPE,
                                               **({"fit_whole_pair": True,
                                                   "record_intervals": _OBSERVER.get() is not None}
                                                  if scoring_recipe() == FIT_WINDOW_RECIPE else {}))
        # Record performed work before any selection/closure/delivery operation.
        # One observation per query; an eventual delivery failure cannot erase it.
        record_work(scoring)
        if work_observation is not None:
            work_observation["scores"] = [{**row, **structure.metadata.get(row["identity"], {})} for row in scores]
        selected = {row["identity"] for row in scores
                    if policy is None or row["score"] >= policy["threshold"]}
        budget = _research_delivery_budget()
        if budget is None:
            rows, bound, closure = close_selection(
                structure, selected, payload, snapshot, retrieval,
                **({"reference_expansion": link_expansion} if link_expansion != OFF else {}))
        if budget is None and reference_mode and closure["incomplete_dependencies"]:
            stopped, bound = stop_packet(payload, snapshot, retrieval, "dependency_incomplete",
                                        failed_stage="reference_closure", receipt=scoring, closure=closure,
                                        scan_complete=True)
            stopped.update(status="error", hard_stop=True)
            _refresh_estimate(stopped)
            return stopped, bound
    except JointSemanticRelevanceError as exc:
        record_work(exc.receipt)
        return stop_packet(payload, snapshot, retrieval, "scan_incomplete",
                           failed_stage="semantic_scoring", receipt=exc.receipt)
    except (ValueError, OSError) as exc:
        return stop_packet(payload, snapshot, retrieval, "scan_incomplete",
                           failed_stage="structural_source_check", error=str(exc))
    if budget is not None:
        return _fit_research_budget(
            payload, snapshot, retrieval, structure=structure, selected=selected,
            scores=scores, scoring=scoring, policy_digest=policy_digest,
            policy=policy, token=token, link_expansion=link_expansion,
            reference_mode=reference_mode, evidence_mode=evidence_mode,
            observations=observations, work_observation=work_observation,
            budget=budget, finalize_packet=finalize_packet)
    result, bound = _rebuild(payload, bound, retrieval, rows, reason=POLICY)
    # Closure produces trusted checked rows with transient attribution fields;
    # _payload canonicalizes the public row shape. Bind that canonical shape,
    # exactly as the native source projector does after its own _payload call.
    bound = {row["evidence_id"]: {
                 **_snapshot_entry(bound[row["evidence_id"]]["source"], row),
                 **{key: bound[row["evidence_id"]][key]
                    for key in ("structural_native_candidate", "structural_recipe")
                    if key in bound[row["evidence_id"]]},
             }
             for row in result.get("sources", ())}
    result["source_selection"] = {
        "policy": POLICY, "calibration_sha256": policy_digest,
        "calibration_status": "diagnostic_unverified" if policy is None else "empirical",
        "candidate_units": len(scores), "selected_units": len(selected),
        "delivered_rows": len(rows), "scan_complete": True,
        "model_pairs": scoring["model_pairs"], "closure": model_closure_receipt(closure),
    }
    if link_expansion != OFF:
        result["source_selection"]["calibration_scope"] = "selected_units_before_link_expansion"
    retrieval.setdefault("retrieval_diagnostics", {})["minimal_context"] = {
        **({"scores": scores} if not evidence_mode or observations is not None else {}),
        "receipt": scoring, "policy_sha256": policy_digest,
        "closure": closure,
    }
    result["context_quality"] = {"status": "unverified" if rows else "unavailable",
                                 "reasons": ["coverage_unverified"]}
    if closure.get("incomplete_dependencies"):
        result["context_quality"]["reasons"].append("incomplete_structural_dependency")
    if rows:
        result["status"] = "ok"
    else:
        result.update(status="insufficient_evidence", reason_code="no_relevant_source_context",
                      missing=["No structural unit met the frozen empirical relevance threshold."])
    # Semantic rejects are not deferred pages.
    result["more_context"] = continuation_metadata(1, token, len(rows), len(rows))
    root = str(retrieval.get("_source_continuation_project_root") or "")
    if root and rows:
        attach_source_continuation_locators(result, bound, root=root, max_tokens=EMERGENCY_TOKENS)
    _refresh_estimate(result)
    try:
        for row in result.get("sources", ()):
            recheck_structural_row(row, bound[row["evidence_id"]], retrieval)
    except (ValueError, OSError) as exc:
        return stop_packet(result, bound, retrieval, "scan_incomplete",
                           failed_stage="terminal_structural_recheck", error=str(exc))
    errors = validate_model_visible_projection(result, snapshot=bound)
    if errors:
        return stop_packet(result, bound, retrieval, "scan_incomplete",
                           failed_stage="delivery_validation", errors=errors)
    measured = delivery_size(result)
    if measured > EMERGENCY_TOKENS:
        return stop_packet(result, bound, retrieval, "context_emergency_stop",
                           measured_tokens=measured, emergency_tokens=EMERGENCY_TOKENS,
                           selected_units=len(selected), model_pairs=scoring["model_pairs"],
                           scan_complete=True, scope=request.get("scope", "all"))
    if finalize_packet is not None:
        result, bound = finalize_packet(result, bound)
    if work_observation is not None:
        work_observation["delivery_status"] = "returned"
    return result, bound
