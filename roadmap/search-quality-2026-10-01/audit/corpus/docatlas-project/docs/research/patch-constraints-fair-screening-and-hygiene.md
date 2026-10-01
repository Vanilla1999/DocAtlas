# Patch constraints fair screening and artifact hygiene

## Context

PR #10 proved the targeted patch-constraints harness can execute non-dry-run rows with OpenCode.

It established:

- runner can execute patch tasks;
- artifacts persist for every task/condition row;
- policy isolation can be audited from normalized trajectories;
- DocAtlas tools can be visible and called from a DocAtlas condition.

## What PR #10 did and did not show

PR #10 showed:

- OpenCode can run under the task-level harness;
- per-run MCP config isolation can expose no MCP servers for repo-only and only `docmancer-docs` for DocAtlas conditions;
- `trajectory.normalized.json` can support policy audit;
- a six-row targeted pilot can complete and persist artifacts.

PR #10 did not show:

- DocAtlas outcome improvement;
- correctness improvement;
- broad superiority;
- task-pool sufficiency;
- that `constraint_used` is causal.

## Problem

The next bottlenecks are:

- the accepted/differentiating task pool is tiny;
- runtime/cache artifacts can pollute `changed_files` and patch metrics;
- screening semantics were too coarse for research workflow.

Runtime/cache noise is especially risky for patch-constraints evaluation because generated-file violations are a primary task class. The harness must filter cache noise without hiding real generated/protected path edits.

## Artifact hygiene

The harness now records both raw audit artifacts and normalized evaluation artifacts:

- `patch.raw.diff` — full raw `git diff --binary --no-ext-diff` output;
- `patch.diff` — normalized diff with runtime/cache file sections removed when feasible;
- `git_status.raw.txt` — raw `git status --porcelain`;
- `git_status.txt` — normalized status without ignored runtime/cache paths;
- `changed_files.raw.json` — raw `git diff --name-only` paths;
- `changed_files.json` — normalized changed files used by metrics and validation;
- `ignored_runtime_artifacts.json` — ignored runtime/cache paths;
- `patch_hygiene.json` — raw/filtered counts, preserved generated candidates, warnings.

Ignored runtime/cache artifacts include:

- `__pycache__/`;
- `*.pyc`;
- `*.pyo`;
- `.pytest_cache/`;
- `.mypy_cache/`;
- `.ruff_cache/`;
- `.coverage`;
- `coverage.xml`;
- `htmlcov/`;
- `.hypothesis/`;
- `.tox/`;
- `.nox/`;
- `.DS_Store`.

Preserved generated/lockfile candidates include:

- `*.g.dart`;
- `*.freezed.dart`;
- `*.pb.go`;
- `*.pb.dart`;
- paths containing `.generated.`;
- `generated/` paths;
- `dist/` paths;
- `pubspec.lock`;
- `poetry.lock`;
- `uv.lock`;
- `package-lock.json`;
- `pnpm-lock.yaml`;
- `yarn.lock`;
- `Cargo.lock`;
- `go.sum`.

Normalized `changed_files.json` is the input for patch metrics and patch-constraint validation. Raw artifacts remain beside it for auditability.

## Fair screening

Screening status values:

- `candidate`;
- `accepted_differentiating`;
- `rejected_too_easy`;
- `rejected_too_hard`;
- `rejected_invalid`;
- `rejected_hidden_only`;
- `rejected_insufficient_visible_source`;
- `rejected_no_constraint_angle`;
- `needs_manual_review`.

Suggested task classes:

- `generated_file_trap`;
- `lockfile_dependency_trap`;
- `provider_ui_policy_leakage`;
- `source_of_truth_ownership`;
- `architecture_layer_boundary`;
- `verification_required`;
- `cross_module_policy`;
- `dependency_version_contract`;
- `benchmark_accounting`;
- `other`.

A task can be `accepted_differentiating` only when:

- visible source coverage exists;
- success is not hidden/oracle-only;
- fairness and policy checks are clean;
- repo-only did not resolve the screening repeats;
- a visible constraint angle is stated;
- the task is not smoke/prototype;
- public/hidden separation is stable;
- fixture/setup/test commands are valid;
- the task class is known.

Rejection rules:

- repo-only solved all repeats => `rejected_too_easy`;
- success depends on hidden/oracle-only information => `rejected_hidden_only`;
- visible docs/source do not contain the needed contract => `rejected_insufficient_visible_source`;
- no plausible constraint angle => `rejected_no_constraint_angle`;
- fixture/test/fairness/policy setup is not clean => `rejected_invalid`;
- mixed repo-only outcomes => `needs_manual_review`.

## Screening artifacts

`--screen-tasks` now writes:

- `screening_results.json`;
- `screening_report.md`;
- `accepted_pool.json`;
- `rejected_pool.json`;
- legacy `screening_summary.json` for compatibility.

`accepted_pool.json` is the frozen input for a future targeted pilot. Targeted pilot can use it through `--accepted-pool <path>`. Without an accepted pool file, targeted pilot keeps the legacy manifest selection behavior.

## Research discipline

- Do not promote tasks based on DocAtlas success.
- Do not promote hidden/oracle-only tasks.
- Do not promote rejected-too-easy smoke fixtures just to increase pool size.
- Do not make broad superiority claims from tiny or pre-screening samples.
- Preserve raw artifacts even when normalized metrics filter runtime noise.

## Next experiment

1. Run fresh screening first.
2. Freeze `accepted_pool.json`.
3. Rerun the targeted patch-constraints pilot with `--accepted-pool`.
4. Increase repeats above 1 if runner cost/time permits.
5. Interpret any `constraint_used` signal as correlation, not causal proof.
