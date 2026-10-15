from __future__ import annotations

from eval.task_level.task_mining.candidates import MinedCandidate
from eval.task_level.task_mining.scoring import score_candidate


def _candidate(**overrides: object) -> MinedCandidate:
    data = {
        "task_id": "candidate_001",
        "source_project": "nbo",
        "candidate_type": "historical_fix",
        "title": "Candidate",
        "summary": "Sanitized candidate",
        "visible_context_needed": ("docs/architecture.md",),
        "tempting_wrong_fix": ("local patch",),
        "hidden_contract_sources": ("docs/architecture.md",),
        "public_test_signal": "Behavioral public test",
        "estimated_fixture_size": "medium",
        "fixture_cost_score": 5,
        "hidden_contract_visible": True,
    }
    data.update(overrides)
    return MinedCandidate(**data)







