# Patch constraints targeted pilot results

## Status

Exploratory targeted pilot.
Not broad superiority evidence.

This memo records the first non-dry-run targeted patch-constraints pilot with an OpenCode runner adapter that passed canary verification and DocAtlas tool visibility checks. The pilot produced real agent patches for the current accepted/differentiating two-task subset.

## Branch / commit / run IDs

Branch:

```text
test/execute-patch-constraints-targeted-pilot
```

Base:

```text
main @ 5a22bec Research/task level agent benchmark (#9)
```

Run IDs:

```text
opencode_canary_supported_002
opencode_docatlas_tool_canary_001
patch_constraints_targeted_pilot_opencode_real_001
```

Runner:

```text
OpenCode 1.17.11
model=openrouter/anthropic/claude-sonnet-4
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

Accepted/differentiating tasks in the current manifest:

| task_id | class | visible source coverage | status |
| --- | --- | --- | --- |
| `decisive_docmancer_vector_timeout_fallback_001` | benchmark-accounting / fallback semantics | yes | selected |
| `decisive_nbo_cross_module_gate_large_001` | cross-module permission-gate contract | yes | selected |

No additional tasks were promoted. Existing NBO smoke/rejected-too-easy fixtures remain smoke/regression only because repo-only solved them during screening.

## Protocol

Runner canary:

```bash
uv run python -m eval.task_level.runner --verify-runner --runner opencode --model openrouter/anthropic/claude-sonnet-4 --timeout-seconds 180 --run-id opencode_canary_supported_002
```

DocAtlas tool visibility canary:

```bash
uv run python -m eval.task_level.runner --verify-docatlas-tool --runner opencode --model openrouter/anthropic/claude-sonnet-4 --timeout-seconds 180 --run-id opencode_docatlas_tool_canary_001
```

Pilot command:

```bash
uv run python -m eval.task_level.runner --patch-constraints-targeted-pilot --repeats 1 --run-id patch_constraints_targeted_pilot_opencode_real_001 --runner opencode --model openrouter/anthropic/claude-sonnet-4 --timeout-seconds 900
```

Artifact integrity:

```text
expected_total_runs=6
runs_jsonl_records=6
artifact_integrity.ok=true
```

## Results table

| condition | runs | resolved | public pass | hidden pass | policy clean | constraint violations total | median unknowns | constraint used rate | median constraint tokens | median wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `repo_only_strict_offline` | 2 | 0 | 2/2 | 0/2 | 2/2 | 0 | 0.0 | 0.0 | n/a | 145.9452s |
| `docatlas_patch_constraints_workflow` | 2 | 0 | 2/2 | 0/2 | 2/2 | 0 | 0.0 | 0.0 | n/a | 177.33545s |
| `docatlas_patch_constraints_injected` | 2 | 0 | 2/2 | 0/2 | 2/2 | 0 | 1.0 | 1.0 | 667.5 | 102.89335s |

Per-task run status:

| task_id | condition | status | resolved | public | hidden | constraint violations | unknowns | constraint_used |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `decisive_docmancer_vector_timeout_fallback_001` | `repo_only_strict_offline` | completed | false | true | false | 0 | 0 | false |
| `decisive_docmancer_vector_timeout_fallback_001` | `docatlas_patch_constraints_workflow` | completed | false | true | false | 0 | 0 | false |
| `decisive_docmancer_vector_timeout_fallback_001` | `docatlas_patch_constraints_injected` | completed | false | true | false | 0 | 1 | true |
| `decisive_nbo_cross_module_gate_large_001` | `repo_only_strict_offline` | completed | false | true | false | 0 | 0 | false |
| `decisive_nbo_cross_module_gate_large_001` | `docatlas_patch_constraints_workflow` | completed | false | true | false | 0 | 0 | false |
| `decisive_nbo_cross_module_gate_large_001` | `docatlas_patch_constraints_injected` | completed | false | true | false | 0 | 1 | true |

## Pairwise comparison

Workflow vs repo_only:

```text
pairs=2
resolved_delta_mean=0.0
hidden_pass_delta_mean=0.0
policy_clean_delta_mean=0.0
constraint_violation_delta_median=0.0
unknown_count_delta_median=0.0
wall_time_delta_median=+31.39025s
```

Injected vs repo_only:

```text
pairs=2
resolved_delta_mean=0.0
hidden_pass_delta_mean=0.0
policy_clean_delta_mean=0.0
constraint_violation_delta_median=0.0
unknown_count_delta_median=+1.0
wall_time_delta_median=-43.05185s
```

These are two-task exploratory paired deltas. They do not justify broad product claims.

## Violation analysis

No deterministic patch-constraint violations were recorded after patch in this run:

```text
repo_only_strict_offline: 0
workflow: 0
injected: 0
```

This does not show a reduction from DocAtlas because the strict repo-only baseline also had zero recorded deterministic violations. All conditions failed hidden tests on both tasks, so the generated patches were incomplete despite passing public tests.

## Cost analysis

Median wall time:

- `repo_only_strict_offline`: 145.9452s
- `docatlas_patch_constraints_workflow`: 177.33545s
- `docatlas_patch_constraints_injected`: 102.89335s

Token metrics are only partially comparable across OpenCode events. The parser captured low/null input token values in some rows, so cost conclusions should stay cautious.

## Unknown/manual-review analysis

- `docatlas_patch_constraints_injected` produced compact packets and marked `constraint_used=true` on both tasks.
- Injected validation had one unknown on each task.
- Workflow rows did not produce harness-side `constraint_used=true`; agent-side DocAtlas calls were observed, but constraint usage remains a correlation signal only.

## What this supports

- OpenCode canary passed and produced a patch under the harness.
- DocAtlas tool visibility canary passed with `docmancer-docs_get_docs_context` observed and no foreign MCP/web calls.
- The targeted pilot can execute non-dry-run rows and persist complete artifacts.
- Policy isolation by per-run OpenCode config plus trajectory audit worked in this run: no Context7/web/foreign MCP calls were recorded.
- The current two-task pilot found no deterministic project-rule violations in any condition, but also no resolved tasks.

## What this does not support

- It does not show DocAtlas reduces violations versus repo-only.
- It does not show DocAtlas improves resolved/public/hidden pass rates.
- It does not show DocAtlas beats repo-only or Context7.
- It does not prove correctness.
- It does not replace tests.
- It does not show that `constraint_used` is causal.

## Limitations

- Only two accepted/differentiating tasks are available.
- One repeat per task/condition.
- All rows pass public tests but fail hidden tests, so patches are incomplete.
- The workflow condition used DocAtlas tools, but the current evaluator does not yet convert agent-side patch-constraints tool behavior into `constraint_used=true` unless the harness injected a packet.
- OpenCode hard shell network isolation is not provided by CLI flags; enforcement is per-run config plus trajectory audit.
- Generated `__pycache__` files appear in changed-file lists for some fixture runs and should be filtered or prevented in a follow-up hygiene PR.

## Decision

Do not claim a positive DocAtlas outcome.

Merge only as an exploratory pilot execution and runner-hardening PR if reviewers accept the small sample and caveats.

## Next PR recommendation

`test/eval: add fair screening and generated-artifact hygiene for patch constraints pilot`

Follow-up design note: `docs/research/patch-constraints-fair-screening-and-hygiene.md`.
