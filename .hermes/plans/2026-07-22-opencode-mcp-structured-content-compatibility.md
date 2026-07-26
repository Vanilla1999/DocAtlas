# OpenCode MCP Structured-Content Compatibility Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. Treat this as a bounded prerequisite to further OpenCode/real-agent DocAtlas validation.

**Goal:** Make DocAtlas responses model-visible in supported OpenCode clients without duplicating payloads, and ensure project-only retrieval with zero indexed project docs recommends confirmed `sync_project_docs` rather than dependency prefetch.

**Architecture:** Keep `structuredContent` as the default canonical MCP transport. Configure OpenCode registrations to use the existing server-owned text-only compatibility mode (`DOCATLAS_MCP_TEXT_FALLBACK=1`) until OpenCode demonstrably preserves `structuredContent`. Preserve the one-channel invariant: structured clients receive marker + structured payload; text-only clients receive JSON text and no structured payload. Fix project recovery ordering independently so missing project-doc index state is resolved before dependency-doc preparation.

**Tech Stack:** Python 3.12+, MCP Python SDK, pytest, OpenCode JSON/JSONC configuration, POSIX installer shell.

---

## Evidence and problem statement

Reproduced on 2026-07-22 with OpenCode `1.18.4` and the NBO project:

- DocAtlas returned a complete `structuredContent` payload, while `content[0].text` contained only `Structured DocAtlas result attached in structuredContent.`.
- OpenCode persisted only that marker in `part.state.output`; neither `state.metadata` nor top-level metadata retained the structured payload.
- The model therefore could not observe `status`, `reason_code`, `missing`, source evidence, or `recommended_next_action`.
- With `DOCATLAS_MCP_TEXT_FALLBACK=1`, the same provider-free stdio call produced parseable JSON in `content`, omitted `structuredContent`, and exposed `reason_code=project_docs_preflight_confirmation_required`.
- NBO project status reported 38 discovered project-doc candidates and 0 indexed candidates, with placeholder risk for `packages/scan_doc/README.md`; no sync was performed.
- `docs_status(action="project")` correctly pointed to confirmed `sync_project_docs`, while one `get_docs_context(mode="project")` response recommended `prefetch_project_dependency_docs`. Project-index recovery must win for explicit project mode.

Relevant existing contracts:

- `docmancer/mcp/docs_server.py:1251-1274,1319-1329`
- `docmancer/mcp/agent_config.py:70-105,149-152`
- `scripts/install.sh:210-307`
- `scripts/docs_mcp_stdio_smoke.py:20-27,45-61`
- `tests/test_mcp_agent_config.py:146-177`
- `tests/test_release_gate.py:59-79`
- `docmancer/docs/application/unified_context_service.py:191-205`
- `tests/test_unified_docs_context.py:825-857`
- `tests/test_unified_docs_context_mcp.py:222-247`

## Execution status

| Task | Status | Gate |
| --- | --- | --- |
| 1. Freeze the OpenCode model-visible transport regression | not started | RED proves generated OpenCode config and a text-only client cannot currently consume the payload. |
| 2. Register OpenCode with text-only fallback | not started | Generated and migrated OpenCode entries preserve user settings and set the compatibility environment. |
| 3. Add provider-free generated-config transport smoke | not started | Exact generated command/environment returns JSON through `content` with no duplicate structured payload. |
| 4. Correct project-index recovery ordering | not started | Explicit project mode with discovered-but-unindexed docs recommends confirmed `sync_project_docs`, never dependency prefetch as the primary action. |
| 5. Documentation, affected regression, and NBO validation | not started | Focused suites pass; NBO status becomes model-visible. Any NBO sync remains confirmation-gated. |

## Scope boundaries

In scope:

- OpenCode registration produced by Python setup and `scripts/install.sh`.
- Safe migration of an existing same-command OpenCode MCP entry.
- Provider-free text-only MCP smoke through the generated config contract.
- Project-only recovery priority when project docs are discovered but unavailable/unindexed.
- README/MCP server documentation and release tests.

Out of scope:

- Changing the default transport for clients that support `structuredContent`.
- Sending the full payload through both text and structured channels.
- Detecting client capability from model behavior.
- Modifying OpenCode itself; an upstream issue may be filed separately and must not block the local compatibility fix.
- Automatically syncing NBO docs, accepting placeholder docs, or enabling network access.
- Reopening natural-language evidence selection, snippet ranking, or retrieval semantics.

---

### Task 1: Freeze the OpenCode model-visible transport regression

**Objective:** Add failing characterization tests for the exact supported-client contract before changing registration code.

**Files:**

- Modify: `tests/test_mcp_agent_config.py`
- Modify: `tests/test_release_gate.py`
- Reference: `docmancer/mcp/agent_config.py`
- Reference: `scripts/install.sh`

**Step 1: Add RED registration assertions**

Extend the OpenCode registration tests to require this server entry shape:

```json
{
  "type": "local",
  "command": ["doc-atlas", "mcp", "docs-serve"],
  "enabled": true,
  "environment": {
    "DOCATLAS_MCP_TEXT_FALLBACK": "1"
  }
}
```

Add separate cases proving:

1. A fresh OpenCode config receives the fallback variable.
2. An existing same-command entry with unrelated `environment` keys keeps those keys.
3. An existing explicit `DOCATLAS_MCP_TEXT_FALLBACK` value is normalized to `"1"` for the supported OpenCode entry.
4. Re-registration is idempotent.
5. A different command remains fail-closed and is not overwritten.

**Step 2: Add RED installer assertions**

In `tests/test_release_gate.py`, require the installer-generated OpenCode entry and its manual fallback instructions to include `DOCATLAS_MCP_TEXT_FALLBACK`.

**Step 3: Run RED**

Run:

```bash
export PATH="$PWD/.venv/bin:$PATH"
pytest -q tests/test_mcp_agent_config.py tests/test_release_gate.py --tb=short
```

Expected: new OpenCode fallback assertions fail against the current config writer; unrelated tests remain green.

---

### Task 2: Register OpenCode with text-only fallback

**Objective:** Make every DocAtlas-managed OpenCode entry use the existing one-channel text compatibility mode without destroying user configuration.

**Files:**

- Modify: `docmancer/mcp/agent_config.py`
- Modify: `scripts/install.sh`
- Test: `tests/test_mcp_agent_config.py`
- Test: `tests/test_release_gate.py`

**Step 1: Centralize the OpenCode compatibility environment**

Define one Python constant for the required OpenCode server environment:

```python
OPENCODE_MCP_ENVIRONMENT = {"DOCATLAS_MCP_TEXT_FALLBACK": "1"}
```

Use it in the fresh desired entry, current-entry comparison, and migration logic. Do not add the fallback to Claude Code, Codex, or generic MCP targets without separate compatibility evidence.

**Step 2: Merge rather than replace existing environment**

For an existing same-command OpenCode entry:

- preserve unrelated top-level keys;
- preserve unrelated environment variables such as `DOCMANCER_TASK_LEVEL_ALLOW_NETWORK`;
- set `DOCATLAS_MCP_TEXT_FALLBACK` to `"1"`;
- keep `enabled=true`;
- retain the existing different-command refusal.

Update `has_current_server_entry()` and unregister semantics so the managed compatibility key does not make idempotency or cleanup inconsistent.

**Step 3: Update the shell installer**

Change `register_opencode()` in `scripts/install.sh` to generate and migrate the same environment shape. Update the manual JSON example printed on failure. Keep JSONC backup and non-clobber behavior unchanged.

**Step 4: Run GREEN**

Run:

```bash
export PATH="$PWD/.venv/bin:$PATH"
pytest -q tests/test_mcp_agent_config.py tests/test_release_gate.py --tb=short
```

Expected: all tests pass.

---

### Task 3: Add a provider-free generated-config transport smoke

**Objective:** Verify the actual generated OpenCode command/environment from registration through model-visible text, not merely raw MCP SDK `structuredContent` support.

**Files:**

- Modify: `scripts/docs_mcp_stdio_smoke.py`
- Modify: `tests/test_release_gate.py`
- Test: `tests/docs/test_action_packet.py`

**Step 1: Add a text-only payload reader**

Add a helper that deliberately ignores `structuredContent` and parses only `content[0].text`. This models OpenCode 1.18.4 behavior.

**Step 2: Exercise the generated OpenCode contract**

In a temporary HOME/config:

1. Generate/register the OpenCode server entry.
2. Start the exact configured command with its merged environment.
3. Sync only the temporary fixture project used by the existing smoke.
4. Call `get_docs_context`.
5. Parse only text content.
6. Assert the fixture source path and invariant are present.
7. Assert `structuredContent` is absent in fallback mode.
8. Assert the marker is not the model-visible output.

No provider, API key, network request, OpenCode model call, or real user project mutation is allowed.

**Step 3: Preserve the no-duplication contract**

Retain the existing default-mode test proving marker + structured payload. Retain the fallback-mode test proving JSON text + no structured payload. Both transport lanes must stay bounded to one complete payload.

**Step 4: Run smoke tests**

Run:

```bash
export PATH="$PWD/.venv/bin:$PATH"
pytest -q tests/test_release_gate.py tests/docs/test_action_packet.py --tb=short
python scripts/docs_mcp_stdio_smoke.py
```

Expected: provider-free PASS; text-only lane exposes cited fixture content.

---

### Task 4: Correct project-index recovery ordering

**Objective:** Ensure explicit project mode repairs unavailable project-doc evidence before suggesting dependency-doc preparation.

**Files:**

- Modify: `docmancer/docs/application/unified_context_service.py`
- Modify if projection mapping requires it: `docmancer/docs/interfaces/mcp/context_tools.py`
- Test: `tests/test_unified_docs_context.py`
- Test: `tests/test_unified_docs_context_mcp.py`
- Test: `tests/docs/test_model_visible_projection.py`

**Step 1: Add RED project-only recovery tests**

Create a fake project state with:

- project docs discovered;
- indexed/current count equal to zero;
- preflight confirmation required;
- `tool_after_confirmation="sync_project_docs"`;
- dependency metadata present, so an incorrect implementation could choose dependency prefetch.

Assert that `get_docs_context(mode="project")` returns:

```json
{
  "status": "insufficient_evidence",
  "recommended_next_action": {
    "tool": "prepare_docs",
    "arguments_patch": {
      "action": "sync_project_docs",
      "project_path": "/repo"
    },
    "requires_confirmation": true
  }
}
```

Also assert that `prefetch_project_dependency_docs` is not the primary action and that no sync executes automatically.

**Step 2: Preserve non-blocking partial context**

Keep the existing behavior when usable indexed project context exists despite preflight risk: return bounded partial project context and do not blindly sync. The new priority applies only when project evidence is unavailable or insufficient.

**Step 3: Preserve dependency and mixed modes**

Add/retain cases proving:

- explicit dependency mode may recommend `prefetch_project_dependency_docs`;
- mixed mode may retain dependency preparation as a later action after project-index recovery;
- project mode never promotes dependency prefetch above missing project-doc index recovery.

**Step 4: Implement minimal recovery priority**

Carry the typed project preflight action through unified context and MCP projection. Select `sync_project_docs` as the primary confirmed recovery action when the project lane cannot answer because project docs are unindexed. Do not infer recovery from free-form message text.

**Step 5: Run GREEN**

Run:

```bash
export PATH="$PWD/.venv/bin:$PATH"
pytest -q tests/test_unified_docs_context.py tests/test_unified_docs_context_mcp.py tests/docs/test_model_visible_projection.py --tb=short
```

Expected: all tests pass, including existing dependency/mixed routing behavior.

---

### Task 5: Documentation, affected regression, and NBO validation

**Objective:** Document the compatibility contract, run affected gates, and verify that NBO diagnostics are visible without mutating NBO.

**Files:**

- Modify: `README.md`
- Modify: `docs/mcp-docs-server.md`
- Update: `.hermes/plans/2026-07-22-opencode-mcp-structured-content-compatibility.md`
- Update after review evidence only: `.hermes/reviews/2026-07-21-natural-language-library-retrieval-review.md`

**Step 1: Document automatic OpenCode compatibility**

State explicitly:

- OpenCode registration currently enables text fallback because OpenCode 1.18.4 does not preserve structured payloads in model-visible tool output.
- Other structured clients retain the default marker + `structuredContent` lane.
- Users with manual OpenCode configs must set `DOCATLAS_MCP_TEXT_FALLBACK=1` until capability is verified.
- Full payload duplication remains forbidden.

**Step 2: Run affected verification**

Run:

```bash
export PATH="$PWD/.venv/bin:$PATH"
pytest -q \
  tests/test_mcp_agent_config.py \
  tests/test_release_gate.py \
  tests/docs/test_action_packet.py \
  tests/docs/test_mcp_token_footprint.py \
  tests/test_unified_docs_context.py \
  tests/test_unified_docs_context_mcp.py \
  tests/docs/test_model_visible_projection.py \
  --tb=short
git diff --check
```

Then run the project full suite as a diagnostic. Record every residual failure; do not relabel unrelated known failures as green.

**Step 3: Validate NBO read-only visibility**

Using the generated OpenCode fallback environment, call only:

```text
docs_status(action="project", project_path="/home/viadmin/StudioProjects/nbo")
get_docs_context(mode="project", question=<one atomic question>, project_path="/home/viadmin/StudioProjects/nbo")
```

Acceptance:

- model-visible output is parseable JSON, not the marker;
- project status exposes discovered/indexed counts and preflight risk;
- project-only recovery points to confirmed `sync_project_docs`;
- no sync, prefetch, network request, or NBO file write occurs.

**Step 4: Keep NBO preparation confirmation-gated**

Only after explicit user confirmation may a later session call:

```text
prepare_docs(action="sync_project_docs", project_path="/home/viadmin/StudioProjects/nbo", dry_run=false)
```

After confirmed sync, retry a small set of atomic project questions. This mutation is not part of the provider-free compatibility acceptance gate.

**Step 5: Review and commit boundary**

Request read-only exact-HEAD review for:

- one-channel transport correctness;
- OpenCode config preservation/idempotency;
- generated-config smoke realism;
- project-vs-dependency recovery ordering;
- absence of NBO mutation.

Commit only the bounded transport/recovery paths after tests and review pass. Do not include existing dirty natural-language retrieval baseline paths.

---

## Acceptance criteria

The block is complete only when all are true:

1. Fresh and migrated OpenCode registrations set `DOCATLAS_MCP_TEXT_FALLBACK=1` and preserve unrelated user configuration.
2. Default structured clients still receive one structured payload plus a constant marker.
3. OpenCode/text-only clients receive one JSON text payload and no `structuredContent` duplicate.
4. A provider-free generated-config stdio smoke proves cited content is visible through text only.
5. Explicit project mode with discovered-but-unindexed project docs recommends confirmed `sync_project_docs` before dependency prefetch.
6. Dependency and mixed-mode recovery behavior remains covered and intentional.
7. NBO read-only repro exposes structured diagnostics to the model; NBO sync remains unexecuted without confirmation.
8. Focused and affected suites pass, `git diff --check` passes, and full-suite residuals are recorded truthfully.

## Rollback

- Registration rollback: remove only the managed `DOCATLAS_MCP_TEXT_FALLBACK` environment key from OpenCode entries; preserve unrelated environment/config keys.
- Server transport rollback is unnecessary because the existing default structured lane is not changed.
- Recovery rollback: revert only project-index action priority; do not change dependency retrieval or natural-language evidence semantics.

## Ordered execution

1. Freeze registration/installer RED tests.
2. Implement OpenCode environment merge and migration.
3. Add and pass generated-config text-only smoke.
4. Freeze project-index recovery RED tests.
5. Implement typed project recovery priority.
6. Run affected/full diagnostics and read-only NBO repro.
7. Update evidence ledger and obtain exact-HEAD review.
8. File an optional upstream OpenCode `structuredContent` issue separately; do not block local closure on it.
