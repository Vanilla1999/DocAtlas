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

Task 33C dry-run protocol (exactly one task, three cells, one repeat):

```bash
python3 -m eval.task_level.runner \
  --task33c-pilot --dry-run \
  --tasks decisive_nbo_cross_module_gate_large_001 \
  --run-id task33c_dry_run
```

For a causal run, provide `--runner-factory module.path:factory` for a runner that proves the hard turn limit. The harness derives a frozen project-doc query from repeated domain terms in the task objective (without evaluator/gold fields), freezes one host retrieval for the bounded-direct cell, checks its objective/query derivation, project/index revisions, and evidence hash, and validates the returned packet only against that snapshot. The required-once cell exposes exactly one agent-callable `get_docs_context` action before editing and requires a valid bounded-direct ActionPacket for the original task objective.

The bundled JSON subprocess adapter is a non-causal protocol scaffold unless a host-side provider-usage verifier is injected. Its worker runs under bubblewrap with user, mount, network, and PID namespaces; an executable canary must prove that the working directory is read-only, the workspace is absent, networking is denied, and a detached descendant cannot outlive the worker. Missing or failed canaries, missing provider proof, `insufficient_evidence`, a second attempt, or incomplete pilot metrics produce a fail-closed/`INCONCLUSIVE` result. Merely supplying a flag or finding a `bwrap` executable is not verification.

GitHub Actions can inject the controlled GitHub Models adapters with its ephemeral `GITHUB_TOKEN` and `models: read` permission:

```bash
python -m eval.task_level.runner \
  --task33c-pilot \
  --tasks decisive_nbo_cross_module_gate_large_001 \
  --runner-factory eval.task_level.github_models:create_github_models_runner \
  --verify-runner --verify-docatlas-tool \
  --model openai/gpt-4o-mini
```

The parent adapter exposes a hard-turn-controlled repository tool allowlist. The bounded-direct ActionPacket is constructed and validated deterministically by the host from immutable host-owned evidence; no isolated worker or worker prompt is used by the v2 causal protocol.

The engineering pilot freezes a 12-turn limit per parent cell and uses the low-rate-tier `openai/gpt-4o-mini` adapter so a worst-case three-cell run remains below the free API's daily request budget. A turn-limit exhaustion or provider 429 is infrastructure-incomplete, never a completed causal cell.

The machine-readable protocol is `task33c_protocol.lock.json`. Do not edit the task, query, model, conditions, budgets, fixture/oracle/hidden-test identities, or decision thresholds after the first causal dispatch. `task33c_completeness.json` is diagnostic only; the authoritative gate is the independent `task33c_validation.json` produced by:

```bash
python -m eval.task_level.task33_validation \
  eval/task_level/results/task33c_github_models_RUN_ID
```

GitHub execution is intentionally split. `task33c-pr-checks.yml` runs untrusted pull-request validation without GitHub Models access. `task33c-actions-probe.yml` is manual-only. First dispatch it with `run_causal_pilot=false` on the trusted branch and inspect the structured-model, retrieval, and Docker canary artifact. After that probe passes and the protected `task33c-causal-pilot` environment is approved, dispatch the same frozen ref once with `run_causal_pilot=true`. The causal artifact contains only files listed in `task33c_artifact_manifest.json`; virtual environments and workspace copies are never uploaded.

The same protocol can run locally without GitHub Actions or GitHub Models. The local profile uses the pinned `gpt-4o-mini-2024-07-18` snapshot through the direct OpenAI Chat Completions API. It preserves the same host-controlled tool loop, structured schemas, request budget, Docker boundary, evidence snapshot, and independent verifier. Only `OPENAI_API_KEY` is required; the key is never forwarded to Docker or persisted. Run the fail-closed preflight first:

```bash
export OPENAI_API_KEY="..."
python -m eval.task_level.task33_local
```

This builds the digest-pinned evaluator image, prewarms the frozen fixture dependencies, and writes provider, Docker, and retrieval probes. It does not run causal cells. After inspecting a `verified` preflight, explicitly request the one-attempt pilot:

```bash
python -m eval.task_level.task33_local --run-causal-pilot
```

The local result is acceptable only when `task33c_validation.json` reports `VALID`. GitHub Models and direct OpenAI API are separate frozen provider profiles; a single run must use exactly one profile for all three cells, and their results must not be pooled as if they used the same provider.

For directional local iteration without an API key, an explicitly non-causal Codex OAuth path is available. It does not modify the frozen provider profiles and can never produce `task33c_validation.json` or a `VALID` verdict.

### Local two-cell smoke procedure

Use this procedure to compare `repo_only_strict_offline` with `docatlas_bounded_direct`. Do not substitute the legacy three-cell exploratory pilot or expand to a matrix without explicit approval.

1. Run a provider-free preflight with a unique ID:

   ```bash
   run_id="task43_smoke_preflight_$(date -u +%Y%m%d_%H%M%S)"
   uv run --python 3.13 --extra dev python \
     -m eval.task_level.task33_codex_exploratory \
     --host-exploratory \
     --two-cell-smoke \
     --run-id "$run_id"
   ```

   Require `preflight-summary.json` to report `READY_FOR_EXPLORATORY_RUN`, retrieval `status=verified`, exactly one retrieval call, no missing required paths/categories, and `codex_oauth_selector.status=not_required`. This command must not create Codex/provider event artifacts.

2. Use a new unique ID for the bounded run. Result directories are immutable; never reuse the preflight ID:

   ```bash
   run_id="task43_smoke_run_$(date -u +%Y%m%d_%H%M%S)"
   uv run --python 3.13 --extra dev python \
     -m eval.task_level.task33_codex_exploratory \
     --host-exploratory \
     --two-cell-smoke \
     --run-exploratory-pilot \
     --run-id "$run_id" \
     --timeout-seconds 600 \
     --worker-timeout-seconds 120
   ```

   The entrypoint reruns the free preflight, performs one runner canary, and starts exactly two cells only after the canary passes. The provider-call cap is three: one canary, one repo-only cell, and one bounded-direct cell. Selector and DocAtlas tool-visibility canaries are not required because neither omitted lane is present.

3. Do not retry a failed canary or cell in the same cycle. Preserve and classify the artifact, stop with zero or partial cells as applicable, fix infrastructure separately, and obtain explicit approval for a new cycle.

4. Audit cardinality before reporting metrics. There must be exactly three `events.jsonl` streams under the run directory, and each must contain one `thread.started` and one `turn.completed`. Confirm `exploratory_manifest.json` records the exact two conditions, `repeats=1`, `two_cell_smoke=true`, and `provider_call_cap=3`.

5. Verify the harness and frozen lock after local changes:

   ```bash
   uv run --python 3.13 --extra dev python -m pytest \
     tests/task_level/test_task33_codex_exploratory.py \
     tests/task_level/test_task_evaluation.py \
     tests/task_level/test_runner_adapter.py \
     tests/task_level/test_task33_validation.py -q
   git diff --check
   sha256sum eval/task_level/task33c_protocol.lock.json
   git diff --quiet -- eval/task_level/task33c_protocol.lock.json
   ```

6. Compare correctness first (`resolved`, public tests, hidden tests), then evidence recall, total/uncached/output tokens, latency, tool calls, and failure class. A correctness tie with higher cost is not an improvement even if evidence recall rises. One task with one repeat is directional only; never make causal, statistical, release, or generalized performance claims.

Artifacts are written under `eval/task_level/results/<run-id>[_preflight]/`. `task33c_exploratory_summary.json` records correctness, directional token counts, and latency per lane. Time-to-first-edit remains `null` in the summary because current Codex JSONL normalization is not stream-timed. Codex CLI thread IDs are client identifiers, not server request IDs. Host exploratory execution is unisolated, provider usage/server request IDs and hard-turn enforcement are not independently verified, and this path is not validator eligible.
