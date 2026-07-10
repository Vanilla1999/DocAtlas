# Task 02 — make agent bootstrap automatic and compact

## Problem

`doc-atlas agent-contract` exists, but a coding agent does not necessarily run it when it first opens a repository. Tool availability alone is not sufficient: existing task-level experiments showed zero optional adoption in some runs.

## Goal

After `doc-atlas install <agent> --project`, the agent immediately knows the three-tool workflow without the user manually running another command.

## Required behavior

1. Project installation writes or updates one bounded managed instruction block for supported agents.
2. The block contains only:
   - explicit status/health request → `docs_status`;
   - normal project/library/dependency question → `get_docs_context`;
   - `prepare_docs` only from returned `next_action` or explicit sync/refresh/index request;
   - repository docs prove conventions, dependency docs prove external APIs, code proves current implementation.
3. Do not inject the full dependency list or documentation inventory into every prompt. Those remain available through `agent-contract` and `get_docs_context`.
4. Re-running install updates the managed block idempotently and preserves user-authored text outside it.

## Files to inspect first

- `docmancer/cli/commands.py`
- `docmancer/mcp/agent_config.py`
- `docmancer/templates/`
- `AGENTS.md`
- `tests/test_install_cmd.py`
- `tests/test_mcp_agent_config.py`

## Non-goals

- Do not add a fourth public MCP tool.
- Do not automatically crawl the network.
- Do not place a full generated project contract in `AGENTS.md`.
- Do not overwrite user instructions.

## Tests

Add cases for Codex/AGENTS, Claude Code, Cursor, Copilot, and OpenCode where supported. Test first install, repeated install, update of an old managed block, and preservation of surrounding content.

## Acceptance criteria

- A fresh project install gives an agent the correct first-tool rule.
- Install is idempotent.
- Managed guidance stays under 250 words.
- Existing config and installer smoke tests pass.
