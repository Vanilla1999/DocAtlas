# Task-Level Agent Benchmark

This harness measures whether DocAtlas improves real code patches, not retrieval scores.

Primary outcome: a single independent agent run produces a patch that applies cleanly, passes fail-to-pass tests, preserves pass-to-pass tests, builds/compiles, and does not violate condition policy.

The pilot conditions are:

- `repo_only`: repository, issue, shell, search/read/edit, tests only.
- `context7`: repo-only plus Context7 docs tools.
- `docatlas_evidence_first`: repo-only plus preindexed DocAtlas `get_docs_context` with `response_style=evidence-first`.
- `docatlas_snippet_first`: repo-only plus preindexed DocAtlas `get_docs_context` with `response_style=snippet-first`.
- `docatlas_zero_setup`: exploratory DocAtlas without preindexing; never mixed with preindexed storage.
- `docatlas_bounded_direct`: one deterministic, validated ActionPacket enters the parent session.
- `docatlas_bounded_subagent`: one fresh host worker retrieves/compresses; only its validated ActionPacket enters the parent session.

Run safety:

- Every causal run must use a fresh checkout/worktree, fresh process, fresh conversation, fresh temporary `HOME`, fresh `DOCMANCER_HOME`, and a condition-specific output directory.
- Gold patches and gold context are evaluator-only and must not be copied into an agent checkout or prompt.
- Generated results are ignored except `results/README.md` and `results/sample_report.md`.

Current status:

- The manifest contains 8 curated pilot task specs.
- The runner can validate manifest shape, record environment metadata, and generate smoke reports.
- Independent causal benchmarking is gated until a headless runner is verified to enforce condition tool isolation and emit trajectory, patch, token, and tool-call metrics.

Example smoke command:

```bash
python3 -m eval.task_level.runner --validate --smoke --repeats 1
```

Task 33C dry-run protocol (exactly one task, four lanes, one repeat):

```bash
python3 -m eval.task_level.runner \
  --task33c-pilot --dry-run \
  --tasks decisive_nbo_cross_module_gate_large_001 \
  --run-id task33c_dry_run
```

For a causal isolated lane, also provide an absolute JSON-in/JSON-out worker command and a versioned identity. The host passes no parent transcript or repository path, uses a fresh read-only working directory, permits only explicitly named environment variables, allows one attempt, kills the process group on timeout, and rejects any response other than the bounded result contract. The built-in permission boundary fails closed when run as root because mode bits cannot constrain a privileged worker; use a non-root host or a separately verified OS sandbox. A root host must explicitly record that external proof with `--isolated-worker-root-sandbox-verified`; the flag is persisted in pilot metadata and must not be used as a substitute for the proof.
