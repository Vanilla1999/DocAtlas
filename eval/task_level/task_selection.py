from __future__ import annotations

from typing import Literal


CandidateStatus = Literal["accepted", "rejected_too_easy", "rejected_unfair", "needs_redesign"]


def decide_candidate_status(*, repo_only_repeats: int, repo_only_resolved: int, fairness_clean: bool, hidden_oracle_only: bool) -> CandidateStatus:
    """Apply the pre-pilot screening rule for real-project candidate tasks."""
    if hidden_oracle_only or not fairness_clean:
        return "rejected_unfair"
    if repo_only_resolved >= repo_only_repeats:
        return "rejected_too_easy"
    if repo_only_resolved <= max(0, repo_only_repeats - 1):
        return "accepted"
    return "needs_redesign"
