"""M3 — context-only relevance rescue for insufficient_visible_match.

Experimental wrapper around qualify_evidence that admits a block as
"context-only" context when:
- The rejection reason is exactly ``insufficient_visible_match``.
- No other veto applies (policy, exact terms, bound subjects, local witness).
- A neural relevance score meets the calibrated threshold.

Admitted traces are patched with:
- ``qualified=True``  (so the block survives ranking, dedup, delivery)
- ``admission_only=True``  (so no covered_query_ids, no answer_supported)
- ``admission_route="context_only_relevance"``
- ``context_relevance_score`` (the internal score, for traceability)
- ``context_relevance_binding`` (hash binding to question/source/text/model)

This does NOT create factual/parent coverage and does NOT raise
``answer_supported`` or ``edit_ready``.

Scorer limits (pilot): K=60 evaluations, cooperative deadline=10s per stage.
This rejects late results; it does not cancel an in-flight native call.
On error/deadline: degraded fallback (keep old path, no rescue).

Production activation is a separate maintainer decision (P0 freeze).
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import threading
import asyncio
from contextlib import contextmanager, ExitStack
from dataclasses import replace
from typing import Any, Callable
from unittest.mock import patch

from docmancer.docs.domain.evidence_qualification import (
    EvidenceQualification,
    qualify_evidence as _original_qualify,
)

Scorer = Callable[[str, str], float]

M2B_THRESHOLD = 0.7453
MODEL_REVISION = "Xenova/paraphrase-multilingual-mpnet-base-v2"
# Bind the unchanged threshold to its archived result and scoring contract.
# This is a specification hash, NOT a fabricated hash of model weights.
CALIBRATION_SPEC = {
    "threshold": M2B_THRESHOLD, "score_kind": "cosine",
    "results_git_blob": "0c2c0261888d2c039881cecd938b844c514ca55f",
    "manifest_git_blob": "7491989ffeb3737af9046f8287962e72351c0ee7",
    "source_branch_commit": "84938ab25c096257a7ad6af5f39b9d364e67b8e9",
}
CALIBRATION_DIGEST = hashlib.sha256(json.dumps(
    CALIBRATION_SPEC, sort_keys=True, separators=(",", ":")
).encode()).hexdigest()
MAX_EVALUATIONS = 60
SCORER_TIMEOUT_SECONDS = 10.0
# Kept as a historical diagnostic constant for existing experiment imports.
# It is no longer an admission gate: nonempty short rules may be scored.
MIN_EVIDENCE_CHARS = 80

from .scorer_runtime import BoundedScorer, text_digest

_INSTALL_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Score binding
# ---------------------------------------------------------------------------
def _text_hash(text: str) -> str:
    return text_digest(text)


def _question_hash(question: str) -> str:
    return text_digest(question)


def _build_binding(
    question: str, evidence_text: str, source_identity: str,
) -> dict[str, Any]:
    return {
        "question_hash": _question_hash(question),
        "source_identity": source_identity,
        "text_hash": _text_hash(evidence_text),
        "model_revision": MODEL_REVISION,
        "calibration_digest": CALIBRATION_DIGEST,
    }


# ---------------------------------------------------------------------------
# Veto check — safety net beyond the reason check
# ---------------------------------------------------------------------------
def _has_other_veto(result: dict[str, Any]) -> bool:
    """Check if any veto besides insufficient_visible_match applies."""
    if result.get("missing_exact_terms"):
        return True
    if result.get("missing_parent_exact_terms"):
        return True
    if result.get("missing_bound_subjects"):
        return True
    return False


# ---------------------------------------------------------------------------
# Rescue application
# ---------------------------------------------------------------------------
def apply_rescue(
    original: EvidenceQualification,
    *,
    query_id: str,
    question: str,
    evidence_text: str,
    source_identity: str,
    scorer: BoundedScorer,
    source_binding: dict[str, Any] | None = None,
    threshold: float = M2B_THRESHOLD,
) -> EvidenceQualification:
    """Patch a qualification result with context-only admission if eligible.

    Returns the original result unchanged if:
    - The block already qualified.
    - The rejection reason is not ``insufficient_visible_match``.
    - Another veto (exact, subject) is present in the trace.
    - The evidence text is empty (short complete rules are allowed).
    - The scorer is degraded.
    - The neural score is below the threshold.
    """
    if not math.isfinite(threshold):
        raise ValueError("threshold must be finite")
    if original.qualified:
        return original
    if original.reason != "insufficient_visible_match":
        return original
    if not evidence_text.strip():
        scorer.record_decision(question, evidence_text, decision="empty_evidence", query_id=query_id)
        return original
    result = dict(original.trace)
    if _has_other_veto(result):
        return original
    score = scorer.score(question, evidence_text)
    if score is None:
        # Degraded: keep old path, mark reason.
        patched_trace = dict(result)
        patched_trace["context_relevance_degraded"] = True
        if scorer.degraded_reason:
            patched_trace["context_relevance_degraded_reason"] = scorer.degraded_reason
        return replace(original, trace=patched_trace)
    scorer.record_decision(question, evidence_text, query_id=query_id,
        decision="below_threshold" if score < threshold else "context_only_relevance",
        score=score, threshold=threshold, source_identity=source_identity,
        source_binding=dict(source_binding or {}))
    if score < threshold:
        return original
    binding = _build_binding(question, evidence_text, source_identity)
    try:
        binding["scorer_identity"] = scorer.identity()
    except Exception:
        return replace(original, trace={**result, "context_relevance_degraded": True,
            "context_relevance_degraded_reason": "scorer_identity_error"})
    binding["model_revision"] = (binding["scorer_identity"].get("hub_revision")
        or binding["scorer_identity"].get("fingerprint") or "unverified_callable")
    binding["threshold_used"] = threshold
    binding["threshold_matches_archived_calibration"] = threshold == M2B_THRESHOLD
    binding["source_binding"] = dict(source_binding or {})
    patched_trace = dict(result)
    patched_trace.update(
        qualified=True,
        admission_only=True,
        admission_route="context_only_relevance",
        context_relevance_score=score,
        context_relevance_threshold=threshold,
        context_relevance_binding=binding,
        qualification_reason="context_only_relevance",
        covered_query_ids=(),
        coverage_kind=None,
    )
    return replace(
        original,
        qualified=True,
        covered_query_ids=(),
        coverage_kind=None,
        reason="context_only_relevance",
        trace=patched_trace,
    )


# ---------------------------------------------------------------------------
# Installation — patch qualify_evidence in all importing modules
# ---------------------------------------------------------------------------
@contextmanager
def installed(scorer: Scorer | BoundedScorer, *, threshold: float = M2B_THRESHOLD,
              question: str, source_identity: str = "local:test"):
    """Patch qualify_evidence callers to apply context-only rescue.

    Patches the function in every module that imported it by name.
    The scorer receives (question, evidence_text) and returns a float.
    """
    if not math.isfinite(threshold):
        raise ValueError("threshold must be finite")
    if not _INSTALL_LOCK.acquire(blocking=False):
        raise RuntimeError("rescue installation is isolated: nested/concurrent use is forbidden")
    owner_thread = threading.get_ident()
    def current_task():
        try:
            return asyncio.current_task()
        except RuntimeError:
            return None
    owner_task = current_task()
    try:
        bounded = scorer if isinstance(scorer, BoundedScorer) else BoundedScorer(scorer)
        def _patched_qualify(probe, *, query_id, visible_text, evidence_text=None, **kwargs):
            result = _original_qualify(probe, query_id=query_id, visible_text=visible_text,
                                       evidence_text=evidence_text, **kwargs)
            # Other threads/tasks must never use the installing request's question.
            if threading.get_ident() != owner_thread or current_task() is not owner_task:
                return result
            text = evidence_text if evidence_text is not None else visible_text
            candidate = kwargs.get("candidate") or {}
            identity = str(candidate.get("project_identity") or source_identity)
            reference = candidate.get("_reference_evidence") or {}
            provenance = {key: candidate.get(key) for key in (
                "path", "path_or_url", "resolved_version", "generation_id",
                "_source_snapshot_sha256", "_source_catalog_hash", "char_start", "char_end",
                "line_start", "line_end",
            ) if candidate.get(key) is not None}
            provenance["reference_source"] = reference.get("source")
            return apply_rescue(result, query_id=query_id, question=question,
                evidence_text=text, source_identity=identity, source_binding=provenance,
                scorer=bounded, threshold=threshold)

        targets = [
            "docmancer.docs.domain.evidence_qualification",
            "docmancer.docs.application.context_query_probes",
            "docmancer.docs.application.reference_query_tagging",
            "docmancer.docs.application._docs_context_projection_core",
            "docmancer.docs.domain.context_hint_policy",
        ]
        with ExitStack() as stack:
            for module_path in targets:
                module = __import__(module_path, fromlist=["qualify_evidence"])
                stack.enter_context(patch.object(module, "qualify_evidence", _patched_qualify))
            yield bounded
    finally:
        _INSTALL_LOCK.release()
