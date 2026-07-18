# Test Suite Diagnostic Hardening

Status: proposed

## Goal

Make green test results distinguish runtime behavior from schema, artifact, serialization, and compatibility checks, and add a small mutation gate for the security- and evaluation-critical contracts changed here.

## Source evidence

This design is grounded in the current repository surfaces:

- `tests/test_preindex_coverage.py:580-649` claims to verify `guard_dropped_all`, but permits branches with `assert True`, `pass`, or no exact status/reason assertion.
- `docmancer/docs/application/library_docs_service.py:1451-1471` defines the observable contract: when source guards drop every retrieved chunk, status is `empty_library_index`, diagnostics reason is `guard_dropped_all`, and warnings include bounded rejection diagnostics.
- `tests/test_patch_constraints_service.py:656-680` contains five backward-name wrappers that directly invoke already-collected test functions.
- `eval/task_level/task33c_protocol.lock.json:1-12` identifies one active Task33 task, three conditions, a 12-turn limit, and one retrieval call.
- `eval/task_level/tasks.jsonl:18` publicly declares the active task objective, expected symbols (`PermissionService`, `evaluateFlowEntry`, `PermissionDecision`, `BrowserPermissionGate`, `ScanPermissionGate`, `OfflineSyncGate`), and expected project documents. Hidden tests and oracle content are not design inputs.
- `eval/task_level/evaluators/actionability.py:43-96` has no contract for the active Task33 task and silently returns an empty list.
- `eval/task_level/github_models.py:441-486,500-556,692-755` declares a host-owned runner, iterates over `request.max_turns`, persists per-turn usage, and reports `max_turns_enforced=True`.
- `tests/task_level/test_task_evaluation.py:35-41` checks only policy wording, not the host loop.
- `pytest.ini:29-30` and `tests/conftest.py:25-70` define existing operational markers (`advanced`, `live`, `live_network`, `integration`).
- `.github/workflows/ci.yml:67-102` runs core and advanced suites separately.

## Non-goals

- Do not change `task33c_protocol.lock.json`, task fixtures, oracle files, hidden tests, causal thresholds, or benchmark conditions.
- Do not inspect hidden evaluator contents.
- Do not add a full mutation framework or whole-repository mutation run.
- Do not infer runtime correctness from committed benchmark reports.

## Decision 1: exact `guard_dropped_all` oracle

Rewrite the existing test without changing production behavior. The test must assert all of:

1. `status == "empty_library_index"`;
2. `diagnostics["reason_code"] == "guard_dropped_all"`;
3. warnings contain `cross_source_contamination_filtered` with `dropped == 2`;
4. warnings contain `wrong_library_id` with `dropped == 2`;
5. `results == []`.

No conditional assertion, `assert True`, or permissive fallback is allowed.

## Decision 2: remove duplicate wrappers

Delete the five wrappers at `tests/test_patch_constraints_service.py:657-680` that only call another collected `test_*` function. Their target tests remain authoritative. Repository and CI searches show no selector contract for the wrapper names; therefore preserving aliases would retain duplicate execution without compatibility value.

## Decision 3: active-protocol actionability invariant

`requirements_for_task()` remains a public-evidence registry. Add a contract for the single task named by `TASK33C_PILOT_TASK_ID`. The registry is literal and machine-checkable:

| requirement_id | expected_symbols | expected_files |
| --- | --- | --- |
| `shared_entry_decision` | `PermissionService`, `evaluateFlowEntry`, `PermissionDecision` | `docs/permission-architecture.md`, `lib/modules/permission/application/permission_service.dart` |
| `browser_gate_delegates` | `BrowserPermissionGate`, `evaluateFlowEntry` | `docs/browser-flow.md`, `lib/modules/browser/application/browser_permission_gate.dart` |
| `scan_gate_delegates` | `ScanPermissionGate`, `evaluateFlowEntry` | `docs/scan-flow.md`, `lib/modules/scan/application/scan_permission_gate.dart` |
| `offline_sync_uses_shared_gate` | `OfflineSyncGate`, `evaluateFlowEntry` | `docs/offline-sync.md`, `lib/modules/sync/application/offline_sync_gate.dart` |

Every row uses `source_type="project_doc"`, `allowed_for_agent=True`, and `match_all_symbols=True`. The opt-in conjunctive mode requires the complete symbol group for that row, so the shared `evaluateFlowEntry` symbol alone cannot recall all four contracts; legacy task registries retain their existing any-symbol-or-file matching. The descriptions restate the corresponding public fixture documents only. Generated-file immutability remains a visible patch-surface constraint, not an actionability row: the public task has no generated-file symbol that could represent that requirement without producing false recall.

Add an invariant test that loads the task ID from the active protocol lock and compares the complete registry against the literal table. It must also load the public `TaskSpec` and verify that every expected symbol is in `task.expected_symbols`, every file is in `task.expected_project_docs` or `TASK33C_REQUIRED_TARGET_PATHS`, every symbols/files list is non-empty, and no requirement contains a hidden/oracle/private path, `source_type="hidden_test"`, or `allowed_for_agent=False`. An adversarial scorer test proves that `evaluateFlowEntry` alone yields zero recall/salience, and a positive test proves that all four complete symbol groups yield full recall/salience. Unknown non-protocol task IDs may continue returning an empty list; the active protocol may not.

## Decision 4: behavioral runner enforcement test

Delete the policy-wording test from `test_task_evaluation.py`. Do not change the frozen policy text or production runner.

Add an adversarial test to `test_github_models_adapter.py` using the real `GitHubModelsRunner` host loop and fake provider completions that never emit `finish`. With `max_turns = 2`, assert:

1. the provider is called exactly twice;
2. status is `max_turns_exhausted` and exit code is non-zero;
3. `max_turns_enforced is True`;
4. persisted usage contains exactly two turns numbered 1 and 2;
5. token usage reports `completed_turn_events == 2` and `effective_max_turns == 2`.

This proves host enforcement independently of prompt wording.

## Decision 5: semantic suite labels

Register five mutually exclusive diagnostic markers:

- `behavioral`: executes production behavior and checks a semantic outcome;
- `schema`: checks a static or wire-format shape without proving producer behavior;
- `artifact`: checks committed reports, snapshots, workflows, or documentation artifacts without executing their producer;
- `serialization`: checks encoding/decoding compatibility only;
- `compatibility`: checks a deliberately supported legacy alias or backward-compatible surface.

These markers are orthogonal to operational markers such as `advanced`, `live`, and `integration`.

Classification is explicit rather than defaulting unknown tests to `behavioral`:

1. introduce a temporary `diagnostic_unclassified` marker during inventory construction;
2. collect the full suite and commit a module-level classification manifest, with exact node-ID overrides for mixed-purpose modules;
3. classify every currently collected test as one of the five diagnostic labels;
4. fail collection if a test has multiple diagnostic labels, has no manifest match, or remains `diagnostic_unclassified`;
5. new test modules therefore fail closed until classified; no unknown test is presented as behavioral evidence.

The manifest is reviewed at module level. Exact test overrides take precedence over module labels. In particular, committed artifact/snapshot modules, JSON-serializability tests, schema-only tests, and genuine compatibility tests receive their narrow labels; tests that execute production logic and assert semantic outcomes receive `behavioral`. The manifest also stores a SHA-256 digest of the sorted, de-parameterized node IDs in every module. Full-module and full-directory collection validate those digests, so adding, deleting, or renaming a test in an already known module requires explicit manifest review. Exact-node selections skip module-completeness validation but still require a known module and diagnostic label. A checked-in inventory test proves zero unclassified tests and exactly one diagnostic marker per node ID. Operational markers are excluded from this count.

CI keeps the existing core/advanced split; labels enable diagnostic reporting and selective local runs without changing which tests are required.

## Decision 6: bounded mutation gate

Add `scripts/run_critical_mutation_gate.py`. It creates a fresh isolated temporary source copy per run. It excludes `.git`, virtual environments, generated results, runtime workspaces, oracle data, and hidden-test data, but preserves the importable `eval/task_level/fixtures` package and the public template files required by targeted tests. It runs a baseline plus three exact mutants:

1. disable the code-declaration guard in `docmancer/docs/domain/normative_language.py`;
2. disable the active Task33 actionability branch;
3. extend the GitHub Models host loop by one turn.

The gate uses the current `sys.executable` and runs pytest with `cwd=<temp-copy>` and `PYTHONPATH=<temp-copy>` prepended to the existing environment. Before baseline and mutant tests, an import-origin probe asserts that every targeted production module's `__file__` is inside the temporary copy. Baseline and mutant runs use the same command and environment.

Each exact replacement must match once, change the source hash, and run in a new clean temporary copy. Each mutant has one targeted test and is counted as killed only when pytest exits with code `1` and its JUnit report contains at least one testcase and failure with zero errors. Interruption, collection/setup/internal errors, invalid invocation, and no collected tests are infrastructure failures, not successful mutation detection. A surviving mutant, wrong import origin, non-unique replacement, unchanged hash, or baseline failure fails the gate. The shared worktree is never modified. On failure, stdout, stderr, and JUnit reports are retained under `${RUNNER_TEMP}` when available; the advanced CI job uploads matching directories for diagnosis.

Run the gate in the existing `advanced-contract` CI job after advanced pytest. Keep the gate deterministic, offline, provider-free, and under one minute locally.

## Deletions

Delete only tests proven redundant or replaced by a stronger behavioral oracle:

- five direct wrapper tests in `test_patch_constraints_service.py`;
- one prompt-string policy test in `test_task_evaluation.py` after the host-loop enforcement test is green.

Do not delete artifact, schema, serialization, or compatibility tests solely because they are not behavioral; classify them so their evidence level is visible.

## Verification

Required before merge:

1. RED evidence for the new actionability invariant and runner-limit behavior where applicable;
2. focused pytest for every modified test module;
3. mutation gate baseline passes and all three mutants are killed;
4. `pytest tests -q` passes;
5. collection shows every test has exactly one diagnostic marker;
6. `git diff --check` passes;
7. `git diff --quiet -- eval/task_level/task33c_protocol.lock.json` passes and its SHA-256 remains `d2690c4dd5a8b0b39395d2143369fe2d1c3158e0d7b6527420b8d6987333a378`;
8. independent read-only blocking review returns PASS.
