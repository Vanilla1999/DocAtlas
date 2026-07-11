# Task 24 — define a lean primary install profile

## Priority

P2 cost and onboarding, after the release artifact gate.

## Problem

The default package installs vector clients/embedders and PDF, DOCX, and RTF processing even when a user needs only local Markdown, SQLite/lexical retrieval, and the three-tool Docs MCP flow. The cost has not been measured, so extras cannot be split safely by intuition.

## Goal

Measure the installed product and make the smallest supported Docs MCP profile the default without breaking explicit advanced use cases.

## Required changes

1. Measure clean cold install time, downloaded/installed bytes, dependency count, first CLI startup, first MCP startup, and idle memory for the current package.
2. Map every direct dependency to the core Docs flow, an advanced surface, or development only. Record import sites and whether imports are eager.
3. Define and test a core profile for local Markdown/project docs, exact dependency metadata, SQLite/lexical retrieval, and stdio MCP.
4. Move heavy vector, browser, and document-format features to named extras when the measurements and import boundaries permit it.
5. When an optional feature is invoked without its extra, return one actionable install command; never fail core startup during import.
6. Keep a compatibility extra that installs the previous all-features dependency set for existing users.
7. Make the installer select/pin a profile explicitly and verify the primary MCP handshake after installation.
8. Commit before/after measurements produced from clean environments. The core profile must reduce clean installed bytes and direct+transitive dependency count by at least 30% versus the recorded baseline, while median first MCP startup may regress by no more than 10% across five runs.

## Non-goals

- Do not remove features solely to improve an install-size number.
- Do not replace retrieval algorithms in this task.
- Do not make optional imports silently change answer semantics without reporting the active backend.

## Acceptance criteria

- Every default dependency has a documented core justification; all others are optional or explicitly retained with evidence.
- Core installation passes the task 15 wheel/MCP smoke without advanced extras.
- Missing optional features fail with a stable actionable message.
- Existing all-features users have a documented compatible install path.
- Clean-environment measurements meet the >=30% installed-size/dependency-count reduction and <=10% first-startup regression budgets; `git diff --check` passes.
