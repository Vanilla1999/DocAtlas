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

Scorer limits (pilot): K=20 evaluations, timeout=10s per stage.
On error/timeout: degraded fallback (keep old path, no rescue).

Production activation is a separate maintainer decision (P0 freeze).
"""
from __future__ import annotations

import hashlib
import time
from contextlib import contextmanager
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
CALIBRATION_DIGEST = "m2b-calibration-v1"
MAX_EVALUATIONS = 60
SCORER_TIMEOUT_SECONDS = 10.0
MIN_EVIDENCE_CHARS = 80


# ---------------------------------------------------------------------------
# Score binding
# ---------------------------------------------------------------------------
def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _question_hash(question: str) -> str:
    return hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]


def _build_binding(
    question: str, evidence_text: str, source_identity: str,
) -> dict[str, str]:
    return {
        "question_hash": _question_hash(question),
        "source_identity": source_identity,
        "text_hash": _text_hash(evidence_text),
        "model_revision": MODEL_REVISION,
        "calibration_digest": CALIBRATION_DIGEST,
    }


# ---------------------------------------------------------------------------
# Bounded scorer — enforces K, timeout, error fallback
# ---------------------------------------------------------------------------
class BoundedScorer:
    """Wraps a scorer with evaluation limits, timeout, and cache."""

    def __init__(self, scorer: Scorer, *, max_evaluations: int = MAX_EVALUATIONS,
                 timeout: float = SCORER_TIMEOUT_SECONDS):
        self._scorer = scorer
        self._max = max_evaluations
        self._timeout = timeout
        self._count = 0
        self._cache: dict[tuple[str, str], float] = {}
        self._degraded = False
        self._degraded_reason: str | None = None

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def degraded_reason(self) -> str | None:
        return self._degraded_reason

    def score(self, question: str, evidence_text: str) -> float | None:
        """Return score, or None if degraded/timeout/error/over-limit."""
        cache_key = (_question_hash(question), _text_hash(evidence_text))
        if cache_key in self._cache:
            return self._cache[cache_key]
        if self._degraded:
            return None
        if self._count >= self._max:
            self._degraded = True
            self._degraded_reason = "evaluation_limit_reached"
            return None
        self._count += 1
        try:
            start = time.monotonic()
            value = float(self._scorer(question, evidence_text))
            elapsed = time.monotonic() - start
            if elapsed > self._timeout:
                self._degraded = True
                self._degraded_reason = "scorer_timeout"
                return None
        except Exception:
            self._degraded = True
            self._degraded_reason = "scorer_error"
            return None
        self._cache[cache_key] = value
        return value


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
    threshold: float = M2B_THRESHOLD,
) -> EvidenceQualification:
    """Patch a qualification result with context-only admission if eligible.

    Returns the original result unchanged if:
    - The block already qualified.
    - The rejection reason is not ``insufficient_visible_match``.
    - Another veto (exact, subject) is present in the trace.
    - The evidence text is too short for meaningful neural scoring.
    - The scorer is degraded.
    - The neural score is below the threshold.
    """
    if original.qualified:
        return original
    if original.reason != "insufficient_visible_match":
        return original
    if len(evidence_text.strip()) < MIN_EVIDENCE_CHARS:
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
    if score < threshold:
        return original
    binding = _build_binding(question, evidence_text, source_identity)
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
    if isinstance(scorer, BoundedScorer):
        bounded = scorer
    else:
        bounded = BoundedScorer(scorer)

    def _patched_qualify(probe, *, query_id, visible_text, evidence_text=None, **kwargs):
        result = _original_qualify(probe, query_id=query_id, visible_text=visible_text,
                                   evidence_text=evidence_text, **kwargs)
        text = evidence_text if evidence_text is not None else visible_text
        candidate = kwargs.get("candidate") or {}
        identity = str(candidate.get("project_identity") or source_identity)
        # Revalidate the current evidence; serialized prior admission is not authority.
        return apply_rescue(
            result, query_id=query_id, question=question,
            evidence_text=text, source_identity=identity,
            scorer=bounded, threshold=threshold,
        )

    targets = [
        "docmancer.docs.domain.evidence_qualification",
        "docmancer.docs.application.context_query_probes",
        "docmancer.docs.application.reference_query_tagging",
        "docmancer.docs.application._docs_context_projection_core",
        "docmancer.docs.domain.context_hint_policy",
    ]
    patches = []
    for module_path in targets:
        patches.append(patch.object(
            __import__(module_path, fromlist=["qualify_evidence"]),
            "qualify_evidence",
            _patched_qualify,
        ))
    for p in patches:
        p.start()
    try:
        yield bounded
    finally:
        for p in patches:
            p.stop()
