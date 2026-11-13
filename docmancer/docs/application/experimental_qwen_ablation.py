"""Opt-in diagnostic Qwen selection ablations; no inference or production default.

Enable DOCATLAS_EXPERIMENT_QWEN_STUDY=1 with PAIRED_QWEN=1 and an explicit
DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE. Modes are mutually exclusive. The
caller retains default acquisition, pruning, eligibility, grouping, locator
routing, cost/tie ordering and the exact delivery/reference fitter. Existing
paired-selector compatibility guards must remain in place.

Transform the entire scored post-prune row pool once, before unit max reduction
and the existing locator override. Keep raw scorer/cache/trace scores unchanged.
Relative values are pool-relative ranking signals, NOT calibrated probabilities
or evidence of answer sufficiency. No thresholds or holdout-dependent choices.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import os
from typing import Mapping, Sequence


STUDY_ENV = "DOCATLAS_EXPERIMENT_QWEN_STUDY"
MODE_ENV = "DOCATLAS_EXPERIMENT_QWEN_SELECTION_MODE"
MODES = ("control", "no_stop", "no_redundancy", "relative")
RECIPE = "qwen-selection-ablation-v1"


@dataclass(frozen=True)
class QwenStudySettings:
    """None is OFF; instantiate via load_settings to validate environment guards."""

    mode: str | None = None

    def __post_init__(self) -> None:
        if self.mode is not None and self.mode not in MODES:
            raise ValueError("qwen_study_invalid_selection_mode")

    def transform_scores(self, scores: Sequence[float]) -> Sequence[float]:
        """Return the original scores except in relative mode; never mutate them.

        Paired scoring already requires finite [0, 1] values. Recheck this only
        for relative mode so malformed inputs cannot become plausible rankings.
        An empty/all-zero pool has scale zero and stays empty/all-zero.
        """
        if self.mode != "relative":
            return scores
        if any(isinstance(score, bool) or not isinstance(score, (int, float))
               or not math.isfinite(score) or not 0 <= score <= 1 for score in scores):
            raise ValueError("qwen_study_invalid_raw_score")
        scale = max((score for score in scores if math.isfinite(score) and score > 0), default=0.0)
        return [score / scale if scale > 0 else 0.0 for score in scores]

    def marginal_gain(self, relevance: float, redundancy: float) -> float:
        """Change ONLY similarity subtraction; locator-adjusted relevance enters."""
        return relevance if self.mode == "no_redundancy" else relevance - redundancy

    def should_stop(self, priority_gain: float) -> bool:
        """Gate ONLY the whole-loop nonpositive stop, not eligibility or fitting.

        no_stop keeps the SAME max-priority candidate, cost divisor and ties.
        It must proceed to candidate removal and the original exact fitter;
        skipping a candidate or clamping its gain would be a different ablation.
        """
        return self.mode != "no_stop" and priority_gain <= 0

    def trace_receipt(self) -> dict:
        """JSON-ready settings for the separate paired trace, never the packet."""
        if self.mode is None:
            return {}
        return {
            "recipe": RECIPE,
            "study": True,
            "mode": self.mode,
            "score_formula": (
                "M = max({s_j in scored post-prune row pool | finite(s_j) and s_j > 0}, default=0); "
                "r_i = s_i / M if M > 0 else 0"
                if self.mode == "relative" else "r_i = s_i (raw Qwen score unchanged)"
            ),
            "relevance_formula": (
                "R(unit) = mean_q(max(max_{i in unit}(r_i), "
                "1 if q in unit.locator_queries else 0))"
            ),
            "redundancy_formula": (
                "D = max(similarity(unit, selected_unit) for selected_unit in other groups, default=0)"
            ),
            "gain_formula": "G = R" if self.mode == "no_redundancy" else "G = R - D",
            "priority_formula": "(G / sqrt(cost_bytes), R, -min(row_indices))",
            "stop_formula": (
                "no whole-loop stop on nonpositive priority; keep same priority and exact fitter"
                if self.mode == "no_stop" else "stop whole loop when best priority[0] <= 0"
            ),
            "unchanged": ["raw scorer/cache scores", "acquisition", "pruning", "eligibility",
                          "grouping", "locator override", "cost and ties", "exact budget/reference fitter"],
            "interpretation": "diagnostic ranking only; no calibration or sufficiency claim",
        }

    def continuation_settings(self) -> dict:
        """Merge into fingerprint settings; OFF adds no keys or identity change."""
        return {"qwen_study": self.trace_receipt()} if self.mode is not None else {}


def load_settings(environ: Mapping[str, str] | None = None) -> QwenStudySettings:
    """Fail closed on missing modes, typos, unguarded modes or non-Qwen study.

    Unset/0 study and absent mode preserve OFF. Study=1 requires an explicit
    mode (including control) and the existing paired Qwen switch exactly 1.
    Validate at the public selection entry before any early return. The caller
    still enforces existing paired native-budget/default-selector constraints.
    """
    env = os.environ if environ is None else environ
    study, mode = env.get(STUDY_ENV), env.get(MODE_ENV)
    if study not in (None, "0", "1"):
        raise ValueError("qwen_study_guard_must_be_0_or_1")
    if study != "1":
        if mode is not None:
            raise ValueError("qwen_selection_mode_requires_study_1")
        return QwenStudySettings()
    if env.get("DOCATLAS_EXPERIMENT_PAIRED_QWEN") != "1":
        raise ValueError("qwen_study_requires_paired_qwen_1")
    if mode not in MODES:
        raise ValueError("qwen_study_requires_explicit_control_no_stop_no_redundancy_or_relative")
    return QwenStudySettings(mode)
