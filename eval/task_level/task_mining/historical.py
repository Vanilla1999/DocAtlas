from __future__ import annotations

import json
import re
from pathlib import Path

from eval.task_level.task_mining.candidates import MinedCandidate
from eval.task_level.task_mining.scoring import score_candidate


PRIVATE_TEXT_PATTERNS = re.compile(r"(coderepo\.corp|git@|https://github\.com/|AKIA[0-9A-Z]{16}|-----BEGIN)", re.IGNORECASE)


def build_seed_candidates() -> list[MinedCandidate]:
    """Return sanitized pre-screening candidates; raw project history is never embedded."""
    return [
        MinedCandidate(
            task_id="real_project_nbo_generated_policy_source_001",
            source_project="nbo",
            candidate_type="generated_file_trap",
            title="Generated permission metadata source-of-truth mismatch",
            summary="A generated model output appears to miss a policy flag, but the visible convention says edits must happen in the source model.",
            visible_context_needed=("docs/generated-files.md", "permission source model", "generated model output", "architecture notes"),
            tempting_wrong_fix=("edit generated .freezed.dart output", "duplicate metadata in provider", "patch only the public test fixture"),
            hidden_contract_sources=("docs/generated-files.md", "source-model comments"),
            public_test_signal="Runtime metadata assertion; should not name the generated-file rule as the exact patch.",
            estimated_fixture_size="medium",
            fixture_cost_score=5,
            requires_distributed_context=True,
            has_nearby_tempting_wrong_fix=True,
            hidden_contract_visible=True,
            generated_source_of_truth_trap=True,
        ),
        MinedCandidate(
            task_id="real_project_nbo_permission_handler_version_001",
            source_project="nbo",
            candidate_type="dependency_trap",
            title="Pinned permission-handler API mismatch",
            summary="A permission status mapping bug should be fixed against the lockfile-pinned API rather than latest public API memory.",
            visible_context_needed=("pubspec.lock", "dependency usage notes", "permission mapping source", "fake status tests"),
            tempting_wrong_fix=("invent latest-only enum members", "change dependency versions", "patch platform-specific branch only"),
            hidden_contract_sources=("pubspec.lock", "docs/dependencies.md"),
            public_test_signal="Fake status mapping test reproduces behavior without naming the exact dependency symbol to use.",
            estimated_fixture_size="medium-large",
            fixture_cost_score=7,
            requires_distributed_context=True,
            has_nearby_tempting_wrong_fix=True,
            hidden_contract_visible=True,
            pinned_dependency_matters=True,
        ),
        MinedCandidate(
            task_id="real_project_historical_architecture_contract_001",
            source_project="sanitized_real_project",
            candidate_type="historical_fix",
            title="Historical architecture-sensitive behavior fix",
            summary="A real fix commit shape where behavior changed in one module while the contract lived in docs and tests elsewhere.",
            visible_context_needed=("ADR/convention document", "caller module", "shared service", "public behavior tests"),
            tempting_wrong_fix=("local caller-only patch", "test-specific branch", "bypass shared service"),
            hidden_contract_sources=("visible ADR", "module README"),
            public_test_signal="Behavioral symptom test; should not reveal the shared-service implementation shape.",
            estimated_fixture_size="large",
            fixture_cost_score=7,
            requires_distributed_context=True,
            has_nearby_tempting_wrong_fix=True,
            hidden_contract_visible=True,
            historical_fix_available=True,
            exposes_private_domain=True,
        ),
        MinedCandidate(
            task_id="real_project_nbo_existing_public_test_patch_001",
            source_project="nbo",
            candidate_type="adr_mismatch",
            title="Obvious public-test patch anti-candidate",
            summary="A documented mismatch where the public test names the exact method and expected replacement, making it a poor differentiator.",
            visible_context_needed=("public test", "single nearby source file"),
            tempting_wrong_fix=("the same one-line fix public tests already reveal",),
            hidden_contract_sources=("visible public test",),
            public_test_signal="Exact method and expected branch are named in the failing assertion.",
            estimated_fixture_size="small",
            fixture_cost_score=2,
            public_tests_reveal_patch=True,
            hidden_contract_visible=True,
        ),
    ]


def sanitized_report_rows(candidates: list[MinedCandidate] | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for candidate in candidates or build_seed_candidates():
        score = score_candidate(candidate)
        row = {
            **score,
            "candidate_name": candidate.title,
            "source_type": candidate.candidate_type,
            "why_it_might_beat_repo_only": candidate.summary,
            "visible_context_needed": list(candidate.visible_context_needed),
            "tempting_wrong_fix": list(candidate.tempting_wrong_fix),
            "privacy_risk": candidate.privacy_notes,
            "estimated_fixture_size": candidate.estimated_fixture_size,
            "selection_recommendation": "implement_next" if score["recommended"] else "do_not_implement_yet",
        }
        _assert_sanitized(row)
        rows.append(row)
    return rows


def render_markdown_report(candidates: list[MinedCandidate] | None = None) -> str:
    rows = sanitized_report_rows(candidates)
    lines = [
        "# Mined Candidate Pre-Screening Report",
        "",
        "Purpose: identify real-project task candidates before implementing full sanitized fixtures.",
        "",
        "Privacy boundary: this report contains only sanitized task shapes and excludes raw history, private remotes, access material, user records, and full business domain details.",
        "",
        "## Larger Sanitized Fixture Mode",
        "",
        "Use this mode when narrow fixtures make the answer obvious:",
        "",
        "- Include enough surrounding modules to make local fixes tempting.",
        "- Place docs or ADR constraints in separate visible locations.",
        "- Include lockfile or dependency notes when pinned-version behavior matters.",
        "- Include two or more plausible edit locations.",
        "- Avoid full app snapshots, private remotes, user records, and raw git history.",
        "- Do not minimize the fixture so much that the only nearby file reveals the answer.",
        "",
        "## Candidates",
    ]
    for row in rows:
        lines.extend(
            [
                "",
                f"### {row['task_id']}",
                "",
                f"Candidate name: {row['candidate_name']}",
                f"Source type: {row['source_type']}",
                f"Why it might beat repo-only: {row['why_it_might_beat_repo_only']}",
                f"Visible context needed: {', '.join(row['visible_context_needed'])}",
                f"Tempting wrong fix: {', '.join(row['tempting_wrong_fix'])}",
                f"Privacy risk: {row['privacy_risk']}",
                f"Estimated fixture size: {row['estimated_fixture_size']}",
                f"Scores: DocAtlas {row['docatlas_relevance_score']}/10, repo-only difficulty {row['repo_only_difficulty_score']}/10, fairness {row['fairness_score']}/10, privacy risk {row['privacy_risk_score']}/10, fixture cost {row['fixture_cost_score']}/10",
                f"Selection recommendation: {row['selection_recommendation']}",
                f"Reason: {row['reason']}",
            ]
        )
    report = "\n".join(lines) + "\n"
    _assert_sanitized(report)
    return report


def write_reports(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = sanitized_report_rows()
    (output_dir / "mined_candidates.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    (output_dir / "mined_candidates.md").write_text(render_markdown_report(), encoding="utf-8")


def _assert_sanitized(value: object) -> None:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    if PRIVATE_TEXT_PATTERNS.search(text):
        raise ValueError("mined candidate report contains private or credential-like text")
