# Task-Level Agent Benchmark Report

## Executive result
Independent causal benchmark not completed in this harness invocation.

## Environment
```json
{
  "benchmark_run_timestamp": "2026-06-28T09:50:10.041968+00:00",
  "branch": "research/task-level-agent-benchmark",
  "context7_mcp_version": "MCP server exposed via current opencode tool schema; exact package version not reported by available tools",
  "docatlas_commit_sha": "b5941c408cba2c578e113acbbefc130b65b845b5",
  "docker_version": "Docker version 29.3.1, build c2be9cc",
  "model_agent_version": "opencode 1.17.11 available; Claude Code 2.1.138 available; cx/gpt-5.5-medium current interactive agent",
  "os": "Linux ViPC 6.17.0-35-generic #35~24.04.1-Ubuntu SMP PREEMPT_DYNAMIC Tue May 26 19:30:42 UTC 2 x86_64 x86_64 x86_64 GNU/Linux",
  "python_version": "Python 3.12.3",
  "runner_detection": {
    "candidates": {
      "Claude Code headless": "/home/viadmin/.local/bin/claude",
      "OpenCode headless": "/home/viadmin/.opencode/bin/opencode",
      "OpenHands": null,
      "SWE-agent": null,
      "mini-SWE-agent": null
    },
    "independent_runner_verified": false,
    "reason": "Generic headless CLIs were found, but SWE-style tool policy isolation and normalized trajectory metrics must be verified before causal runs.",
    "usable": {
      "Claude Code headless": "/home/viadmin/.local/bin/claude",
      "OpenCode headless": "/home/viadmin/.opencode/bin/opencode"
    }
  }
}
```

## Task table
| task | condition | repeat | status | resolved | public | hidden | behavior | form | project | version | network_attempts | harness_docatlas | agent_docatlas | tokens | wall_time | context_injected | context_used | checklist_items | checklist_used | retrieval_status | fallback | policy_clean |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| real_project_nbo_001 | repo_only_strict_offline | 0 | completed | False | False | True | 0.6667 | 1.0 | 1.0 | 1.0 | 0 | 0 | 0 | 206312/3429 | 86.3027 | False | False | 0 | False | None | False | True |
| real_project_nbo_001 | docatlas_action_checklist_injected | 0 | completed | False | False | True | 0.6667 | 1.0 | 1.0 | 1.0 | 0 | 1 | 0 | 282383/4355 | 102.7679 | True | True | 4 | True | fallback_local_project_context | True | True |
| real_project_nbo_001 | docatlas_tool_recommended | 0 | completed | False | False | True | 0.6667 | 1.0 | 1.0 | 1.0 | 0 | 0 | 4 | 607667/6010 | 164.7154 | False | True | 0 | False | None | False | True |
| real_project_nbo_001 | repo_only_web_audited | 0 | completed | False | False | True | 0.6667 | 1.0 | 1.0 | 1.0 | 0 | 0 | 0 | 215110/3437 | 85.6566 | False | False | 0 | False | None | False | True |
| decisive_docmancer_vector_timeout_fallback_001 | repo_only_strict_offline | 0 | completed | False | True | False | 0.0 | 0.0 | 0.0 | None | 0 | 0 | 0 | 124922/2260 | 56.2029 | False | False | 0 | False | None | False | True |
| decisive_docmancer_vector_timeout_fallback_001 | repo_only_web_audited | 0 | completed | False | True | False | 0.0 | 0.0 | 0.0 | None | 0 | 0 | 0 | 123437/2564 | 75.6638 | False | False | 0 | False | None | False | True |
| decisive_docmancer_vector_timeout_fallback_001 | docatlas_action_checklist_injected | 0 | completed | False | True | False | 0.0 | 0.0 | 0.0 | None | 0 | 1 | 0 | 133896/2415 | 60.8221 | True | True | 1 | True | success | False | True |
| decisive_docmancer_vector_timeout_fallback_001 | docatlas_tool_recommended | 0 | completed | False | True | False | 0.0 | 0.0 | 0.0 | None | 0 | 0 | 2 | 184578/2545 | 111.1275 | False | True | 0 | False | None | False | True |
| decisive_nbo_cross_module_gate_large_001 | docatlas_tool_recommended | 0 | completed | False | True | False | 0.0 | 0.0 | 0.0 | None | 0 | 0 | 6 | 267075/4054 | 125.6484 | False | True | 0 | False | None | False | True |
| decisive_nbo_cross_module_gate_large_001 | repo_only_strict_offline | 0 | completed | False | True | False | 0.0 | 0.0 | 0.0 | None | 0 | 0 | 0 | 169988/3685 | 87.1877 | False | False | 0 | False | None | False | True |
| decisive_nbo_cross_module_gate_large_001 | docatlas_action_checklist_injected | 0 | completed | False | True | False | 0.0 | 0.0 | 0.0 | None | 0 | 1 | 0 | 138081/3993 | 87.9849 | True | True | 1 | False | success | False | True |
| decisive_nbo_cross_module_gate_large_001 | repo_only_web_audited | 0 | completed | False | True | False | 0.0 | 0.0 | 0.0 | None | 0 | 0 | 0 | 218441/4631 | 113.1064 | False | False | 0 | False | None | False | True |

## Artifact integrity
```json
{
  "expected_total_runs": 12,
  "finished": true,
  "in_memory_results": 12,
  "ok": true,
  "reason": null,
  "runs_jsonl_records": 12
}
```

## Condition results
- `docatlas_action_checklist_injected`: resolved=0/3 (0.0%), median_time=87.9849
- `docatlas_tool_recommended`: resolved=0/3 (0.0%), median_time=125.6484
- `repo_only_strict_offline`: resolved=0/3 (0.0%), median_time=86.3027
- `repo_only_web_audited`: resolved=0/3 (0.0%), median_time=85.6566

## Paired comparison
Pilot report computes paired deltas when each compared condition has matched task/repeat results. Wide intervals must be treated as directional evidence only.

## Context utilization
DocAtlas adoption and utilization are recorded separately for harness-side context injection and agent-side MCP tool calls.
- `docatlas_action_checklist_injected`: agent_docatlas_calls=0, context_used=3/3
- `docatlas_tool_recommended`: agent_docatlas_calls=12, context_used=3/3
- `repo_only_strict_offline`: agent_docatlas_calls=0, context_used=0/3
- `repo_only_web_audited`: agent_docatlas_calls=0, context_used=0/3

## Failures
No independent agent failures were measured in this run.

## Cold/warm economics
DocAtlas preindex and warm query timing hooks are present; no full preindexed benchmark was executed.

## Claims we can make
The harness and curated pilot manifest are reproducible; current output is not a causal task-level result unless independent runner mode is used.

## Claims we cannot make
Cannot claim DocAtlas improves patch success from harness smoke tests or retrieval scores alone.

## Next experiment
Run 8 tasks x 4 conditions x 2 repeats with a verified headless runner and isolated storage.

## Final decision
ITERATE: harness and task manifest are ready; execute with verified independent runner before product claims.
