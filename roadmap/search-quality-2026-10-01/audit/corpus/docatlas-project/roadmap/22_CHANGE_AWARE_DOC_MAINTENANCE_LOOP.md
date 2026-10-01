# Task 22 — close the change-aware documentation maintenance loop

Status: Done for bounded local maintenance scope (`dc102f3`).

## Completion evidence

- The Task 20 impact path emits one bounded `documentation-update-brief-1` handoff with changed paths/symbols, repository facts to verify, explicit missing evidence, a fail-closed edit allow-list, non-invention rules, and the existing `prepare_docs(sync_project_docs)` follow-up.
- Incremental project-doc sync accepts changed, deleted, and renamed paths, validates repository-relative inputs, reprocesses only affected candidates, and scopes vector updates and pruning to affected chunk identities.
- Content-hash identity makes repeated unchanged syncs perform zero file reprocessing, zero derived writes, and zero unrelated-file work.
- Accepted deletions and rename sources are removed from lexical and vector retrieval and return bounded, traceable tombstone diagnostics; unrelated indexed documentation remains available.
- `doc-atlas docs-impact --base ... --head ... --sync-saved-docs` derives lifecycle state from an exact Git diff and rejects dirty or otherwise unaccepted affected paths before indexing. The optional adapter performs no authoring, commits, comments, pushes, or network access.
- The public MCP inventory remains `get_docs_context`, `prepare_docs`, and `docs_status`; incremental sync is an action of `prepare_docs`, not a fourth tool.
- `eval/change_aware/maintenance_eval.json` freezes precision/recall, 8 KiB brief size, 2-second local latency, zero unrelated reprocessing, and zero unchanged derived-write budgets. `tests/docs/test_change_aware_maintenance.py`, `tests/test_docs_service.py`, `tests/test_cli.py`, and MCP contract tests cover the required fixtures and boundaries.

The implementation was merged to `main` in `dc102f387117dad7834db366d123e2f5ee545b51`. This closure audit records the already-verified bounded workflow; it does not authorize DocAtlas to edit official documentation or claim a production-model quality result.

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
