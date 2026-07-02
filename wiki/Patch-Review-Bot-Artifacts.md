# Patch-review bot artifact contract

Status: public-ish contract for PR-bot and automation consumers of `docmancer patch-review` output.

DocAtlas patch-review artifacts are advisory review context. They help bots attach useful comments, warnings, and trace links, but they do not prove correctness, replace tests or human review, or decide whether a PR is safe to merge. A separate policy layer must own any hard gate semantics.

## Consumer entrypoint

Start from `review_summary_manifest.json`, not from `review_summary.md`.

The manifest is the artifact discovery contract. Consumers should select entries by `filename`, `kind`, and `schema_version`, then read the referenced JSON file from the same output directory. Human markdown remains a presentation artifact for reviewers.

If `review_summary_manifest.json` is absent, unreadable, malformed, or has an unsupported `schema_version`, automation must treat the output directory as having no completed patch-review run. Consumers should ignore sibling artifacts such as `review_summary_bot_bundle.json` and `review_summary.md`, then fall back to manual review rather than inferring pass/safe-to-merge from stale, partial, or incompatible files.

After a supported manifest is loaded, consumers should still fail closed if a manifest-referenced bot JSON artifact is missing, unreadable, malformed, or fails the consumer's required contract checks. In that case, do not parse `review_summary.md` to recover automation decisions; fall back to manual review and treat the run as incomplete for bot purposes.

Required manifest fields:

- `schema_version`: manifest schema version.
- `summary_mode`: `compact`, `standard`, or `verbose`.
- `product_role`: currently `non_blocking_pr_review_assistant`.
- `claims_avoided`: claim categories the artifact set intentionally does not make.
- `artifacts[]`: ordered artifact descriptors.

Required `artifacts[]` descriptor fields:

- `filename`: generated artifact name in the patch-review output directory.
- `kind`: stable semantic kind for discovery.
- `schema_version`: integer for versioned JSON artifacts, or `null` for raw/debug/markdown artifacts.
- `intended_consumers`: intended readers such as `human_reviewer`, `pr_bot`, `automation`, or `debugger`.
- `safe_usage`: advisory usage guidance and safety limits.

## Bot-facing artifacts

Current bot-facing JSON artifacts:

- `review_summary_quality.json` (`kind: bot_quality_metadata`) — attachability, summary-health counts, typed signals, unknown triage, and claim guardrails.
- `review_summary_actions.json` (`kind: bot_action_metadata`) — ranked checklist items, violations, evidence links, and claim guardrails.
- `review_summary_pr_comment.json` (`kind: bot_pr_comment_payload`) — render-ready non-blocking PR comment payload, including compact deterministic coverage counts. Render-ready fields may be escaped or truncated; raw evidence remains in raw artifacts and trace metadata.
- `review_summary_trace.json` (`kind: bot_traceability_metadata`) — links rendered recommendations back to `constraints.json`, `validation.json`, and `constraint_coverage.json` for audit/debug.
- `constraint_coverage.json` (`kind: constraint_coverage_metadata`) — machine-readable covered-vs-unknown/manual category counts for PR bots that need warning badges without treating unknowns as pass.
- `review_summary_bot_bundle.json` (`kind: bot_bundle`) — single-file bot integration entrypoint embedding manifest, quality, actions, coverage, PR comment, trace metadata, and advisory integration decisions.

Raw audit/debug artifacts remain separate:

- `constraints.json` is raw extracted constraint evidence, not a verdict.
- `validation.json` preserves satisfied, violated, and unknown validation results. Unknown means manual review, not pass.
- `patch.diff`, `changed_files.json`, `untracked_files.json`, `ignored_runtime_artifacts.json`, and `patch_hygiene.json` are supporting review/debug context.

## Advisory decision semantics

`review_summary_bot_bundle.json.advisory_decision` is for non-blocking integration behavior only.

Stable fields:

- `should_attach_comment`: whether a bot has enough advisory signal to attach a comment.
- `show_warning_badge`: whether violations or manual-review signals deserve warning presentation.
- `highlight_violations`: whether known violations should be emphasized.
- `requires_manual_review`: whether violations or unknowns require human attention.
- `reason_codes`: deterministic reasons such as `violations_present`, `manual_review_required`, `actionable_items_present`, or `no_attachable_review_signal`.
- `coverage_counts`: deterministic coverage counters copied from `constraint_coverage.json` as `{covered, unknown_manual}` for bot badges and routing. A non-zero `unknown_manual` count is a manual-review signal, not a pass signal.
- `unknown_triage_codes`: granular unknown categories copied from `review_summary_quality.json.unknown_triage[]`, such as `missing_diff_evidence`, `missing_test_evidence`, `manual_review_required`, or `low_risk_unknown`; these help route human review and must not be treated as pass. Each `unknown_triage[].examples[]` entry includes the validation `constraint_id`/`reason` plus source constraint context (`source`, `instruction`, `evidence`, and `confidence` when present) so bots can route manual-review hints without parsing markdown.
- `unknown_triage_counts`: granular unknown counts keyed by the same codes as `unknown_triage_codes`, copied from `review_summary_quality.json.unknown_triage[].count` so bots can show warning/manual-review badges without flattening all unknowns into one opaque count. This field is additive in bot bundle schema v3; consumers reading an older v3 bundle where it is absent should reconstruct counts from `quality.unknown_triage[]` when available, otherwise fall back to manual review rather than treating unknowns as pass.
- `semantics`: currently `advisory_non_blocking_only`.
- `claims_avoided`: includes `safe_to_merge`, `correctness_proof`, and `test_or_human_review_replacement`.

Forbidden bot-consumer assumptions:

- Do not infer `safe_to_merge`; this field is intentionally absent.
- Do not treat missing violations as a pass. Unknown/manual-review signals remain non-pass signals.
- Do not turn `requires_manual_review=false` into a merge gate decision.
- Do not parse `review_summary.md` to recover automation decisions; use JSON artifacts.
- Do not drop raw `constraints.json` or `validation.json` when audit/debug evidence is needed.

## Schema version policy

Schema versions are centralized in `PATCH_REVIEW_SCHEMA_VERSIONS` in `docmancer/docs/application/patch_review_service.py`. A required-field removal, type change, or meaning change should bump the affected artifact schema version and update contract tests. Additive fields may keep the current version when existing consumers can ignore them safely.

Bot integrations should reject unknown major/required schema expectations conservatively and fall back to manual review rather than reading sibling artifacts or treating the result as pass.
