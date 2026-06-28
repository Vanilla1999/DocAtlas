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


def test_candidate_scoring_rewards_distributed_context():
    plain = score_candidate(_candidate())
    distributed = score_candidate(
        _candidate(
            requires_distributed_context=True,
            has_nearby_tempting_wrong_fix=True,
            pinned_dependency_matters=True,
        )
    )

    assert distributed["docatlas_relevance_score"] > plain["docatlas_relevance_score"]
    assert distributed["repo_only_difficulty_score"] > plain["repo_only_difficulty_score"]


def test_candidate_scoring_penalizes_obvious_public_test_patch():
    hard = score_candidate(_candidate(requires_distributed_context=True, has_nearby_tempting_wrong_fix=True))
    obvious = score_candidate(
        _candidate(
            requires_distributed_context=True,
            has_nearby_tempting_wrong_fix=True,
            public_tests_reveal_patch=True,
        )
    )

    assert obvious["repo_only_difficulty_score"] < hard["repo_only_difficulty_score"]
    assert obvious["recommended"] is False


def test_candidate_scoring_penalizes_privacy_risk():
    safe = score_candidate(_candidate(requires_distributed_context=True, has_nearby_tempting_wrong_fix=True))
    risky = score_candidate(
        _candidate(
            requires_distributed_context=True,
            has_nearby_tempting_wrong_fix=True,
            exposes_private_domain=True,
        )
    )

    assert risky["privacy_risk_score"] > safe["privacy_risk_score"]
    assert risky["recommended"] is False


def test_candidate_requires_visible_hidden_contracts():
    visible = _candidate(hidden_contract_visible=True, hidden_contract_sources=("docs/architecture.md",))
    hidden_only = _candidate(hidden_contract_visible=False, hidden_contract_sources=())

    assert visible.requires_visible_hidden_contracts()
    assert not hidden_only.requires_visible_hidden_contracts()
    assert score_candidate(hidden_only)["fairness_score"] < score_candidate(visible)["fairness_score"]
