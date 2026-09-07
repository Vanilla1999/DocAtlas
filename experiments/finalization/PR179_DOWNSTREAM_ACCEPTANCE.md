# PR #179 downstream acceptance fixes

Production fix: `dc1befb5bce806b2ced2fd2ca4c1ff66a9ca5f0e`.

## Question-surface regression

The newly reachable downstream CI gate exposed three legacy-owner questions that the newer QuestionPlan path was claiming as unresolved. The legacy contract already represented the bounded `behavior + usage` form for an exact technical subject.

Fix:

- preserve legacy ownership only for the exact bounded form `what does <technical_subject> do/report and when should I use it / it be used`;
- keep compound questions with any extra unknown tail fail-closed;
- classify ownership from the final supported contract rather than `plan.handled` alone.

Local evidence after the fix:

- canonical question-surface gate: `100/100`;
- ownership distribution: `legacy=11`, `question_plan=77`, `unsupported=12`;
- nearby question/contract + deadline/executor/diagnostic tests: `354 passed`.

## Python 3.11 deadline failure

The full CI job failed `test_library_prefetch_job_deadline_is_terminal_and_retryable` before `SlowAgent.add()` was entered. This was a test-isolation defect, not a production deadline defect.

Production `LibraryJobExecutor` intentionally starts a submitted job deadline while it is queued. That behavior remains protected by `test_queued_work_does_not_receive_a_fresh_execution_deadline` and was not changed.

The service deadline test was using the process-wide shared executor while assuming an empty queue. In a full suite, unrelated still-running jobs could consume the intentionally tiny `0.05s` deadline before this test's worker started. The test now uses a dedicated executor so it measures the intended property: once its own work starts, deadline terminalization is failed + retryable and staging is rolled back.

Targeted evidence:

- deadline + executor + diagnostic inventory: `12 passed`;
- repeated isolated deadline runs completed successfully before command-budget cutoff;
- no timeout constant or production executor semantics were weakened.

## Temporary publication infrastructure

A one-shot workflow applied the reviewed patch to the current PR head and removed itself in the same production commit. `.github/workflows/pr179-downstream-fix.yml` is absent from `dc1befb5...`.
