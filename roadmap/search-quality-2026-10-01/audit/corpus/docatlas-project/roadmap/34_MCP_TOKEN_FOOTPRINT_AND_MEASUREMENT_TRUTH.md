# Task 34 — MCP token footprint and measurement truth

## Priority

P1 efficiency prerequisite. Complete before changing the public MCP response shape or running another paid token comparison.

## Problem

Current evaluation discussions mix several different quantities:

- raw retrieval text processed inside DocAtlas;
- the serialized result visible to the model;
- the static `tools/list` catalog repeated by an MCP client;
- duplicated `content` and `structuredContent` transport bytes;
- cumulative provider input across an entire coding-agent session;
- cached, uncached, reasoning, and output tokens.

These quantities are not interchangeable. A 1,500-token `ActionPacket` does not prove a 1,500-token agent session, and a 200,000-token session does not prove that one MCP response contained 200,000 tokens. The harness also undercounts test commands from runners that normalize shell calls as `Bash`, `Shell`, or `command_execution` rather than `bash.*`.

Without a deterministic local footprint report, later PRs cannot show which boundary they actually improved or prevent token regressions without spending provider tokens.

## Goal

Add a provider-free, deterministic measurement boundary for the public Docs MCP surface and its representative responses. Correct the task-level shell/test counters needed by a future benchmark.

This task measures bytes and deterministic estimates. It does not claim provider-billed token savings, model correctness, or causal product value.

## Measurement contract

Canonical JSON measurement uses:

```python
json.dumps(
    value,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
```

The offline token estimate is `ceil(serialized_utf8_bytes / 4)` and must be named `estimated_tokens`, never `provider_tokens`.

Record at least:

```yaml
schema_version: 1
public_tool_count: 3
mcp_tools_list_bytes: 0
mcp_tools_list_estimated_tokens: 0
tools:
  - name: get_docs_context
    description_bytes: 0
    input_schema_bytes: 0
    output_schema_bytes: 0
    total_bytes: 0
responses:
  - fixture_id: project_patch_ok
    response_kind: patch_context
    raw_retrieval_bytes: 0
    text_content_bytes: 0
    structured_content_bytes: 0
    model_visible_bytes: 0
    model_visible_estimated_tokens: 0
    duplicate_payload_bytes: 0
    largest_fields: []
```

`duplicate_payload_bytes` is non-zero when a text content item contains a JSON representation semantically equal to `structuredContent`. A short marker that refers to structured content is not duplication.

Metrics and diagnostics must be written to a local report, stderr, or test output. They must not be added to the normal model-facing MCP response merely to measure that response.

## Representative local fixtures

Use deterministic in-memory or temporary-directory fixtures; do not call a model, network, GitHub Actions, or a provider API.

Required fixture classes:

1. project coding task with authoritative docs and target source files;
2. library documentation question with one primary and two supporting sources;
3. mixed project/dependency question;
4. `insufficient_evidence` with one bounded recovery action;
5. oversized/adversarial documents with Unicode, repeated text, large metadata, and instruction-like content;
6. compatibility/unbounded response, measured separately and clearly labelled non-default.

Each fixture must retain a stable identifier so before/after reports can be compared in review.

## Required work

1. Add one reusable footprint module under `docmancer/docs/` or `docmancer/mcp/`. It must accept already-built tool/result values and must not instantiate the network/indexing stack.
2. Add a developer-facing CLI or module entry point that writes a JSON report and a short Markdown/table summary. It must exit non-zero when a hard budget is exceeded.
3. Attribute `tools/list` bytes by tool and by description/input/output schema.
4. Attribute response bytes by transport channel and by top-level field. Cap diagnostic field lists so the report itself remains bounded.
5. Detect exact semantic duplication between JSON text content and structured content.
6. Record raw retrieval size separately from the model-visible projection. Do not sum them and call the result provider input.
7. Add regression tests for canonical serialization, Unicode handling, marker handling, semantic duplicate detection, and deterministic ordering.
8. Fix task-level command normalization so `test_runs` recognizes at least:
   - `Bash` with `arguments.command`;
   - `Shell` with `arguments.command`;
   - `command_execution` with its normalized command;
   - existing `bash.*` events.
9. Count and persist separately:
   - `successful_shell_calls`;
   - `failed_shell_calls`;
   - `exec_error_count`;
   - `retried_command_count` when a stable normalized command fingerprint repeats after failure;
   - `pytest_invocations` and other supported test-runner invocations.
10. Keep historical result JSON readable. New fields are additive and absent historical fields remain `null`/unavailable rather than inferred.

## Initial budgets

The first report records the current state before enforcing later compact-surface targets. This task itself enforces only invariants that should already hold:

- exactly three default public Docs MCP tools;
- deterministic report output for identical inputs;
- bounded diagnostic output;
- no secret-like environment values in the report;
- no field labelled as provider usage without provider evidence.

Tasks 35 and 36 own the hard catalog and response byte ceilings.

## Expected implementation areas

- `docmancer/mcp/docs_server.py`
- `docmancer/docs/interfaces/mcp/context_tools.py`
- a new footprint/serialization helper under `docmancer/docs/` or `docmancer/mcp/`
- `eval/task_level/execution.py`
- `eval/task_level/schemas.py` when additive metric fields require it
- focused tests under `tests/docs/` and `tests/task_level/`

## Implementation status on 2026-07-15

- `docmancer.docs.mcp_footprint` produces deterministic JSON and Markdown artifacts from already-built tool/result values without a provider, network call, or service/index instantiation.
- The fetched three-tool baseline is 13,470 serialized bytes, approximately 3,368 estimated tokens. `get_docs_context` accounts for 9,591 bytes, including a 5,620-byte output schema. These are static UTF-8 byte estimates, not provider usage.
- Synthetic characterization fixtures separately expose raw retrieval, text, structured, visible, duplicate, and largest-field measurements. Current bounded fixtures have zero full-payload duplication; compatibility fixtures deliberately record the existing duplication baseline.
- Task-level metrics now normalize `Bash`, `Shell`, `command_execution`, and legacy `bash.*` calls, recognize supported test commands from the command itself, and persist success/failure/unknown, exec-error, retry, and pytest counts.
- A non-zero command exit is recorded as a failed shell call, not an executor failure. `exec_error_count` is reserved for runner/spawn/transport failures where the command did not produce an interpretable exit code.
- Focused tests report `39 passed`; the full provider-free task-level suite reports `305 passed`. `compileall` and `git diff --check` pass. No benchmark or provider API was run.

## Local verification

Run only provider-free checks:

```bash
uv run pytest tests/docs/test_mcp_token_footprint.py
uv run pytest tests/task_level/test_task_level_harness.py tests/task_level/test_runner_adapter.py
uv run python -m compileall docmancer eval/task_level
git diff --check
```

If local dependency provisioning is unavailable, static review may proceed, but the PR must stay draft/unmerged until these focused tests run successfully somewhere trusted. A paid benchmark is not required for this task.

## Acceptance criteria

- A deterministic JSON footprint report covers all three public tools and every required fixture class.
- Raw retrieval, model-visible response, tool catalog, transport duplication, and provider usage are distinct fields with distinct definitions.
- The report identifies exact full-payload duplication without counting a short text marker as duplication.
- No provider, model credential, Docker boundary, or GitHub workflow is required to produce the report.
- `test_runs` correctly counts normalized Codex/Hermes shell commands from fixtures.
- Shell failures, retries, and test invocations are separately observable for future analysis.
- Historical artifacts remain readable and missing metrics remain explicitly unavailable.
- Focused local tests, `compileall`, and `git diff --check` pass.

## Non-goals

- Do not change retrieval ranking, response semantics, public tool schemas, or token ceilings in this PR.
- Do not run or reinterpret Task 33 benchmark cells.
- Do not estimate provider cache behavior from UTF-8 byte counts.
- Do not add measurement fields to the normal model-visible response.
- Do not claim end-to-end savings from a smaller static artifact.
