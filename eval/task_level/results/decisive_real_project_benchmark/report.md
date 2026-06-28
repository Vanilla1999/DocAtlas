# Decisive Real-Project Task-Level Benchmark Report

Generated: 2026-06-28T08:20:58Z; updated 2026-06-28T09:08:54Z after `decisive_existing_screening_001`, `decisive_nbo_generated_policy_source_001_screening_001`, and `decisive_nbo_permission_handler_version_001_screening_001`.

## Executive verdict

INCONCLUSIVE

## Direct answer

Can we say DocAtlas is better than asking the agent without it?

Inconclusive, because accepted task pool is still insufficient. Latest strict-offline screening has 1 accepted task, below the required 3 accepted real-project tasks.

## Candidate pool

- total candidates mined: 12
- recommended candidates: 7
- existing fixtures screened in latest existing-fixture run: 5
- newly implemented candidates screened: 2 (`decisive_nbo_generated_policy_source_001`, `decisive_nbo_permission_handler_version_001`)
- accepted candidates after latest screening: 1
- rejected_too_easy after latest screening: 6
- rejected_unfair after latest screening: 0
- needs_redesign / implementation: 5 recommended candidates remain; both newly implemented decisive candidates need redesign before any full pilot

The candidate pool is recorded in:

- `eval/task_level/results/task_selection/decisive_candidate_pool.md`
- `eval/task_level/results/task_selection/decisive_candidate_pool.json`

The latest screening summaries are recorded in:

- `eval/task_level/results/decisive_real_project_benchmark/existing_screening_summary.json`
- `eval/task_level/results/decisive_nbo_generated_policy_source_001_screening_001/screening_summary.json`
- `eval/task_level/results/decisive_nbo_permission_handler_version_001_screening_001/screening_summary.json`
- `eval/task_level/results/decisive_real_project_benchmark/decisive_nbo_permission_handler_version_001_screening_summary.json`

## Accepted tasks

### real_project_nbo_001

- source_project: nbo
- candidate_type: existing real-project fixture
- why DocAtlas-relevant: project docs, pinned dependency, architecture constraint, generated-file constraint, local context
- repo_only screening: `repo_only_strict_offline` resolved 1/2, policy-clean, zero network attempts
- fairness: clean
- privacy: sanitized NBO fixture scope

This is only 1 accepted task. It is not enough to run or interpret the full decisive pilot.

## Rejected too easy

- `real_project_nbo_permission_002`: strict offline resolved 2/2
- `real_project_nbo_generated_source_001`: strict offline resolved 2/2
- `real_project_nbo_distributed_permission_policy_001`: strict offline resolved 2/2
- `real_project_nbo_cross_module_permission_contract_001`: strict offline resolved 2/2
- `decisive_nbo_generated_policy_source_001`: validated, then strict offline resolved 2/2 in `decisive_nbo_generated_policy_source_001_screening_001`; policy clean, artifact integrity clean, fairness clean
- `decisive_nbo_permission_handler_version_001`: validated, then strict offline resolved 2/2 in `decisive_nbo_permission_handler_version_001_screening_001`; policy clean, artifact integrity clean, fairness clean

## Screening

- run_id: `decisive_existing_screening_001`
- expected runs: 10
- completed runs: 10
- artifact integrity: clean (`ok=true`, `runs_jsonl_records=10`)
- condition: `repo_only_strict_offline`
- policy_clean: true for screened summaries
- network_attempts: 0

Additional new-candidate screening:

- run_id: `decisive_nbo_generated_policy_source_001_screening_001`
- expected runs: 2
- completed runs: 2
- artifact integrity: clean (`ok=true`, `runs_jsonl_records=2`)
- result: rejected_too_easy, `repo_only_strict_offline` resolved 2/2

- run_id: `decisive_nbo_permission_handler_version_001_screening_001`
- expected runs: 2
- completed runs: 2
- artifact integrity: clean (`ok=true`, `runs_jsonl_records=2`)
- result: rejected_too_easy, `repo_only_strict_offline` resolved 2/2

## Pilot

pilot not run because:

- accepted tasks: 1
- missing requirement: at least 3 accepted real-project tasks are required before the full 4-condition pilot

## Metrics

No full decisive pilot runs were executed. Therefore the following causal deltas cannot be computed for the decisive pool:

- policy-clean resolved delta
- contract-score delta
- network leakage delta
- token/time overhead
- fallback rate
- DocAtlas call/use rate

## Evidence supporting the verdict

- Baseline task-level test suite passed before this cycle: `108 passed`.
- A decisive candidate pool with 12 sanitized candidates was created.
- Latest existing-fixture strict-offline screening completed 10/10 runs with clean artifact integrity.
- The generated-policy-source candidate validated successfully but screened too easy at 2/2 strict-offline resolved.
- The dependency-trap permission-handler-version candidate validated successfully but screened too easy at 2/2 strict-offline resolved.
- Only 1 task is accepted by strict-offline screening; 6 screened tasks are rejected as too easy.

## Evidence weakening any stronger claim

- Accepted task count is 1, below the required minimum of 3.
- No full 4-condition decisive pilot was run.
- No decisive run-level DocAtlas condition metrics exist for retrieval/use, fallback dominance, or contract-score improvement.
- Four screened existing fixtures and two new decisive candidates remain too easy for repo-only strict offline.

## Claims

Can claim:

- A sanitized decisive candidate pool has been prepared for the next benchmark iteration.
- Latest strict-offline screening evidence found 1 accepted and 6 too-easy tasks.
- The current evidence does not support a positive DocAtlas-over-repo-only claim.
- The correct current benchmark verdict is `INCONCLUSIVE`.

Cannot claim:

- DocAtlas improves coding agents on real patches.
- DocAtlas beats `repo_only_strict_offline`.
- DocAtlas beats Context7.
- DocAtlas vector retrieval is robust for this benchmark.
- The decisive real-project benchmark has completed a causal 4-condition pilot.
