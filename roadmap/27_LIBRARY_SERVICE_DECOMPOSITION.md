# Task 27 — decompose the external library application service

## Priority

P2 architecture. Complete only after tasks 11–18 stabilize behavior.

## Problem

`library_docs_service.py` mixes request validation, source resolution, crawl orchestration, job/deadline control, staging publication, registry state, and query behavior in one very large module. A weaker model must load unrelated branches and broad exception paths to change one lifecycle rule.

## Goal

Extract one coherent ingest orchestration boundary while preserving the public MCP/application behavior exactly.

## Preparation

1. Freeze a behavioral characterization suite for validation responses, job transitions, partial/success/failure publication, retry, cancellation/deadline, and repeated queries.
2. Record the existing public method signatures and serialized response snapshots.
3. Run mutation/spies that prove staging is published only through the tested commit boundary.

## Required change

1. Extract the library ingest/job orchestration from `LibraryDocsApplicationService` into one application component with explicit ports for:
   - source resolution/fetch;
   - extraction/index staging;
   - lease/deadline/job state;
   - atomic publication.
2. Keep query/read behavior in the existing facade or a separate read component, but do not redesign ranking.
3. Replace broad cross-layer exception handling at the extracted boundary with the stable error taxonomy from tasks 12, 14, and 30.
4. Make dependencies constructor-injected so deterministic transports, clocks, executors, and stores are testable without monkeypatching globals.
5. Keep compatibility entrypoints delegating through the same component; do not duplicate orchestration.
6. Set a module budget: no extracted application module should exceed 700 lines without a documented exception, and the facade should visibly shrink.

## Non-goals

- Do not change public response schemas or tool names.
- Do not add features, ecosystems, ranking changes, or cache formats.
- Do not combine CLI or project-doc service refactors.

## Acceptance criteria

- Characterization snapshots are unchanged except for explicitly approved internal diagnostic fields.
- There is one job/commit orchestration path for public and compatibility entrypoints.
- Tests can inject clock, executor, fetcher, and store without real network or sleeps.
- The original service loses the extracted responsibilities and meets the stated module budget or records a narrowly justified residual.
- Full related suites and `git diff --check` pass.
