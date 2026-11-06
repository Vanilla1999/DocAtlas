# Candidate terminal snapshot: 13 of 16 receipts

**16/37 facts; 17/37 supporting fact citations. Five 900-second L2 timeouts count as failed answers.**

The eight previously reviewed L0 cases are unchanged. Newly reviewed terminal receipts: L2 T01-en, T01-ru, T02-ru, T05-ru, T10-ru. Each has session outcome `interrupted`, a censored receipt, no final text and no completed context tool result. No outstanding sessions were polled.

The interrupted JSONL streams omit usage present in persisted session metadata. This artifact uses the more complete session totals, preserving the smaller step-event totals and flagging the mismatch rather than claiming reconciliation.

## Recorded usage and outcomes

```json
{
  "terminal_receipts": 13,
  "completed_answers": 8,
  "censored_timeouts": 5,
  "expected_full_sessions": 16,
  "facts_pass": 16,
  "facts_total": 37,
  "facts_partial": 1,
  "citations_supported": 17,
  "answers_pass": 5,
  "usage_recorded_lower_bound": {
    "input": 356307,
    "output": 3842,
    "reasoning": 0,
    "cache_read": 28032,
    "cache_write": 0,
    "input_with_cache": 384339,
    "steps": 32,
    "top_level_tool_calls": 24,
    "top_level_tool_errors": 0,
    "reported_nested_tool_calls": 16
  },
  "original_question_deviations_observed": 6,
  "original_question_exact_observed": 2,
  "original_question_unobservable": 5,
  "emergency_stops": 2,
  "seconds_sum": 5324.3
}
```

## Fresh paired comparison

```json
{
  "fresh_full_baseline_input_with_cache": 169853,
  "fresh_full_baseline_sessions": 16,
  "fresh_full_baseline_facts": "42/46",
  "matched_baseline_sessions": 13,
  "matched_baseline_usage": {
    "input": 93988,
    "output": 7313,
    "reasoning": 0,
    "cache_read": 29952,
    "cache_write": 0,
    "input_with_cache": 123940,
    "steps": 40,
    "top_level_tool_calls": 40,
    "top_level_tool_errors": 0,
    "reported_nested_tool_calls": 0
  },
  "matched_baseline_facts_pass": 35,
  "matched_baseline_facts_total": 37,
  "candidate_recorded_input_with_cache_lower_bound": 384339,
  "matched_input_ratio_lower_bound": 3.1010085525254154,
  "limitation": "Only 13 terminal receipts included; three unnotified/unread cases are absent, not assumed failures. Five censored cases count as failed answers, and their recorded cost is a lower bound. Six exact-question deviations remain protocol failures. Historical and setup-invalid runs are separate."
}
```

Use the matched 13-case baseline for this snapshot. Final aggregation must use the full fresh **169853 input+cache / 16** baseline, not historical runs. A lower token cost on a timed-out case would not establish efficiency: no answer was produced and in-flight cost can be missing.

## Exact-question and source checks

The six observed L0 quote-wrapping deviations remain failures of exact original-question preservation. For the five censored L2 calls, in-flight get_docs_context arguments are absent from the saved completed-tool stream: preservation is **unobservable**, not PASS or a guessed deviation.
Delivered source bodies were checked against independent frozen file spans; content_sha256 was checked for projection-fingerprint presence, not compared with sha256(snippet). Independent raw-file SHA values are separately labelled. Projection-digest reconstruction is not claimed.

## New per-fact grades

### L2/T01-en

No final answer. Receipt: 900.18 seconds; censored at 900 seconds. Recorded input+cache: 5339 (lower bound).

- **T01.F1: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: Branch name: `feat/<topic>` or `fix/<description>`
- **T01.F2: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: Run the full test suite before opening the PR
- **T01.F3: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: New connectors or fetchers should include tests where practical

### L2/T01-ru

No final answer. Receipt: 900.24 seconds; censored at 900 seconds. Recorded input+cache: 8323 (lower bound).

- **T01.F1: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: Branch name: `feat/<topic>` or `fix/<description>`
- **T01.F2: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: Run the full test suite before opening the PR
- **T01.F3: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: New connectors or fetchers should include tests where practical

### L2/T02-ru

No final answer. Receipt: 900.25 seconds; censored at 900 seconds. Recorded input+cache: 5347 (lower bound).

- **T02.F1: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: `doc-atlas clear-index` previews a bounded cleanup plan before removing derived
- **T02.F2: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: for all local indexes while preserving configuration
- **T02.F3: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: can be bound to its `plan_digest`

### L2/T05-ru

No final answer. Receipt: 900.22 seconds; censored at 900 seconds. Recorded input+cache: 5363 (lower bound).

- **T05.F1: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: the installed wheel, actual project installer, stdio MCP, SQLite and MiniLM
- **T05.F2: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: not autonomous OpenCode/model runs or token benchmarks

### L2/T10-ru

No final answer. Receipt: 900.2 seconds; censored at 900 seconds. Recorded input+cache: 5359 (lower bound).

- **T10.F1: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: Воспроизвести один исходный пользовательский вопрос через настоящий публичный API/CLI/MCP
- **T10.F2: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: **Две сопоставимые попытки.** Запустить поток с подробными логами off и on из двух одинаковых исходных состояний
- **T10.F3: FAIL; citation FAIL.** Session censored after 900 seconds with no final answer. Required fact not answered: **Два независимых PASS и паритет.**

## Limits

No new model/product calls. Fixed terminal-receipt snapshot; no completion polling.
For all five censored sessions, persisted session token totals exceed the interrupted JSONL step totals. Accounting uses the larger persisted session ledger and preserves both, without claiming reconciliation. Unrecorded in-flight work and emitted tool counts remain lower bounds.
A censored session without final text fails every required fact and citation, regardless of exit/status or server work underway.
An unrecorded in-flight request is not evidence that no scan occurred or that its original question was exact.
All previous successful-case grading is preserved byte-for-byte in the prior artifact and reused without inference or retuning.
