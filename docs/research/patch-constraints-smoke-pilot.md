# Patch constraints smoke pilot

Date: 2026-06-28
Run IDs: `patch_constraints_smoke_001`, `patch_constraints_smoke_001_single`

## Scope

A small targeted pilot was attempted after telemetry, constraint packet generation, and constraint validation were added.

Requested conditions:

- `repo_only_strict_offline`
- `docatlas_action_checklist_injected`
- `docatlas_patch_constraints_injected`

Primary task used for comparable completed rows:

- `real_project_nbo_001`

A second task, `decisive_nbo_cross_module_gate_large_001`, was started in `patch_constraints_smoke_001`, but the command hit the 600 second supervisor timeout before the 6-run matrix completed. Raw trajectories are not committed as evidence; this report records only the completed comparable rows and the timeout limitation.

## Command attempted

```bash
uv run python -m eval.task_level.runner \
  --execute \
  --runner codex \
  --model gpt-5.5 \
  --tasks real_project_nbo_001 decisive_nbo_cross_module_gate_large_001 \
  --conditions repo_only_strict_offline docatlas_action_checklist_injected docatlas_patch_constraints_injected \
  --repeats 1 \
  --run-id patch_constraints_smoke_001 \
  --timeout-seconds 600
```

A one-task retry also timed out before finishing all conditions, but the original run already contained the three comparable `real_project_nbo_001` rows.

## Completed comparable rows from `patch_constraints_smoke_001`

| task | condition | resolved | hidden pass | policy clean | input tokens | output tokens | wall time seconds | constraint packet tokens | constraint used | constraint violations after patch | fallback used |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| real_project_nbo_001 | repo_only_strict_offline | false | true | true | 175054 | 2802 | 81.1241 | null | false | 0 | false |
| real_project_nbo_001 | docatlas_action_checklist_injected | false | true | true | 181888 | 3119 | 77.0836 | null | false | 0 | true |
| real_project_nbo_001 | docatlas_patch_constraints_injected | false | true | true | 239328 | 4008 | 105.4822 | 1138 | true | 0 | true |

## Findings

- Quality: no condition resolved `real_project_nbo_001`; hidden tests passed but public/compile gate did not resolve.
- Cost: patch constraints were the most expensive completed condition in input tokens and wall time.
- Token overhead: `docatlas_patch_constraints_injected` added a 1138-token packet and used 239328 input tokens versus 175054 for strict offline.
- Retrieval/fallback: both DocAtlas injected conditions used `fallback_local_project_context`; this is not vector retrieval success.
- Constraint usefulness: constraint usage was detected for the patch-constraints condition and validation reported zero violations, but this did not translate into task resolution.

## Limitation

The pilot is a smoke/regression signal only. It is incomplete for the two-task matrix because Codex runs exceeded the supervisor timeout. It does not support a positive production claim.

## Interpretation

Patch constraints are technically injectable, bounded, source-attributed, persisted as artifacts, and measurable after patch. The smoke result supports keeping the prototype in benchmark/eval while gathering stronger evidence. It does not support productionizing broadly yet.
