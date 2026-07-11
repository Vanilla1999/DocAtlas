# Task 23 — decide product scope from task success and token efficiency

## Priority

P1/P2 evidence gate. Run after the primary workflows are stable; do not use this task to tune correctness bugs.

## Problem

The current decisive benchmark is a `NEGATIVE_SIGNAL`: all tested conditions resolved 0/3 tasks, and DocAtlas increased time/context volume without a correctness gain. Newer candidates are all from one domain and were correctly rejected as too easy. Retrieval Hit@K and tool adoption do not prove that a coding agent completes work better.

## Goal

Measure whether DocAtlas improves real coding outcomes or context efficiency, then make an explicit continue, narrow, integrate, or pivot decision.

## Required benchmark design

1. Analyze the negative run by required-evidence recall, context rank, agent tool usage, failure reason, latency, and input/output token cost. Do not discard it.
2. Materialize at least three independent external real-project domains. Critical facts must be distributed across project docs, code/config/lockfiles, and dependency docs and not be obvious near the edit.
3. Screen every candidate with a repo-only pilot. Too-easy or unfair tasks remain non-differentiating and cannot support claims.
4. Use public tests plus hidden tests, with a named acceptance oracle for each task.
5. Compare at least:
   - repo-only;
   - repo plus audited external web/Context7 context where allowed;
   - DocAtlas available but not recommended;
   - DocAtlas tool-recommended.
6. Use the same model, prompt policy, context limits, attempt budget, and starting repository state across lanes.
7. Run at least three independent repeats per lane/task and report uncertainty rather than only best attempts.
8. Measure resolved rate, patch correctness, required-evidence recall, useful-context ratio, total tokens, tool-output tokens, latency, tool calls, lifecycle overhead, and failure taxonomy.
9. Preserve sanitized traces and immutable task fixtures sufficient to reproduce scoring.

## Predeclared decision rule

Before running, freeze this decision threshold: either DocAtlas improves resolved rate by at least 10 percentage points without increasing median total tokens by more than 10%, or resolved rate remains within 2 percentage points while median total tokens fall by at least 25% and median latency does not increase by more than 10%. Report uncertainty; a threshold is not met when its confidence interval is compatible with a worse result.

If neither threshold is met, do not rewrite the report as a win. Choose one documented outcome:

- improve retrieval/ranking and rerun once on unchanged tasks;
- narrow DocAtlas to local project documentation;
- integrate Context7/web as the external-library source;
- stop parity investment.

## Non-goals

- Do not use self-referential DocAtlas repository tasks as the majority of evidence.
- Do not tune tasks after seeing lane outcomes.
- Do not infer task success from retrieval metrics alone.

## Acceptance criteria

- At least three fairness-clean differentiating tasks from independent domains complete the full repeated protocol.
- Reports include failures, confidence/uncertainty, token/context efficiency, and all non-differentiating exclusions.
- The numeric decision rule above and statistical procedure are committed before result collection and are not edited after outcomes are visible.
- Product claims and the next roadmap revision match the measured decision, including a negative/pivot result.
- Benchmark validators and `git diff --check` pass.
