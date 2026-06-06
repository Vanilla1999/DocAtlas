# 17 — Cross-Index Project + Library Retrieval

## Problem

Docmancer's product wedge is not only public-doc lookup. It should combine project-owned docs with dependency docs so agents can answer questions using both local conventions and external APIs.

Current public-doc benchmarks do not prove that combined retrieval path.

## Goal

Build and benchmark cross-index retrieval across:

- project-owned docs;
- dependency docs;
- registered public docs;
- exact-version package docs.

The target behavior:

> Project docs win when they answer local conventions; library docs win when the query needs API details; combined answers include both when useful.

## Scope

Fixture repository:

- README or docs with local conventions;
- ADR or architecture notes;
- lockfile dependencies;
- benchmark queries requiring project docs, library docs, or both.

Retrieval behavior:

- retrieve from multiple source classes;
- fuse results with source-class-aware RRF;
- expose source class in result metadata and explain output.

## Non-Goals

- Do not ingest source code as project-owned docs in this task.
- Do not require exact-version docs to be fully implemented before testing source-class fusion with available docs.
- Do not bury project docs under public docs when local conventions directly answer the question.

## Implementation Notes

Start with a small fixture and explicit expected source classes.

Example query classes:

- local architecture question answered by project docs;
- API usage question answered by library docs;
- implementation convention question requiring both project docs and library docs.

## Verification

Add benchmark checks for:

- at least one project source when project docs answer the query;
- library docs present when API details are required;
- correct source-class ordering for mixed queries;
- no regression to public-doc-only behavior.

## Success Criteria

- Cross-index retrieval is measurable.
- Result metadata identifies source class.
- Benchmark proves Docmancer's project-aware wedge beyond Context7-style public-doc lookup.

## Current Status

Implemented MVP test in:

- `tests/test_cross_index_retrieval_mvp.py`.

The fixture indexes one project-owned document and one library-doc document in the same local index, then verifies that a mixed query can retrieve both `source_class` values:

- `project_file`;
- `library_docs`.

Verification:

```bash
uv run pytest tests/test_cross_index_retrieval_mvp.py
```

This item is complete for the first measurable cross-index retrieval fixture.

Remaining future work:

- add source-class-aware RRF weighting;
- add benchmark queries that verify source-class ordering, not only presence;
- combine this with exact-version dependency docs once Pub/Cargo suites are end-to-end.
