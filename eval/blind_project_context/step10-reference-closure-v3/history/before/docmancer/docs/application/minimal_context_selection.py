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
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from docmancer.docs.domain.minimal_context_config import EMERGENCY_TOKENS
from .complete_context_scoring import WINDOW_RECIPE, GATED_WINDOW_RECIPE, FIT_WINDOW_RECIPE, score_complete_units
from .experimental_selection_modes import MINI_REVISION, JointSemanticRelevanceError
from .context_continuation import continuation_fingerprint, continuation_metadata
from .context_json import serialize_context_json
from .experimental_context_finalization import _rebuild
from .model_visible_projection import _refresh_estimate, _snapshot_entry, validate_model_visible_projection
from .projection_tokenizer import projection_token_count
from .standalone_text_view import render_standalone_text
from . import context_evidence_scoring as evidence_scoring


POLICY = "complete_calibrated_context_v1"
STRUCTURAL_RECIPE = "minimal-structure-v1"
EVIDENCE_STRUCTURAL_RECIPE = evidence_scoring.STRUCTURAL_RECIPE
_OBSERVER = ContextVar("minimal_context_observer", default=None)


def scoring_recipe() -> str:
    recipe = os.environ.get("DOCATLAS_MINIMAL_CONTEXT_RECIPE", WINDOW_RECIPE)
    if recipe not in {WINDOW_RECIPE, GATED_WINDOW_RECIPE, FIT_WINDOW_RECIPE, evidence_scoring.RECIPE}:
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
    if scoring_recipe() == evidence_scoring.RECIPE:
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
    result.pop("more_context", None)
    result["missing"] = [reason]
    _refresh_estimate(result)
    return result, bound


def delivery_size(packet: dict) -> int:
    """Price the whole supported rendering, not a byte/4 approximation."""
    rendered = render_standalone_text(packet)
    text = rendered.text if rendered.text is not None else serialize_context_json(packet)
    return projection_token_count(text.encode("utf-8"))


def select_minimal_context(payload: dict, snapshot: dict, retrieval: dict, *,
                           portion: int, continuation_token: str | None,
                           request_binding: dict | None, finalize_packet=None) -> tuple[dict, dict]:
    from .minimal_context_structure import build_units, close_selection, recheck_structural_row
    from .source_continuation import attach_source_continuation_locators

    policy, policy_digest = load_policy()
    evidence_mode = scoring_recipe() == evidence_scoring.RECIPE
    structural_recipe = EVIDENCE_STRUCTURAL_RECIPE if evidence_mode else STRUCTURAL_RECIPE
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
    if evidence_mode:
        settings.update(model_revision=evidence_scoring.REVISION, structural_recipe=structural_recipe,
                        model_id=evidence_scoring.MODEL_ID, contract_sha256=evidence_scoring.CONTRACT_SHA256,
                        lanes="exact_original_only")
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
            work_observation = {"receipt": receipt, "policy_sha256": policy_digest,
                                "delivery_status": "not_confirmed"}
            observations.append(work_observation)

    try:
        structure = build_units(payload, snapshot, retrieval,
                                **({"recipe": structural_recipe} if evidence_mode else {}))
        if evidence_mode:
            from .context_evidence_structure import EvidenceDocuments
            documents = EvidenceDocuments(structure)
            scores, scoring = evidence_scoring.score_evidence_units(
                original, tuple(unit.identity for unit in structure.units), documents,
                os.environ.get("DOCATLAS_EXPERIMENT_EVIDENCE_MODEL_PATH", ""),
                diagnostics=_OBSERVER.get() is not None)
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
        rows, bound, closure = close_selection(structure, selected, payload, snapshot, retrieval)
    except JointSemanticRelevanceError as exc:
        record_work(exc.receipt)
        return stop_packet(payload, snapshot, retrieval, "scan_incomplete",
                           failed_stage="semantic_scoring", receipt=exc.receipt)
    except (ValueError, OSError) as exc:
        return stop_packet(payload, snapshot, retrieval, "scan_incomplete",
                           failed_stage="structural_source_check", error=str(exc))
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
        "model_pairs": scoring["model_pairs"], "closure": closure,
    }
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
