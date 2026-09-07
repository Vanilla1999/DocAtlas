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

## Diagnostic inventory repair

Inventory repair commit: `b60d0992149e0ab54e61aa6456b8392bbdae3186`.

The first publication incorrectly wrote the SHA-256 of `tests/test_docs_service_part07.py` into `module_node_hashes`. That field is defined as the SHA-256 of the sorted base pytest node IDs, not the file contents. The deadline test changed only its body, so its 15-node inventory is unchanged and the correct digest remains `8657db026c2d2a0ddfdb1bbe266fc807360f223ba8f0d639ffbe0fa203939813`.

The `tests/docs/test_question_span_coverage.py` digest remains `6ae30e88c1c081c0bbed9ed2705233aed6b2acfe7073977a44dbb5731929674c` because that module really did add one new adversarial test node.

GitHub-side verification before publication:

- recomputed the service-module digest from exactly 15 discovered test nodes;
- full offline-core `--collect-only` passed the diagnostic inventory hook;
- `tests/test_docs_service_part07.py` plus `tests/test_diagnostic_labels.py` passed;
- the publication diff was restricted to `tests/diagnostic_labels.json`.

## P1 evidence refresh

Evidence refresh commit: `1ce88a67ee1a6add6f06aa34880bef6d0d730646`.

P1.4, P1.5 and P1.6 were regenerated after the production ownership change. Review of the generated diff showed no case, verdict, mismatch, assignment, safety metric or claim-boundary change. The only changes in those three reports are the new `_project_answer_contract_part02.py` blob identity and the aggregate planner SHA. The P1 Agent Truth closure then changed only its references to the refreshed P1.4/P1.5/P1.6 blobs.

Verified after regeneration:

- P1.4 gate PASS; self-test `5/5`;
- P1.5 gate PASS; self-test `6/6`;
- P1.6 gate PASS; self-test `6/6`;
- P1 Agent Truth closure PASS; self-test `4/4`;
- closure outcome remains `AUTONOMOUS_AGENT_TRUTH_NOT_PROVEN`.

## Temporary publication infrastructure

The one-shot downstream-fix, evidence-refresh and diagnostic-repair workflows removed themselves in their publication commits. None of `.github/workflows/pr179-downstream-fix.yml`, `.github/workflows/pr179-refresh-p1-evidence.yml`, or `.github/workflows/pr179-fix-diagnostic-node-hash.yml` is present in the final production tree.
