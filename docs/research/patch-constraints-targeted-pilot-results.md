# Patch constraints targeted pilot results

## Status

Exploratory targeted pilot execution attempt.
Not broad superiority evidence.

This result memo records a verified partial run: the harness executed the targeted pilot matrix and persisted per-run blocked artifacts, but no coding-agent patches were generated because the available independent runners were not usable for causal patch runs in this environment.

## Branch / commit / run IDs

Branch:

```text
test/execute-patch-constraints-targeted-pilot
```

Base:

```text
main @ 5a22bec Research/task level agent benchmark (#9)
```

Prerequisite harness commits were cherry-picked because the local `main` did not yet contain the prior targeted-pilot branch:

```text
31136db test/eval: add patch constraints targeted pilot harness
8284c23 docs/research: add patch constraints targeted pilot memo
5739d8f test/eval: split patch constraints workflow and injection pilots
```

Run IDs:

```text
patch_constraints_runner_canary_001
patch_constraints_targeted_pilot_opencode_blocked_003
```

## Question

Does DocAtlas patch-constraints workflow reduce deterministic project-rule violations compared with `repo_only_strict_offline`?

## Conditions

- `repo_only_strict_offline`
- `docatlas_patch_constraints_workflow`
- `docatlas_patch_constraints_injected`

Interpretation:

- workflow = product workflow / agent-side guidance;
- injected = eval control for compact packet quality;
- repo_only = strict offline baseline.

## Task pool

Accepted/differentiating tasks found in the current manifest:

| task_id | class | visible source coverage | status |
| --- | --- | --- | --- |
| `decisive_docmancer_vector_timeout_fallback_001` | architecture/layer boundary / benchmark accounting | yes | selected |
| `decisive_nbo_cross_module_gate_large_001` | cross-module source-of-truth ownership | yes | selected |

No additional tasks were promoted in this PR. Existing NBO smoke/rejected-too-easy tasks have useful regression coverage but are not accepted/differentiating evidence without fresh fair screening.

## Protocol

Command attempted:

```bash
uv run python -m eval.task_level.runner --patch-constraints-targeted-pilot --repeats 1 --run-id patch_constraints_targeted_pilot_opencode_blocked_003 --runner opencode --timeout-seconds 120
```

Runner verification probe:

```bash
uv run python -m eval.task_level.runner --verify-runner --runner claude --model sonnet --timeout-seconds 120 --run-id patch_constraints_runner_canary_001
```

Observed runner state:

- Claude Code CLI exists but canary failed before patch generation with `Not logged in · Please run /login`.
- OpenCode CLI exists but the harness adapter intentionally raises `NotImplementedError` until strict tool/MCP isolation is verified.
- The targeted pilot matrix therefore completed as blocked rows, not causal patch rows.

## Results table

| task_id | condition | repeat | status | resolved | public_tests_pass | hidden_tests_pass | policy_clean | constraint_violations_after_patch | unknown_count | constraint_used | constraint_packet_tokens |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `decisive_docmancer_vector_timeout_fallback_001` | `repo_only_strict_offline` | 0 | runner_unavailable | false | false | false | true | 0 | 0 | false | n/a |
| `decisive_docmancer_vector_timeout_fallback_001` | `docatlas_patch_constraints_workflow` | 0 | runner_unavailable | false | false | false | true | 0 | 0 | false | n/a |
| `decisive_docmancer_vector_timeout_fallback_001` | `docatlas_patch_constraints_injected` | 0 | runner_unavailable | false | false | false | true | 0 | 0 | false | n/a |
| `decisive_nbo_cross_module_gate_large_001` | `repo_only_strict_offline` | 0 | runner_unavailable | false | false | false | true | 0 | 0 | false | n/a |
| `decisive_nbo_cross_module_gate_large_001` | `docatlas_patch_constraints_workflow` | 0 | runner_unavailable | false | false | false | true | 0 | 0 | false | n/a |
| `decisive_nbo_cross_module_gate_large_001` | `docatlas_patch_constraints_injected` | 0 | runner_unavailable | false | false | false | true | 0 | 0 | false | n/a |

Artifact integrity:

```text
expected_total_runs=6
runs_jsonl_records=6
artifact_integrity.ok=true
```

## Pairwise comparison

Workflow vs repo_only:

```text
pairs=2
resolved_delta_mean=0.0
constraint_violation_delta_median=0.0
```

Injected vs repo_only:

```text
pairs=2
resolved_delta_mean=0.0
constraint_violation_delta_median=0.0
```

These deltas are not outcome evidence because every paired row is `runner_unavailable` and no patch was generated.

## Violation analysis

No deterministic project-rule violations were observed because no patch was generated.

This is a blocked-run result, not evidence that any condition avoids violations.

## Cost analysis

Token counts and wall-time metrics are not meaningful for the blocked pilot:

- `input_tokens`: null
- `output_tokens`: null
- `constraint_packet_tokens`: null
- `wall_time_seconds`: 0.0 in blocked rows

## Unknown/manual-review analysis

`unknown_count=0` in blocked rows because validation had no constraints or patch to inspect.

This does not imply low manual-review burden; it means the validator did not run on a real patch.

## What this supports

- The targeted pilot command now runs to completion even when a runner is unavailable.
- Blocked runner rows persist `runs.jsonl`, `result.json`, `patch.diff`, `changed_files.json`, and `validation.json` artifacts instead of crashing the harness.
- Artifact integrity can distinguish completed blocked matrices from causal patch results.
- The current environment is not ready for a causal patch pilot until an independent runner is authenticated and verified.

## What this does not support

- It does not show that DocAtlas reduces project-rule violations.
- It does not show that DocAtlas improves resolved/public/hidden pass rates.
- It does not show that DocAtlas beats repo-only or Context7.
- It does not prove correctness.
- It does not replace tests.

## Limitations

- No coding-agent patch was generated.
- Claude Code was present but unauthenticated in the isolated canary run.
- OpenCode adapter is deliberately non-causal until strict tool isolation is verified.
- Only 2 accepted/differentiating tasks are available in the manifest.
- No new accepted NBO tasks were added because existing rejected-too-easy NBO fixtures require fresh fair screening before promotion.
- The pilot remains blocked on verified runner availability, not on constraint workflow logic.

## Decision

Pause causal interpretation.

Continue only after authenticating/verifying an independent runner or adding a supported runner adapter with strict tool/MCP isolation.

## Next PR recommendation

`test/eval: verify independent runner for patch-constraints pilot`
