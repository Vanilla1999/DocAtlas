# Decisive Real-Project Task-Level Benchmark Report

Generated: 2026-06-28T09:50:10Z; final analysis after `decisive_full_pilot_001`.

## Executive verdict

NEGATIVE_SIGNAL

Confidence: low.

## Direct answer

Can we say DocAtlas is better than asking the agent without it?

No. In the decisive low-confidence pilot, DocAtlas conditions did not outperform repo-only baselines on resolved rate or contract scores.

## Candidate pool

- total candidates mined: 12
- recommended candidates: 7
- implemented new decisive candidates: 5
- accepted tasks: 3
- rejected_too_easy tasks in decisive cycle: 7
- rejected_unfair: 0

Accepted tasks used in the full pilot:

1. `real_project_nbo_001`
2. `decisive_docmancer_vector_timeout_fallback_001`
3. `decisive_nbo_cross_module_gate_large_001`

Caveat: `decisive_docmancer_vector_timeout_fallback_001` is self-referential to Docmancer. It can count as cautious workflow/regression evidence, but not as external proof by itself.

Rejected too easy:

- `real_project_nbo_permission_002`: strict offline resolved 2/2
- `real_project_nbo_generated_source_001`: strict offline resolved 2/2
- `real_project_nbo_distributed_permission_policy_001`: strict offline resolved 2/2
- `real_project_nbo_cross_module_permission_contract_001`: strict offline resolved 2/2
- `decisive_nbo_generated_policy_source_001`: strict offline resolved 2/2
- `decisive_nbo_permission_handler_version_001`: strict offline resolved 2/2
- `decisive_nbo_browser_scan_policy_001`: strict offline resolved 2/2

## Pilot result

- run_id: `decisive_full_pilot_001`
- shape: 3 accepted tasks x 4 conditions x 1 repeat
- expected runs: 12
- completed runs: 12
- confidence: low because repeats=1
- artifact integrity: clean (`ok=true`, `runs_jsonl_records=12`)
- policy clean: 12/12
- network attempts: 0

Condition results:

| condition | resolved | policy clean | context/docatlas use | median wall time |
|---|---:|---:|---:|---:|
| `repo_only_strict_offline` | 0/3 | 3/3 | 0/3 | 86.3027s |
| `repo_only_web_audited` | 0/3 | 3/3 | 0/3 | 85.6566s |
| `docatlas_tool_recommended` | 0/3 | 3/3 | 3/3 context used, 12 agent DocAtlas calls | 125.6484s |
| `docatlas_action_checklist_injected` | 0/3 | 3/3 | 3/3 context used, checklist used 2/3 | 87.9849s |

Per-task outcome summary:

- `real_project_nbo_001`: no condition resolved; all conditions had the same contract-score shape in the report.
- `decisive_docmancer_vector_timeout_fallback_001`: no condition resolved; public passed and hidden failed in every condition.
- `decisive_nbo_cross_module_gate_large_001`: no condition resolved; public passed and hidden failed in every condition.

## Evidence

What supports the verdict:

- The accepted-task gate was finally reached: 3 accepted tasks.
- The full low-confidence pilot completed all 12 expected runs.
- Artifact integrity was clean.
- Policy audit was clean in every run.
- DocAtlas was actually used/adopted in the DocAtlas conditions:
  - `docatlas_tool_recommended`: 12 agent DocAtlas calls, context used 3/3.
  - `docatlas_action_checklist_injected`: context used 3/3.
- Despite that, DocAtlas conditions resolved 0/3, identical to repo-only baselines.
- DocAtlas conditions did not improve contract scores on at least 2 accepted tasks.
- Tool-recommended DocAtlas had substantially higher median wall time and token volume than `repo_only_strict_offline` without correctness gain.

What weakens confidence:

- Repeats=1, so this is a low-confidence pilot, not a statistically strong benchmark.
- One accepted task is self-referential to Docmancer and should not be treated as external product proof alone.
- `docatlas_action_checklist_injected` had one fallback-local-project-context path, so this does not prove robust vector retrieval.
- All conditions resolved 0/3, so the result is a negative signal for this pilot, not a broad universal claim about every possible task.

## Claims

Can claim:

- A 3-task x 4-condition x 1-repeat decisive pilot completed.
- The pilot had clean artifact integrity and clean policy audit.
- DocAtlas context/tool use occurred in the DocAtlas conditions.
- In this low-confidence pilot, DocAtlas did not improve resolved rate over repo-only.
- Current benchmark verdict: `NEGATIVE_SIGNAL` with low confidence.

Cannot claim:

- DocAtlas improves coding agents on real patches.
- DocAtlas beats `repo_only_strict_offline`.
- DocAtlas beats Context7.
- DocAtlas vector retrieval is robust.
- This is a statistically strong negative result; the pilot has only one repeat and one self-referential accepted task.
