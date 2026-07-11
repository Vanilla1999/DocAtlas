# Task 22 — close the change-aware documentation maintenance loop

## Priority

P1 core product goal.

## Product decision

DocAtlas indexes documentation; it does not silently author official project files. The host coding model may create a normal reviewable Git patch using DocAtlas's bounded evidence and impact output. DocAtlas then indexes only the accepted repository files.

## Problem

The pieces exist separately: code changes can produce an impact report, missing docs can produce a model handoff, and `prepare_docs(sync_project_docs)` can reindex. There is no coherent incremental workflow connecting those pieces, so users must remember when and what to update.

## Goal

Turn a code diff into a compact documentation-update brief, then incrementally reindex accepted documentation changes without a fourth MCP tool.

## Required workflow

1. Given a base/head Git diff, call the section-impact application path from task 20.
2. Return a bounded authoring brief for the host model containing:
   - changed paths/symbols and evidence;
   - affected authoritative document sections;
   - facts that must be verified in code/config/tests;
   - missing evidence and claims that must not be invented;
   - exact files/sections allowed to edit;
   - the existing `prepare_docs(sync_project_docs)` follow-up.
3. Never write Markdown in the DocAtlas service. The host agent/user produces a normal Git diff and reviews it.
4. Extend sync to accept changed/deleted/renamed documentation paths and update only affected derived rows/chunks.
5. Make sync idempotent by content hash. Unchanged files create no new chunks or vector writes.
6. Remove derived data for accepted deletions and preserve traceable tombstone/status information needed to avoid stale retrieval.
7. Provide an optional local watch/CI mode that reports impact and sync status. It may index already-saved files but must not author, commit, comment, or access network without explicit action.
8. Expose the workflow through the existing three tools and CLI/CI adapters; no fourth public MCP tool.

## Required fixtures

- code change requiring one section update;
- config/lockfile change affecting dependency docs;
- doc rename and deletion;
- unchanged save/idempotent sync;
- code change with insufficient evidence;
- rejected/uncommitted proposed doc patch that must not be treated as accepted truth;
- monorepo diff affecting only one module's docs.

## Metrics

Record impacted-section precision/recall, brief size, files/chunks reprocessed, and end-to-end local latency. Set regression budgets before optimizing.

## Non-goals

- Do not auto-commit, auto-push, or silently modify documentation.
- Do not require a long-running daemon for the basic flow.
- Do not regenerate the entire index for one changed file.

## Acceptance criteria

- A supported code diff produces one evidence-bounded update brief.
- After a reviewed file change, incremental sync updates only changed/deleted/renamed documents.
- Repeating sync with unchanged content performs zero derived writes.
- Stale deleted content is no longer retrieved.
- The public MCP inventory remains exactly three.
- Integration tests, metric fixture, and `git diff --check` pass.
