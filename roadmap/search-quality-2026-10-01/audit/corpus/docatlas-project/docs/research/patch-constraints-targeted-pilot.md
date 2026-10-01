# Patch constraints targeted pilot

## Status

Exploratory targeted pilot.
Not broad superiority evidence.

This memo describes the targeted evidence PR for the DocAtlas patch-constraints workflow now that `get_patch_constraints` and `validate_patch_against_constraints` are available in production. It is a protocol and harness checkpoint, not a claim that DocAtlas broadly improves coding agents.

## Commit / branch / run IDs

Branch: `test/patch-constraints-targeted-pilot`

Base branch: `main`

Base commit at branch creation:

```text
5a22bec Research/task level agent benchmark (#9)
```

Dry-run planning artifact produced locally:

```text
eval/task_level/results/patch_constraints_targeted_pilot_dry_run_003/
```

The dry-run is non-causal: it launches no coding agent and should not be interpreted as benchmark outcome evidence.

## Question

Does DocAtlas patch-constraints workflow reduce high-confidence deterministic project-rule violations compared with `repo_only_strict_offline`?

## Hypothesis

Primary:

- fewer high-confidence deterministic constraint violations after patch.

Secondary:

- no material regression in public/hidden pass;
- bounded token/time overhead;
- useful manual-review unknowns;
- no hidden/oracle leakage.

## Conditions

- `repo_only_strict_offline`
- `docatlas_patch_constraints_workflow`
- `docatlas_patch_constraints_injected`

The workflow condition is intentionally narrow. It models agent-side use of the DocAtlas patch-constraints workflow rather than broad docs retrieval superiority.

The injected condition is included as a harness-side control to isolate compact constraint-packet quality from agent tool-use discipline. It is not the primary product workflow claim.

## Task selection

Selection rule:

- `selection_status == "accepted"`
- `differentiating == true`

Current accepted/differentiating subset in `main`:

| task_id | task class | accepted/differentiating | visible source coverage | expected constraint types | public/hidden separation |
| --- | --- | --- | --- | --- | --- |
| `decisive_docmancer_vector_timeout_fallback_001` | architecture/layer boundary | yes | yes | architecture, dependency_version, source_of_truth | hidden tests/oracles stay eval-harness-only |
| `decisive_nbo_cross_module_gate_large_001` | source-of-truth ownership / cross-module policy | yes | yes | architecture, source_of_truth, dependency_version, forbidden_edit, generated_file | hidden tests/oracles stay eval-harness-only |

Limitation: only 2 accepted/differentiating tasks are currently available, below the desired 8–12 task target. Rejected-too-easy/smoke tasks remain useful for regression but should not be used as proof-of-value tasks.

## Protocol

1. Compile constraints before editing, either by agent-side workflow use or by harness-side injected packet condition.
2. Inject compact constraint packet only for the injected condition.
3. Agent edits code.
4. Collect `changed_files` and `patch_diff`.
5. Validate patch against constraints.
6. Allow exactly one repair pass on deterministic violations.
7. Run public tests.
8. Run hidden tests only in eval harness.
9. Persist artifacts.

Required per-run artifacts where feasible:

- `constraints.json`
- `constraints.md`
- `validation.json`
- `changed_files.json`
- `patch.diff`
- `result.json`

Existing compatibility artifact names may also be written:

- `patch_constraints.json`
- `patch_constraints.md`
- `patch_constraints_injection.json`

## Metrics

| task_id | condition | repeat | resolved | public_tests_pass | hidden_tests_pass | policy_clean | constraint_violations_after_patch | violation_types | unknown_count | manual_review_required | constraint_used | constraint_packet_tokens | input_tokens | output_tokens | wall_time_seconds | fallback_used |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pending | pending | pending | pending | pending | pending | pending | pending | pending | pending | pending | pending | pending | pending | pending | pending | pending |

## Results

No causal benchmark result is claimed in this PR.

The local dry-run verified that the harness can build a targeted pilot plan for the accepted task subset and persist a non-causal artifact contract. It did not launch coding agents, generate patches, run hidden tests, or compare outcomes.

## Interpretation

The current state supports a constrained next step:

- the repo has a targeted two-condition protocol;
- the harness can select accepted/differentiating tasks;
- the workflow condition is explicit and separate from generic DocAtlas context injection;
- artifact expectations are machine-checkable.

It does not show whether the workflow reduces violations or improves outcomes.

## Limitations

- small sample size;
- stochastic agent behavior;
- task selection bias;
- prompt-shape confounds;
- fallback confounds;
- token/time overhead;
- hidden/public separation risk;
- validator false positives;
- unknown/manual-review noise;
- only 2 accepted/differentiating tasks currently available;
- dry-run artifacts are protocol evidence only, not outcome evidence.

## Decision

Continue.

Next step: run the targeted pilot with a verified independent runner on the accepted subset, then expand the accepted task pool before making any outcome claim.

## Allowed claims

- DocAtlas supports a deterministic two-step constraint workflow.
- The targeted pilot harness can compare `repo_only_strict_offline` with `docatlas_patch_constraints_workflow`.
- The pilot protocol tracks deterministic project-rule violations and manual-review unknowns.

## Claims still avoided

- No broad superiority.
- No correctness proof.
- No replacement for tests.
- No “beats repo-only”.
- No “beats Context7”.
- No causal interpretation from `constraint_used` alone.
