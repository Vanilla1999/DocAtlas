# Post-merge review: PR #56–#59

Date: 2026-07-16

Repository: `Vanilla1999/DocAtlas`

Reviewed target: `main` at `fd0f1d192ac4ef845ba0198d8b6b9b62ccc84d7c`

Reviewed Git tree: `72151113751d159ed059f171faf9aaeb79ae4ee3`

## Verdict

The stacked merge order and final tree are correct, and no new defect was found in PR #56 (Task 39) or PR #57 (Task 40). Two correctness defects remain in the merged stack:

1. PR #58 silently broadens filtered legacy lexical queries from FTS AND semantics to OR semantics.
2. PR #59 stores the published Task 41 SHA but never evaluates it, so the claimed commit binding is not enforced.

Both findings are reproducible from the merged `main` tree. This review branch intentionally changes no production code.

## Reviewed merge boundaries

| PR | Task | Squash merge | Parent | Result tree | Review result |
|---|---|---|---|---|---|
| [#56](https://github.com/Vanilla1999/DocAtlas/pull/56) | 39 — retrieval baseline | `a7f25d1451469c5454fde73697c0c4814f7da4a8` | `866d294` | `4ca4701e594aa745946927c42a97f1369dbbbf73` | No finding |
| [#57](https://github.com/Vanilla1999/DocAtlas/pull/57) | 40 — parent/child index | `38b26eae93341b24b5a9b4982d173037e06bea21` | `a7f25d1` | `de11fb7624fac289809fe8f0afac3217f435941c` | No finding |
| [#58](https://github.com/Vanilla1999/DocAtlas/pull/58) | 41 — contextual hybrid retrieval | `dbb4ec8b2382427874492dc2625e31133c5a5f37` | `38b26ea` | `1ae917bab5a99b6f91f7d4f729146c7d4e262a74` | Finding 1 |
| [#59](https://github.com/Vanilla1999/DocAtlas/pull/59) | 42 — evidence selection | `fd0f1d192ac4ef845ba0198d8b6b9b62ccc84d7c` | `dbb4ec8` | `72151113751d159ed059f171faf9aaeb79ae4ee3` | Finding 2 |

The four squash merges form the expected first-parent chain. The final local tree exactly matched `origin/main` before this report was added.

## Findings

### [P2] Filtered legacy FTS queries always fall through to broader OR matching

Affected PR: #58

Affected code: `docmancer/core/sqlite_store.py:2008-2148`

`_search_rows()` correctly builds two filter expressions:

- `filter_sql` for promoted columns in `retrieval_children`;
- `legacy_filter_sql` for JSON metadata in legacy `sections` rows.

In the no-active-generation path, however, the primary legacy query interpolates `filter_sql` while binding `legacy_filter_params` (`sqlite_store.py:2121-2125`). For a promoted key such as `library_id`, the generated query references `sections.library_id`, but the legacy `sections` schema has no such column. The resulting `sqlite3.OperationalError` is swallowed at line 2130. Execution then reaches the fallback query, which joins the terms with `OR` at line 2133.

Minimal reproduction on the merged tree:

1. Create a legacy-only `SQLiteStore` with two documents in `library_id=sdk`:
   - `both.md`: `alpha beta exact sentinel`
   - `alpha.md`: `alpha only sentinel`
2. Run `_search_rows("alpha beta", 10)`.
3. Run `_search_rows("alpha beta", 10, filters={"library_id": "sdk"})`.

Observed:

```text
without filter: ['both.md']
with filter:    ['both.md', 'alpha.md']
```

The filter itself is still applied by the fallback, so this is not a cross-library isolation leak. It is a deterministic precision regression: adding an otherwise valid filter broadens the textual predicate and can promote partially matching evidence.

Recommended correction:

- use `legacy_filter_sql` in the primary no-active-generation query as well as `legacy_filter_params`;
- add a regression test proving that a promoted metadata filter preserves the original multi-term FTS semantics on a legacy-only index;
- consider narrowing the caught `OperationalError` path or recording the fallback reason so schema mistakes cannot silently alter retrieval semantics.

### [P2] Task 41 `commit_sha` is stored but not enforced by the Task 42 acceptance gate

Affected PR: #59

Affected code: `eval/evidence_selection_quality.py:162-248` and `eval/evidence_selection/baseline_v1.json:5`

The checked-in baseline contains:

```json
"commit_sha": "9afb20d7aca6c0411b14739781dacceb292cb78f"
```

`evaluate()` reads the baseline and checks dataset digests, frozen metrics, the Task 41 candidate-trace hash, the retrieval-config hash, token cost, and per-case correctness. It never reads or compares `baseline["commit_sha"]`. A repository-wide search finds the field only in `baseline_v1.json`.

Therefore replacing the SHA with any other string does not affect `correctness`, `task41_match`, or the final verdict. The publication step updated the requested remote Task 41 SHA, but the acceptance gate treats it as decorative metadata.

Impact:

- the report cannot substantiate its claimed commit-level provenance binding;
- a stale or mistyped Task 41 SHA remains green as long as the trace/config hashes match;
- no test detects that the published branch identity and the baseline have diverged.

Recommended correction:

- define the intended offline-verifiable identity explicitly (prefer an immutable Task 41 source/tree digest; the pre-squash branch commit is not an ancestor of merged `main`);
- make `evaluate()` fail closed when that identity is absent or mismatched;
- expose the expected and observed identity in `task41_gate`;
- add a regression test that mutates only the baseline identity and requires a failing verdict.

## Review coverage

The review inspected the exact per-PR diffs and the merged behavior for:

- Task 39 dataset/config/code provenance, per-case gates, ranking direction, deterministic ties, and projection budgets;
- Task 40 stable identities, Unicode spans, generation validation/activation, legacy compatibility, vector bookkeeping, and rollback/retention paths;
- Task 41 context construction, query planning, promoted filters, backend verification, strict/degraded dispatch, fusion identity, vector readiness, and legacy coexistence;
- Task 42 candidate normalization, hard eligibility, mandatory coverage, deduplication, budget fitting, selection hashes, formatter survival checks, model-visible validation, and the Task 41 acceptance binding.

Evidence considered:

- the merged first-parent stack and exact Git trees listed above;
- the existing full-suite result `2291 passed, 10 skipped` and successful post-merge CI supplied with the stack;
- static data-flow tracing for the unused `commit_sha` field;
- an isolated executable SQLite reproduction for the legacy filtered-query regression.

## Suggested follow-up

Fix both findings in a separate implementation PR. Keep the changes narrow: one query-variable correction plus a regression test for Finding 1, and one explicit provenance contract plus a mismatch test for Finding 2. Re-run the Task 39–42 provider-free gates, the full suite, `compileall`, `git diff --check`, and the release artifact gate before merging.
