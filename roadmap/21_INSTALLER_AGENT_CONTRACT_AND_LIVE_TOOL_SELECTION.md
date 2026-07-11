# Task 21 — install one agent contract and prove tool selection

## Priority

P0/P1 adoption. Complete after task 11 and before task 15, so the release artifact smoke covers the installed canonical contract.

## Problem

`doc-atlas install <agent> --project` can generate a compact bootstrap, but the hero installer only registers MCP and asks the user to prompt the agent manually. Installed/global skill text and Copilot/wiki guidance can still lead with legacy CLI/direct-tool flows. Existing tool-selection tests exercise a deterministic helper, not an actual weaker model reading real tool descriptions.

## Goal

Every supported installer should leave the coding agent with one compact, consistent workflow and measurable first-tool behavior.

## Canonical contract

The installed guidance must say, in client-appropriate syntax:

1. Call `get_docs_context` first for project or dependency documentation questions.
2. If it returns `next_action`, request any required network/write confirmation and call the exact `prepare_docs` action.
3. Poll `docs_status` only for a returned job id.
4. Repeat the original `get_docs_context` question after successful preparation.
5. Prefer repository code/search for implementation facts and DocAtlas for documentation context; do not use legacy direct tools.

## Required changes

1. Make the supported one-line/project installer invoke the same bootstrap generator after MCP registration, or print one explicit command when automatic file mutation is not allowed.
2. Generate client-specific files idempotently with begin/end markers. Preserve unrelated user instructions and support clean update/uninstall.
3. Remove absolute developer paths and legacy-first flows from all active installed templates and supported client instructions.
4. Keep the canonical wording in one source and render adapters from it to prevent drift.
5. Add static contract tests over every generated/committed instruction file.
6. Add a tool-choice evaluation runner that presents the actual public tool schemas plus installed guidance to at least one named weaker/low-cost model adapter.
7. Cover scenarios for local docs present/missing/stale, exact library present/missing, job polling, implementation-only code search, network confirmation, invalid prepare payload, and unrelated questions.
8. Commit sanitized per-scenario results and model/tool-schema versions. Keep live evaluation opt-in; deterministic schema/fixture tests remain in CI.

## Decision metrics

- first-tool accuracy;
- unnecessary prepare/status rate;
- legacy-tool hallucination rate;
- exact next-action argument-copy accuracy;
- original-question retry rate after preparation.

Use at least 20 scenarios with three repeats. Freeze thresholds before the first live run: first-tool accuracy >=95%, unnecessary prepare/status rate <=5%, legacy-tool hallucination rate 0%, exact next-action argument-copy accuracy >=95%, and original-question retry rate >=95%. A failure changes guidance/schema or is reported as a failed gate; it must not be hidden by excluding scenarios.

## Non-goals

- Do not force DocAtlas for implementation facts already answered by code.
- Do not overwrite arbitrary agent files.
- Do not add another public tool.

## Acceptance criteria

- A fresh supported install produces both working MCP registration and compact project guidance.
- Reinstall/update is idempotent and uninstall removes only managed blocks/files.
- No active installed instruction mentions legacy direct tools as the default.
- Static cases pass in CI and the opt-in weaker-model report meets predeclared thresholds or explicitly records failure.
- Installer tests and `git diff --check` pass.
