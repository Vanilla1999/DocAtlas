# Task 19 — make project-document evidence complete and authoritative

## Priority

P1 local-project quality.

## Implementation status

Done for the bounded local Task 19 scope. Documentation gaps are evaluated per required
section from parsed production evidence; aggregate completeness fails closed whenever one
section is partial or missing. The reviewable catalog supports exact documents, configured
monorepo roots, and optional local index graphs with repository containment, symlink,
traversal, loop, and work-count bounds. Authority and lifecycle metadata keep completed or
superseded plans out of ordinary retrieval while preserving explicit history search. The
coding-model handoff retains missing-evidence and sync/retry actions within a deterministic
12 KiB serialized ceiling and reports omissions.

Evidence: `tests/docs/test_project_state.py`,
`tests/docs/test_project_evidence_production.py`,
`tests/docs/test_project_docs_catalog.py`, and
`tests/docs/test_task19_project_docs_closure.py`.

## Problem

The missing-doc handoff can set `evidence_complete=true` merely because some evidence was found. A minimal manifest can therefore be presented as enough to document entrypoints, modules, runtime flow, configuration, and tests. Documentation discovery is also tied to a small set of directory names, while roadmap/research prompts can be indexed without a reliable active/completed authority.

## Goal

Tell the coding model exactly which architectural claims are supported, which evidence is missing, and which repository documents are authoritative.

## Required changes

1. Define required evidence categories for each requested documentation section. For example, runtime flow cannot be complete from a package manifest alone.
2. Replace the aggregate boolean shortcut with per-section state:
   - `complete`;
   - `partial`;
   - `missing`;
   - evidence paths and facts;
   - `missing_evidence` categories and bounded discovery suggestions.
3. Set top-level `evidence_complete=true` only when every required section is complete.
4. Let projects configure documentation roots in a reviewable repository file. Support common nested/monorepo roots such as `handbook/`, `guides/`, and `<module>/docs/` without hardcoding every name.
5. Follow an explicit docs index only within repository/root policy; reject path traversal and loops.
6. Add document authority/status metadata: source-of-truth, supporting, generated, roadmap/research, active, completed, superseded, and stale.
7. Prevent completed/superseded roadmap prompts from outranking current architecture/agent instructions. Keep them searchable only when history is requested.
8. Return a compact handoff suitable for a weaker model: inspect only named evidence, do not invent missing claims, edit normal Git files, then call the existing sync action. The serialized handoff must not exceed 12 KiB; truncation keeps missing-evidence and next-action fields and reports omitted counts.

## Required fixtures

- manifest-only project where entrypoint/runtime/test evidence is missing;
- monorepo with `backend/docs` and `frontend/guides`;
- project with `docs/INDEX.md` linking an allowed nested document;
- index traversal/loop rejection;
- completed roadmap task conflicting with current `AGENTS.md`;
- missing one required section while all others are complete.

## Non-goals

- DocAtlas must not author or commit official documentation.
- Do not crawl arbitrary filesystem roots.
- Do not delete historical roadmap files.

## Acceptance criteria

- `evidence_complete` cannot be true while any required section is partial/missing.
- Every missing claim category has an explicit bounded evidence request.
- Configured/nested docs are discovered safely in monorepos.
- Current source-of-truth instructions outrank stale roadmap/research text in retrieval tests.
- Handoff output remains at or below 12 KiB with deterministic priority/truncation behavior.
- Related tests and `git diff --check` pass.
