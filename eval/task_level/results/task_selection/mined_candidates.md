# Mined Candidate Pre-Screening Report

Purpose: identify real-project task candidates before implementing full sanitized fixtures.

Privacy boundary: this report contains only sanitized task shapes and excludes raw history, private remotes, access material, user records, and full business domain details.

## Larger Sanitized Fixture Mode

Use this mode when narrow fixtures make the answer obvious:

- Include enough surrounding modules to make local fixes tempting.
- Place docs or ADR constraints in separate visible locations.
- Include lockfile or dependency notes when pinned-version behavior matters.
- Include two or more plausible edit locations.
- Avoid full app snapshots, private remotes, user records, and raw git history.
- Do not minimize the fixture so much that the only nearby file reveals the answer.

## Candidates

### real_project_nbo_generated_policy_source_001

Candidate name: Generated permission metadata source-of-truth mismatch
Source type: generated_file_trap
Why it might beat repo-only: A generated model output appears to miss a policy flag, but the visible convention says edits must happen in the source model.
Visible context needed: docs/generated-files.md, permission source model, generated model output, architecture notes
Tempting wrong fix: edit generated .freezed.dart output, duplicate metadata in provider, patch only the public test fixture
Privacy risk: Sanitized summary only; no private URLs, sensitive records, or raw history.
Estimated fixture size: medium
Scores: DocAtlas 7/10, repo-only difficulty 8/10, fairness 8/10, privacy risk 1/10, fixture cost 5/10
Selection recommendation: implement_next
Reason: Meets pre-implementation thresholds for a mined real-project candidate.

### real_project_nbo_permission_handler_version_001

Candidate name: Pinned permission-handler API mismatch
Source type: dependency_trap
Why it might beat repo-only: A permission status mapping bug should be fixed against the lockfile-pinned API rather than latest public API memory.
Visible context needed: pubspec.lock, dependency usage notes, permission mapping source, fake status tests
Tempting wrong fix: invent latest-only enum members, change dependency versions, patch platform-specific branch only
Privacy risk: Sanitized summary only; no private URLs, sensitive records, or raw history.
Estimated fixture size: medium-large
Scores: DocAtlas 8/10, repo-only difficulty 8/10, fairness 8/10, privacy risk 1/10, fixture cost 7/10
Selection recommendation: do_not_implement_yet
Reason: fixture cost above 6

### real_project_historical_architecture_contract_001

Candidate name: Historical architecture-sensitive behavior fix
Source type: historical_fix
Why it might beat repo-only: A real fix commit shape where behavior changed in one module while the contract lived in docs and tests elsewhere.
Visible context needed: ADR/convention document, caller module, shared service, public behavior tests
Tempting wrong fix: local caller-only patch, test-specific branch, bypass shared service
Privacy risk: Sanitized summary only; no private URLs, sensitive records, or raw history.
Estimated fixture size: large
Scores: DocAtlas 7/10, repo-only difficulty 7/10, fairness 8/10, privacy risk 6/10, fixture cost 7/10
Selection recommendation: do_not_implement_yet
Reason: privacy risk above 3; fixture cost above 6

### real_project_nbo_existing_public_test_patch_001

Candidate name: Obvious public-test patch anti-candidate
Source type: adr_mismatch
Why it might beat repo-only: A documented mismatch where the public test names the exact method and expected replacement, making it a poor differentiator.
Visible context needed: public test, single nearby source file
Tempting wrong fix: the same one-line fix public tests already reveal
Privacy risk: Sanitized summary only; no private URLs, sensitive records, or raw history.
Estimated fixture size: small
Scores: DocAtlas 1/10, repo-only difficulty 0/10, fairness 8/10, privacy risk 1/10, fixture cost 2/10
Selection recommendation: do_not_implement_yet
Reason: DocAtlas relevance below 7; repo-only difficulty below 7; public tests reveal the likely patch
