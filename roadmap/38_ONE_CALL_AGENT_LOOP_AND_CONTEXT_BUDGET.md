# Task 38 — one-call agent loop and retained-context budget

## Priority

P1 end-to-end token-control integration. Start after Tasks 34–36 establish a compact server boundary. Keep it separate from the frozen Task 33 protocol unless a new protocol version is explicitly approved.

## Implementation status

Implemented locally as an optional provider-neutral host adapter, separate from the unchanged Task 33C lock, and hardened after adversarial review. The host validates the exact compact DocAtlas shape before retention, rejects raw fields, normalizes shell aliases before test accounting, treats repeated `edit` actions as repairs, rejects unknown actions, and requires an initial patch attempt before success. The 1/12/7,000/1/2/32,768 profile limits remain hard. Output capture uses one global byte ceiling including diff data; adapters receive that ceiling before both DocAtlas delivery and action execution can return materialized output. Dynamic tool removal is verified against the next actual catalog; truncated-output capability remains unverified without a complete content hash. The fake adapter proves only this local contract; real-model savings remain a later evidence gate.

## Problem

A compact MCP response does not bound cumulative session tokens. Coding clients can resend the tool catalog, old shell output, successful test logs, repeated retrieval results, and the full conversation on every model request. The server cannot force an arbitrary MCP client to remove tools or compact its history after a successful call.

The bounded-direct exploratory signal therefore identifies only part of the problem. Reaching a complete-session budget requires an optional client/host capability with explicit request, history, repair, and test-run limits.

## Goal

Define and implement a provider-neutral local agent-loop adapter that lets the coding model initiate exactly one DocAtlas call, then retains only the minimal state needed to finish the patch.

This remains Context7-like interaction:

```text
model requests get_docs_context once
→ host executes the compact MCP call
→ host validates the result
→ DocAtlas tool is no longer exposed for later turns
→ model edits/tests under a bounded retained history
```

It is not host-prefetch before the model's decision and it does not require a second model/subagent.

## Capability boundary

The adapter must report whether it can prove:

- one successful pre-edit DocAtlas call;
- removal/disablement of DocAtlas tools after success;
- a hard maximum model-request count;
- a hard per-request serialized input ceiling;
- bounded tool output capture;
- bounded repair passes and test invocations;
- deterministic history compaction with hashes of omitted content;
- provider usage fields when a provider exposes them.

A generic MCP client that cannot prove these controls remains supported, but it must not claim the one-call bounded-loop capability.

## Retained state contract

After the DocAtlas result is accepted, active history should retain only:

1. canonical user objective and immutable task ID/hash when supplied by a host;
2. the validated compact DocAtlas result;
3. a bounded current action-state summary;
4. the current diff or a bounded diff summary plus hash;
5. the most recent failing test/compile output needed for repair;
6. concise results of completed actions.

Remove or replace with deterministic summaries:

- previous `rg`, `find`, `cat`, and directory-listing output;
- successful full test logs;
- superseded failures;
- repeated tool schemas/results;
- old file contents already represented by the current diff/state;
- debug/diagnostic payloads not needed for the next action.

Every omitted block must have a content hash and reason in a host-side audit record. Omitted text does not need to remain in the model prompt.

## Budget profile

Define versioned profiles rather than hard-coding one universal product limit. The first engineering profile should include:

```yaml
max_docatlas_calls: 1
max_model_requests: 12
max_serialized_input_tokens_per_request: 7000
max_repair_passes: 1
max_test_invocations: 2
max_tool_output_bytes_per_call: 32768
```

These values are an engineering profile to test locally with fake adapters. They must not silently modify `task33c_protocol.lock.json`, whose existing request budget remains frozen for comparability.

Exceeding a hard limit produces a typed incomplete/budget-exhausted result, never a normal success.

## Fail-closed behavior

- `insufficient_evidence` stops before edits;
- a second DocAtlas call is rejected after a successful first call;
- oversized tool output is truncated during streaming/capture, not after unbounded buffering;
- a third test invocation is rejected or requires an explicitly different profile;
- request-history fitting preserves objective, compact context, current diff, and latest failure before optional prose;
- missing provider usage remains unavailable and cannot be replaced by local byte estimates.

## Required work

1. Define a provider-neutral adapter interface and capability record.
2. Implement the one-call DocAtlas state machine with `not_called`, `accepted`, `insufficient`, and `failed` terminal states.
3. Remove/disable DocAtlas tools after an accepted call when the host supports dynamic tool exposure.
4. Add deterministic retained-history construction and omitted-content hashing.
5. Add bounded stdout/stderr/tool-result capture.
6. Enforce versioned request, repair, and test-run budgets.
7. Use Task 34 command normalization for test/error/retry counters.
8. Persist a sanitized audit artifact containing budgets, counts, compaction hashes, and terminal reason but no credentials or raw private provider events.
9. Build a fake deterministic model/tool adapter that exercises normal, retry, repeated-MCP, oversized-output, and budget-exhaustion paths without provider calls.
10. Document which existing clients can and cannot prove the capability.

## Local verification matrix

Provider-free tests must cover:

1. successful one-call patch loop;
2. `insufficient_evidence` before any edit;
3. attempted second DocAtlas call;
4. 13th model request under the 12-request profile;
5. second repair versus forbidden third logical attempt;
6. third test invocation;
7. oversized stdout and stderr;
8. repeated failed shell command fingerprint;
9. deterministic compaction for identical histories;
10. secret-like input absent from sanitized audit artifacts.

## Expected implementation areas

- a new optional host/loop module under `eval/task_level/` or a clearly separated integration package
- runner capability types under `eval/task_level/runners/`
- Task 34 metrics/normalization helpers
- local fake adapters and focused tests
- user/developer documentation describing capability limits

Do not put provider credentials or a required model runtime inside the core MCP server.

## Local verification

```bash
uv run pytest tests/task_level/test_one_call_agent_loop.py
uv run pytest tests/task_level/test_runner_adapter.py tests/task_level/test_task_level_harness.py
uv run pytest tests/docs/test_mcp_token_footprint.py
uv run python -m compileall docmancer eval/task_level
git diff --check
```

The test suite must use fake adapters and local subprocess fixtures. No benchmark, paid API, GitHub Models, or GitHub Actions run is required.

## Later evidence gate

After benchmark execution becomes available, compare at minimum:

- repo-only versus compact agent-called MCP;
- correctness/hidden score;
- cumulative input/output and uncached input;
- tool-catalog contribution;
- MCP visible-response contribution;
- shell failures/retries/test invocations;
- latency and time to first edit.

Until then, this task may claim only that hard local budgets are enforced under tested fake-adapter histories. It may not claim a percentage reduction on a real model.

## Acceptance criteria

- The model can initiate one compact DocAtlas call and cannot successfully call it twice in the bounded profile.
- DocAtlas tools are removed/disabled after success when the host advertises that capability.
- Request, input, repair, test, and output limits are hard-enforced and independently tested.
- Retained history contains the objective, compact context, current diff/state, and latest relevant failure without carrying superseded raw output.
- Compaction is deterministic and omitted blocks have hashes/reasons.
- Budget exhaustion and insufficient evidence are typed incomplete outcomes.
- A generic client without these controls is not falsely labelled verified.
- No provider credential or paid request is required for focused tests.
- Focused local tests, `compileall`, and `git diff --check` pass.

## Non-goals

- Do not change the frozen Task 33C protocol in place.
- Do not require this adapter for every third-party MCP client.
- Do not add a compression subagent or recursive delegation.
- Do not make DocAtlas store provider credentials.
- Do not claim real-model savings before a later comparable benchmark.
