from __future__ import annotations

from eval.task_level.task_mining.candidates import MinedCandidate


def _clamp(value: int) -> int:
    return max(0, min(10, value))


def score_candidate(candidate: MinedCandidate) -> dict[str, object]:
    docatlas_relevance_score = 3
    repo_only_difficulty_score = 3
    fairness_score = 5
    privacy_risk_score = 1

    if candidate.requires_distributed_context:
        docatlas_relevance_score += 3
        repo_only_difficulty_score += 2
    if candidate.has_nearby_tempting_wrong_fix:
        repo_only_difficulty_score += 2
    if candidate.pinned_dependency_matters:
        docatlas_relevance_score += 2
        repo_only_difficulty_score += 1
    if candidate.generated_source_of_truth_trap:
        docatlas_relevance_score += 1
        repo_only_difficulty_score += 1
    if candidate.historical_fix_available:
        docatlas_relevance_score += 1
        fairness_score += 1
    if candidate.hidden_contract_visible:
        fairness_score += 3
    else:
        fairness_score -= 4
    if candidate.public_tests_reveal_patch:
        repo_only_difficulty_score -= 4
        docatlas_relevance_score -= 2
    if candidate.exposes_private_domain:
        privacy_risk_score += 5
        fairness_score -= 1
    if candidate.requires_heavy_runtime:
        privacy_risk_score += 1
    if candidate.gold_patch_large:
        repo_only_difficulty_score -= 1
        fairness_score -= 1

    docatlas_relevance_score = _clamp(docatlas_relevance_score)
    repo_only_difficulty_score = _clamp(repo_only_difficulty_score)
    fairness_score = _clamp(fairness_score)
    privacy_risk_score = _clamp(privacy_risk_score)
    fixture_cost_score = _clamp(candidate.fixture_cost_score)
    recommended = (
        repo_only_difficulty_score >= 7
        and docatlas_relevance_score >= 7
        and fairness_score >= 8
        and privacy_risk_score <= 3
        and fixture_cost_score <= 6
    )

    return {
        "task_id": candidate.task_id,
        "source_project": candidate.source_project,
        "candidate_type": candidate.candidate_type,
        "docatlas_relevance_score": docatlas_relevance_score,
        "repo_only_difficulty_score": repo_only_difficulty_score,
        "fairness_score": fairness_score,
        "privacy_risk_score": privacy_risk_score,
        "fixture_cost_score": fixture_cost_score,
        "recommended": recommended,
        "reason": _reason(
            candidate,
            recommended,
            docatlas_relevance_score,
            repo_only_difficulty_score,
            fairness_score,
            privacy_risk_score,
            fixture_cost_score,
        ),
    }


def _reason(
    candidate: MinedCandidate,
    recommended: bool,
    docatlas_score: int,
    difficulty_score: int,
    fairness_score: int,
    privacy_score: int,
    fixture_cost_score: int,
) -> str:
    if recommended:
        return "Meets pre-implementation thresholds for a mined real-project candidate."

    blockers: list[str] = []
    if docatlas_score < 7:
        blockers.append("DocAtlas relevance below 7")
    if difficulty_score < 7:
        blockers.append("repo-only difficulty below 7")
    if fairness_score < 8:
        blockers.append("fairness below 8 or hidden contract not visible enough")
    if privacy_score > 3:
        blockers.append("privacy risk above 3")
    if fixture_cost_score > 6:
        blockers.append("fixture cost above 6")
    if candidate.public_tests_reveal_patch:
        blockers.append("public tests reveal the likely patch")
    return "; ".join(blockers)
