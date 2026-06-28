# DocAtlas task-level cost and accuracy analysis

## Verdict

QUALITY_POSITIVE_COSTLY

Direct answer: current artifacts show a limited quality/policy-clean positive signal for DocAtlas-assisted workflows in paired historical pilots, but it is costly in tokens/time and does not establish broad DocAtlas superiority.

## Data analyzed

```json
{
  "accepted_tasks": [
    "decisive_docmancer_vector_timeout_fallback_001",
    "decisive_nbo_cross_module_gate_large_001",
    "real_project_nbo_001"
  ],
  "comparable_pilot_records": 109,
  "conditions": [
    "context7",
    "docatlas_action_checklist_injected",
    "docatlas_context_injected",
    "docatlas_snippet_first",
    "docatlas_tool_optional",
    "docatlas_tool_recommended",
    "docatlas_tool_required_once",
    "repo_only",
    "repo_only_strict_offline",
    "repo_only_web_audited"
  ],
  "pilot_runs": 17,
  "records": 133,
  "run_directories": 56,
  "run_families": {
    "analysis_only": 4,
    "canary": 11,
    "decisive_pilot": 2,
    "pilot": 15,
    "screening": 8,
    "validation": 16
  },
  "screening_runs": 8,
  "smoke_rejected_too_easy_tasks": [
    "real_project_nbo_generated_source_001",
    "real_project_nbo_permission_002"
  ],
  "tasks": [
    "click_group_001",
    "decisive_docmancer_vector_timeout_fallback_001",
    "decisive_nbo_browser_scan_policy_001",
    "decisive_nbo_cross_module_gate_large_001",
    "decisive_nbo_generated_policy_source_001",
    "decisive_nbo_permission_handler_version_001",
    "fastapi_depends_001",
    "mixed_fastapi_project_001",
    "real_project_nbo_001",
    "real_project_nbo_cross_module_permission_contract_001",
    "real_project_nbo_distributed_permission_policy_001",
    "real_project_nbo_generated_source_001",
    "real_project_nbo_permission_002"
  ]
}
```

Validation-only runs were collected for inventory but excluded from condition performance comparisons.

## Accuracy vs cost: all pilot tasks

| condition | resolved_rate | hidden_pass_rate | policy_clean_resolved_rate | median_total_tokens | median_wall_time | tokens_per_policy_clean_resolved |
|---|---|---|---|---|---|---|
| context7 | 0.0000 | 0.0000 | 0.0000 | null | 0.0000 | null |
| docatlas_action_checklist_injected | 0.5625 | 0.6250 | 0.5625 | 173358.5000 | 88.3813 | 366540.8889 |
| docatlas_context_injected | 0.3077 | 0.3077 | 0.3077 | 280552 | 133.1119 | 834722.0000 |
| docatlas_snippet_first | 0.0000 | 0.0000 | 0.0000 | 220468.0000 | 124.1020 | null |
| docatlas_tool_optional | 0.0000 | 0.0000 | 0.0000 | 321774.5000 | 140.6447 | null |
| docatlas_tool_recommended | 0.3684 | 0.5263 | 0.3684 | 354595 | 151.6766 | 996117.4286 |
| docatlas_tool_required_once | 0.1429 | 0.1429 | 0.1429 | 351985.0000 | 145.4866 | 1359116.0000 |
| repo_only | 0.2500 | 0.2917 | 0.2500 | 201610.5000 | 91.1247 | 743535.8333 |
| repo_only_strict_offline | 0.5556 | 0.7778 | 0.5556 | 167079 | 83.6437 | 278554.6000 |
| repo_only_web_audited | 0.6667 | 0.7778 | 0.6667 | 182418 | 75.6638 | 296852.1667 |

## Accuracy vs cost: real-project tasks only

| condition | resolved_rate | hidden_pass_rate | policy_clean_resolved_rate | median_total_tokens | median_wall_time | tokens_per_policy_clean_resolved |
|---|---|---|---|---|---|---|
| docatlas_action_checklist_injected | 0.7000 | 0.8000 | 0.7000 | 207252.5000 | 93.1950 | 304735.4286 |
| docatlas_context_injected | 1.0000 | 1.0000 | 1.0000 | 276222 | 116.7486 | 276222.0000 |
| docatlas_tool_recommended | 0.5000 | 0.8000 | 0.5000 | 335791.0000 | 120.7935 | 662428.8000 |
| repo_only | 0.0000 | 1.0000 | 0.0000 | 268194 | 96.3056 | null |
| repo_only_strict_offline | 0.5556 | 0.7778 | 0.5556 | 167079 | 83.6437 | 278554.6000 |
| repo_only_web_audited | 0.6667 | 0.7778 | 0.6667 | 182418 | 75.6638 | 296852.1667 |

## Accuracy vs cost: smoke/rejected-too-easy tasks

| condition | resolved_rate | hidden_pass_rate | policy_clean_resolved_rate | median_total_tokens | median_wall_time | tokens_per_policy_clean_resolved |
|---|---|---|---|---|---|---|
| docatlas_action_checklist_injected | 1.0000 | 1.0000 | 1.0000 | 160832.5000 | 67.9820 | 171077.5000 |
| docatlas_tool_recommended | 0.7500 | 1.0000 | 0.7500 | 277566.5000 | 114.4136 | 355810.3333 |
| repo_only_strict_offline | 1.0000 | 1.0000 | 1.0000 | 150937.5000 | 76.5814 | 152570.0000 |
| repo_only_web_audited | 1.0000 | 1.0000 | 1.0000 | 160811.0000 | 72.6883 | 165997.2500 |

## Accuracy vs cost: accepted/differentiating tasks

| condition | resolved_rate | hidden_pass_rate | policy_clean_resolved_rate | median_total_tokens | median_wall_time | tokens_per_policy_clean_resolved |
|---|---|---|---|---|---|---|
| docatlas_action_checklist_injected | 0.5000 | 0.6667 | 0.5000 | 275957.0000 | 100.5864 | 482946.0000 |
| docatlas_context_injected | 1.0000 | 1.0000 | 1.0000 | 276222 | 116.7486 | 276222.0000 |
| docatlas_tool_recommended | 0.3333 | 0.6667 | 0.3333 | 353498.0000 | 145.1819 | 1122356.5000 |
| repo_only | 0.0000 | 1.0000 | 0.0000 | 268194 | 96.3056 | null |
| repo_only_strict_offline | 0.2000 | 0.6000 | 0.2000 | 167649 | 86.3027 | 782493.0000 |
| repo_only_web_audited | 0.4000 | 0.6000 | 0.4000 | 218547 | 85.6566 | 558562.0000 |

## Paired deltas

Only same run family/run_id, task_id, and repeat pairs are compared.

```json
{
  "accepted_differentiating_tasks": {
    "docatlas_action_checklist_injected - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": 0.0,
        "generated_file": 0.0,
        "project_convention": 0.0,
        "version": 0.0
      },
      "forbidden_edit_delta_median": 0.0,
      "hidden_pass_delta_mean": 0.0,
      "input_token_delta_median": 76071.0,
      "network_attempt_delta_median": 0.0,
      "output_token_delta_median": 604.0,
      "pairs": 5,
      "policy_clean_delta_mean": 0.2,
      "resolved_delta_mean": 0.2,
      "token_delta_pct": 0.4592750329557588,
      "total_token_delta_median": 76997.0,
      "wall_time_delta_median": 4.619199999999999,
      "wall_time_delta_pct": 0.05352323855452957
    },
    "docatlas_context_injected - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": null,
        "generated_file": null,
        "project_convention": null,
        "version": null
      },
      "forbidden_edit_delta_median": null,
      "hidden_pass_delta_mean": null,
      "input_token_delta_median": null,
      "network_attempt_delta_median": null,
      "output_token_delta_median": null,
      "pairs": 0,
      "policy_clean_delta_mean": null,
      "resolved_delta_mean": null,
      "token_delta_pct": null,
      "total_token_delta_median": null,
      "wall_time_delta_median": null,
      "wall_time_delta_pct": null
    },
    "docatlas_tool_recommended - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": 0.0,
        "generated_file": 0.0,
        "project_convention": 0.0,
        "version": 0.0
      },
      "forbidden_edit_delta_median": 0.0,
      "hidden_pass_delta_mean": 0.0,
      "input_token_delta_median": 150408.0,
      "network_attempt_delta_median": 0.0,
      "output_token_delta_median": 369.0,
      "pairs": 5,
      "policy_clean_delta_mean": 0.0,
      "resolved_delta_mean": 0.0,
      "token_delta_pct": 0.8990748528174937,
      "total_token_delta_median": 150729.0,
      "wall_time_delta_median": 54.9246,
      "wall_time_delta_pct": 0.6364180958417291
    },
    "repo_only_web_audited - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": 0.0,
        "generated_file": 0.0,
        "project_convention": 0.0,
        "version": 0.0
      },
      "forbidden_edit_delta_median": 0.0,
      "hidden_pass_delta_mean": 0.0,
      "input_token_delta_median": 48453.0,
      "network_attempt_delta_median": 0.0,
      "output_token_delta_median": 946.0,
      "pairs": 5,
      "policy_clean_delta_mean": 0.2,
      "resolved_delta_mean": 0.2,
      "token_delta_pct": 0.2946572899331341,
      "total_token_delta_median": 49399.0,
      "wall_time_delta_median": 22.314799999999998,
      "wall_time_delta_pct": 0.25856433228624365
    }
  },
  "all_pilot_tasks": {
    "docatlas_action_checklist_injected - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": 0.0,
        "generated_file": 0.0,
        "project_convention": 0.0,
        "version": 0.0
      },
      "forbidden_edit_delta_median": 0.0,
      "hidden_pass_delta_mean": 0.0,
      "input_token_delta_median": 58560.0,
      "network_attempt_delta_median": 0.0,
      "output_token_delta_median": 424.0,
      "pairs": 9,
      "policy_clean_delta_mean": 0.1111111111111111,
      "resolved_delta_mean": 0.1111111111111111,
      "token_delta_pct": 0.3530306022899347,
      "total_token_delta_median": 58984.0,
      "wall_time_delta_median": 4.619199999999999,
      "wall_time_delta_pct": 0.055224721048925375
    },
    "docatlas_context_injected - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": null,
        "generated_file": null,
        "project_convention": null,
        "version": null
      },
      "forbidden_edit_delta_median": null,
      "hidden_pass_delta_mean": null,
      "input_token_delta_median": null,
      "network_attempt_delta_median": null,
      "output_token_delta_median": null,
      "pairs": 0,
      "policy_clean_delta_mean": null,
      "resolved_delta_mean": null,
      "token_delta_pct": null,
      "total_token_delta_median": null,
      "wall_time_delta_median": null,
      "wall_time_delta_pct": null
    },
    "docatlas_tool_recommended - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": 0.0,
        "generated_file": 0.0,
        "project_convention": 0.0,
        "version": 0.0
      },
      "forbidden_edit_delta_median": 0.0,
      "hidden_pass_delta_mean": 0.0,
      "input_token_delta_median": 150408.0,
      "network_attempt_delta_median": 0.0,
      "output_token_delta_median": 369.0,
      "pairs": 9,
      "policy_clean_delta_mean": -0.1111111111111111,
      "resolved_delta_mean": -0.1111111111111111,
      "token_delta_pct": 0.9021421004435027,
      "total_token_delta_median": 150729.0,
      "wall_time_delta_median": 54.9246,
      "wall_time_delta_pct": 0.6566495743253825
    },
    "repo_only_web_audited - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": 0.0,
        "generated_file": 0.0,
        "project_convention": 0.0,
        "version": 0.0
      },
      "forbidden_edit_delta_median": 0.0,
      "hidden_pass_delta_mean": 0.0,
      "input_token_delta_median": 45648.0,
      "network_attempt_delta_median": 0.0,
      "output_token_delta_median": 946.0,
      "pairs": 9,
      "policy_clean_delta_mean": 0.1111111111111111,
      "resolved_delta_mean": 0.1111111111111111,
      "token_delta_pct": 0.2810526756803668,
      "total_token_delta_median": 46958.0,
      "wall_time_delta_median": 19.460899999999995,
      "wall_time_delta_pct": 0.23266426521064942
    }
  },
  "real_project_tasks_only": {
    "docatlas_action_checklist_injected - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": 0.0,
        "generated_file": 0.0,
        "project_convention": 0.0,
        "version": 0.0
      },
      "forbidden_edit_delta_median": 0.0,
      "hidden_pass_delta_mean": 0.0,
      "input_token_delta_median": 58560.0,
      "network_attempt_delta_median": 0.0,
      "output_token_delta_median": 424.0,
      "pairs": 9,
      "policy_clean_delta_mean": 0.1111111111111111,
      "resolved_delta_mean": 0.1111111111111111,
      "token_delta_pct": 0.3530306022899347,
      "total_token_delta_median": 58984.0,
      "wall_time_delta_median": 4.619199999999999,
      "wall_time_delta_pct": 0.055224721048925375
    },
    "docatlas_context_injected - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": null,
        "generated_file": null,
        "project_convention": null,
        "version": null
      },
      "forbidden_edit_delta_median": null,
      "hidden_pass_delta_mean": null,
      "input_token_delta_median": null,
      "network_attempt_delta_median": null,
      "output_token_delta_median": null,
      "pairs": 0,
      "policy_clean_delta_mean": null,
      "resolved_delta_mean": null,
      "token_delta_pct": null,
      "total_token_delta_median": null,
      "wall_time_delta_median": null,
      "wall_time_delta_pct": null
    },
    "docatlas_tool_recommended - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": 0.0,
        "generated_file": 0.0,
        "project_convention": 0.0,
        "version": 0.0
      },
      "forbidden_edit_delta_median": 0.0,
      "hidden_pass_delta_mean": 0.0,
      "input_token_delta_median": 150408.0,
      "network_attempt_delta_median": 0.0,
      "output_token_delta_median": 369.0,
      "pairs": 9,
      "policy_clean_delta_mean": -0.1111111111111111,
      "resolved_delta_mean": -0.1111111111111111,
      "token_delta_pct": 0.9021421004435027,
      "total_token_delta_median": 150729.0,
      "wall_time_delta_median": 54.9246,
      "wall_time_delta_pct": 0.6566495743253825
    },
    "repo_only_web_audited - repo_only_strict_offline": {
      "contract_score_delta": {
        "behavioral": 0.0,
        "generated_file": 0.0,
        "project_convention": 0.0,
        "version": 0.0
      },
      "forbidden_edit_delta_median": 0.0,
      "hidden_pass_delta_mean": 0.0,
      "input_token_delta_median": 45648.0,
      "network_attempt_delta_median": 0.0,
      "output_token_delta_median": 946.0,
      "pairs": 9,
      "policy_clean_delta_mean": 0.1111111111111111,
      "resolved_delta_mean": 0.1111111111111111,
      "token_delta_pct": 0.2810526756803668,
      "total_token_delta_median": 46958.0,
      "wall_time_delta_median": 19.460899999999995,
      "wall_time_delta_pct": 0.23266426521064942
    }
  }
}
```

## Policy analysis

| task | repeat | repo_only_strict_offline | repo_only_web_audited | DocAtlas best | policy_interpretation |
|---|---|---|---|---|---|
| click_group_001 | 0 | missing | missing | missing | no policy-clean advantage observed |
| decisive_docmancer_vector_timeout_fallback_001 | 0 | resolved=False, policy_clean=True, network_attempts=0 | resolved=False, policy_clean=True, network_attempts=0 | resolved=False, policy_clean=True, network_attempts=0 | no policy-clean advantage observed |
| decisive_nbo_cross_module_gate_large_001 | 0 | resolved=False, policy_clean=True, network_attempts=0 | resolved=False, policy_clean=True, network_attempts=0 | resolved=False, policy_clean=True, network_attempts=0 | no policy-clean advantage observed |
| fastapi_depends_001 | 0 | missing | missing | resolved=True, policy_clean=True, network_attempts=0 | no policy-clean advantage observed |
| mixed_fastapi_project_001 | 0 | missing | missing | resolved=False, policy_clean=True, network_attempts=0 | no policy-clean advantage observed |
| real_project_nbo_001 | 0 | resolved=True, policy_clean=True, network_attempts=0 | resolved=True, policy_clean=True, network_attempts=0 | resolved=True, policy_clean=True, network_attempts=0 | no policy-clean advantage observed |
| real_project_nbo_generated_source_001 | 0 | resolved=True, policy_clean=True, network_attempts=0 | resolved=True, policy_clean=True, network_attempts=0 | resolved=True, policy_clean=True, network_attempts=0 | no policy-clean advantage observed |
| real_project_nbo_permission_002 | 0 | resolved=True, policy_clean=True, network_attempts=0 | resolved=True, policy_clean=True, network_attempts=0 | resolved=True, policy_clean=True, network_attempts=0 | no policy-clean advantage observed |

Policy answers:

- Did repo_only solve tasks only by violating no-web policy? No supported pattern in comparable pilot records; strict-offline runs were generally policy-clean.
- Did DocAtlas solve policy-clean where repo_only did not? No such win was detected in current comparable records.
- Did web-audited baseline gain anything? No consistent gain over strict-offline baseline was detected.

## Token and wall-time analysis

DocAtlas generally increased token usage and wall time in paired comparisons. Any quality/policy-clean gains in historical paired pilots were costly rather than efficient. For context-injected conditions, injected context token attribution unavailable.

## Context utilization

```json
{
  "docatlas_action_checklist_injected": {
    "checklist_used_rate": 0.9375,
    "confidence": "normal",
    "context_used_rate": 1.0,
    "docatlas_call_rate": 1.0,
    "fallback_rate": 0.4375,
    "resolved_when_context_not_used": null,
    "resolved_when_context_used": 0.5625,
    "retrieval_success_rate": 0.125,
    "runs": 16,
    "vector_timeout_rate": 0.4375
  },
  "docatlas_context_injected": {
    "checklist_used_rate": 0.0,
    "confidence": "normal",
    "context_used_rate": 0.8461538461538461,
    "docatlas_call_rate": 0.8461538461538461,
    "fallback_rate": 0.0,
    "resolved_when_context_not_used": 0.0,
    "resolved_when_context_used": 0.36363636363636365,
    "retrieval_success_rate": 0.0,
    "runs": 13,
    "vector_timeout_rate": 0.0
  },
  "docatlas_snippet_first": {
    "checklist_used_rate": 0.0,
    "confidence": "low confidence",
    "context_used_rate": 0.0,
    "docatlas_call_rate": 0.0,
    "fallback_rate": 0.0,
    "resolved_when_context_not_used": 0.0,
    "resolved_when_context_used": null,
    "retrieval_success_rate": 0.0,
    "runs": 4,
    "vector_timeout_rate": 0.0
  },
  "docatlas_tool_optional": {
    "checklist_used_rate": 0.0,
    "confidence": "low confidence",
    "context_used_rate": 0.3333333333333333,
    "docatlas_call_rate": 0.0,
    "fallback_rate": 0.0,
    "resolved_when_context_not_used": 0.0,
    "resolved_when_context_used": 0.0,
    "retrieval_success_rate": 0.0,
    "runs": 6,
    "vector_timeout_rate": 0.0
  },
  "docatlas_tool_recommended": {
    "checklist_used_rate": 0.0,
    "confidence": "normal",
    "context_used_rate": 1.0,
    "docatlas_call_rate": 1.0,
    "fallback_rate": 0.0,
    "resolved_when_context_not_used": null,
    "resolved_when_context_used": 0.3684210526315789,
    "retrieval_success_rate": 0.0,
    "runs": 19,
    "vector_timeout_rate": 0.0
  },
  "docatlas_tool_required_once": {
    "checklist_used_rate": 0.0,
    "confidence": "low confidence",
    "context_used_rate": 0.5714285714285714,
    "docatlas_call_rate": 0.5714285714285714,
    "fallback_rate": 0.0,
    "resolved_when_context_not_used": 0.0,
    "resolved_when_context_used": 0.25,
    "retrieval_success_rate": 0.0,
    "runs": 7,
    "vector_timeout_rate": 0.0
  }
}
```

## Claims

Can claim:

- Existing benchmark artifacts now have a normalized cost/accuracy analysis.
- DocAtlas adoption/context-use occurred in DocAtlas conditions.
- Current comparable artifacts show limited quality/policy-clean gains for some DocAtlas-assisted workflows, with higher token/time cost.

Cannot claim:

- DocAtlas improves coding-agent patch success.
- DocAtlas is token- or time-efficient versus repo-only on current tasks.
- DocAtlas provides broad or statistically strong policy-clean wins over repo-only.
- The result is statistically strong; many samples are small and some artifacts are validation/screening rather than pilots.
