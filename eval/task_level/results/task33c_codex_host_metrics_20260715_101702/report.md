# Task-Level Agent Benchmark Report

## Executive result
Directional local evidence only. This summary is not accepted by task33_validation.py and cannot produce a VALID verdict.

## Environment
```json
{
  "evidence_tier": "exploratory",
  "execution_backend": "host_exploratory",
  "model": "gpt-5.3-codex-spark",
  "runner": "codex-cli-oauth"
}
```

## Task table
| task | condition | repeat | status | resolved | public | hidden | behavior | form | project | version | network_attempts | harness_docatlas | agent_docatlas | tokens | wall_time | context_injected | context_used | checklist_items | checklist_used | retrieval_status | fallback | policy_clean | constraint_violations | unknowns | constraint_used | constraint_tokens |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| decisive_nbo_cross_module_gate_large_001 | docatlas_tool_recommended | 0 | completed | False | True | False | 0.0 | 0.0 | 0.0 | None | 0 | 0 | 0 | 409066/9940 | 36.1316 | False | False | 0 | False | None | False | True | 0 | 0 | False | None |
| decisive_nbo_cross_module_gate_large_001 | docatlas_bounded_direct | 0 | condition_setup_failed | False | False | False | n/a | n/a | n/a | n/a | 0 | 1 | 0 | / |  | False | False | 0 | False | success | False | False |  |  | False |  |
| decisive_nbo_cross_module_gate_large_001 | docatlas_bounded_subagent | 0 | completed | False | True | False | 0.0 | 0.0 | 0.0 | None | 0 | 1 | 0 | 422485/9966 | 40.3281 | True | True | 0 | False | success | False | True | 0 | 0 | False | None |
| decisive_nbo_cross_module_gate_large_001 | repo_only_strict_offline | 0 | completed | False | True | False | 0.0 | 0.0 | 0.0 | None | 0 | 0 | 0 | 344625/6862 | 44.513 | False | False | 0 | False | None | False | True | 0 | 0 | False | None |

## Evaluation execution
| task | condition | setup_phase | setup_status | setup_rc | public_status | public_rc | hidden_status | hidden_rc | compile_gate | contract |
|---|---|---|---|---:|---|---:|---|---:|---|---|
| decisive_nbo_cross_module_gate_large_001 | docatlas_tool_recommended | pre_runner | success | 0 | executed | 0 | executed | 1 | not_applicable | valid |
| decisive_nbo_cross_module_gate_large_001 | docatlas_bounded_direct | pre_runner | success | 0 | not_run | None | not_run | None | not_run |  |
| decisive_nbo_cross_module_gate_large_001 | docatlas_bounded_subagent | pre_runner | success | 0 | executed | 0 | executed | 1 | not_applicable | valid |
| decisive_nbo_cross_module_gate_large_001 | repo_only_strict_offline | pre_runner | success | 0 | executed | 0 | executed | 1 | not_applicable | valid |

## Artifact integrity
```json
{
  "expected_total_runs": 4,
  "finished": true,
  "in_memory_results": 4,
  "ok": true,
  "reason": null,
  "runs_jsonl_records": 4
}
```

## Condition results
- `docatlas_bounded_direct`: resolved=0/1 (0.0%), median_time=n/a
- `docatlas_bounded_subagent`: resolved=0/1 (0.0%), median_time=40.3281
- `docatlas_tool_recommended`: resolved=0/1 (0.0%), median_time=36.1316
- `repo_only_strict_offline`: resolved=0/1 (0.0%), median_time=44.513

## Task 33 delivery metrics
| condition | packet_status | packet_tokens | retained_context | parent_tokens | worker_tokens | system_tokens | retrieval_calls | first_edit | total_latency | evidence_fingerprint |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| docatlas_bounded_direct | None | None |  |  |  |  | 1 | None | 0.039553 | 1ea0fabd78cbbbf9a348adcb38812d94c8afac8d5eac323e6807e077eb3fb93e |
| docatlas_bounded_subagent | ok | 1185 | 1185 | 432451 | 23433 | 455884 | 1 | 40.329595 | 50.690906 | 1ea0fabd78cbbbf9a348adcb38812d94c8afac8d5eac323e6807e077eb3fb93e |

## Paired comparison
Pilot report computes paired deltas when each compared condition has matched task/repeat results. Wide intervals must be treated as directional evidence only.

## Context utilization
DocAtlas adoption and utilization are recorded separately for harness-side context injection and agent-side MCP tool calls.
- `docatlas_bounded_direct`: agent_docatlas_calls=0, context_used=0/1
- `docatlas_bounded_subagent`: agent_docatlas_calls=0, context_used=1/1
- `docatlas_tool_recommended`: agent_docatlas_calls=0, context_used=0/1
- `repo_only_strict_offline`: agent_docatlas_calls=0, context_used=0/1

## Failures
One or more exploratory cells were blocked or missing.

## Cold/warm economics
DocAtlas preindex and warm query timing hooks are present; no full preindexed benchmark was executed.

## Claims we can make
The four local lanes provide directional correctness, token, and latency metrics.

## Claims we cannot make
This run cannot establish causal impact or receive a VALID Task 33C verdict.

## Next experiment
Run 8 tasks x 4 conditions x 2 repeats with a verified headless runner and isolated storage.

## Final decision
INCONCLUSIVE
