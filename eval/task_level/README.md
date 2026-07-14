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
- `docatlas_bounded_subagent`: the host freezes the same one-call evidence snapshot used by the direct lane, then a fresh worker compresses it; only its validated ActionPacket enters the parent session.

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

For a causal isolated lane, provide `--runner-factory module.path:factory` for a runner that proves the hard turn limit and `--isolated-worker-factory module.path:factory` for a host-owned worker adapter. The adapter must expose verified capability evidence and provider-usage proof. The harness derives a frozen project-doc query from repeated domain terms in the task objective (without evaluator/gold fields), freezes one host retrieval for both bounded lanes, checks its objective/query derivation, project/index revisions, and evidence hash, and validates the returned packet only against that snapshot.

The bundled JSON subprocess adapter is a non-causal protocol scaffold unless a host-side provider-usage verifier is injected. Its worker runs under bubblewrap with user, mount, network, and PID namespaces; an executable canary must prove that the working directory is read-only, the workspace is absent, networking is denied, and a detached descendant cannot outlive the worker. Missing or failed canaries, missing provider proof, `insufficient_evidence`, a second attempt, or incomplete pilot metrics produce a fail-closed/`INCONCLUSIVE` result. Merely supplying a flag or finding a `bwrap` executable is not verification.
