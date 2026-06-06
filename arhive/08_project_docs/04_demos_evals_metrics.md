# 08.04 — Demos, Evals, Metrics

## 60-day follow-up

After first-class project docs workflow:

1. Rename/clarify `prefetch_project_docs` semantics if needed:
   - current meaning: dependency docs from project metadata;
   - possible alias: `prefetch_project_dependency_docs`.
2. Harden Flutter/Dart project dependency docs.
3. Add Rust/docs.rs pilot for exact dependency docs.
4. Allow `get_project_docs(..., include_dependency_docs=true)` with clear source classes.
5. Add local-only memory as explicitly separate source class, if still needed.

## 90-day demos

### Demo 1 — Docmancer on Docmancer

Index README/wiki/roadmap/product brief and ask:

```text
What should Docmancer build next to become better than Context7?
```

Expected:

- cites project-owned files;
- distinguishes old roadmap from new wedge;
- no WebFetch.

### Demo 2 — Flutter project exact dependency docs

Given a Flutter repo with `pubspec.lock`, ask:

```text
How should this project use go_router redirects?
```

Expected:

- uses exact `go_router` version docs;
- shows `docs_snapshot_exact`;
- cites pub.dev/Dartdoc source.

### Demo 3 — Private architecture + public dependency answer

Ask:

```text
Implement feature X following this repo's architecture and the exact package docs.
```

Expected:

- combines `project_file` sources and `dependency_docs` sources;
- clearly labels trust/source classes;
- compact context pack fits budget.

### Demo 4 — User thinks Docmancer is just Context7

User says:

```text
Use Docmancer here. It is like Context7, right?
```

Expected agent behavior:

- calls or suggests `inspect_project_docs` first;
- explains that Docmancer can index local project docs and exact dependency docs;
- asks before network dependency docs fetch;
- offers `ingest_project_docs` for local docs;
- does not limit itself to `get_library_docs`.

## Metrics

Primary:

- median MCP calls to useful project-docs answer;
- project docs success rate;
- stale/missing docs remediation success rate;
- direct WebFetch fallback rate for project-owned docs;
- source attribution accuracy;
- project-scoped retrieval isolation;
- discovery-first activation rate: how often agent starts with `inspect_project_docs` when user asks to use Docmancer in a repo.

Secondary:

- token compression ratio;
- Hit@5/MRR on project docs eval set;
- time-to-first-project-docs-answer;
- number of demos that work from clean setup;
- percentage of missing-docs responses with machine-readable next actions.

Suggested initial targets:

- `get_project_docs` happy path in <= 2 MCP calls after setup;
- 0 direct WebFetch recommendations when project docs are indexed;
- 100% source_class present in project docs responses;
- no source-code/dependency directories ingested by default project docs discovery;
- Hit@5 baseline established before optimizing retrieval;
- 100% of `project_docs_not_indexed` responses include `inspect_project_docs` / `ingest_project_docs` remediation.

## Riverpod dependency-docs benchmark

The Riverpod RiverEval is the first concrete dependency-docs benchmark for the project-aware lane:

- dataset: `eval/riverpod_golden.yaml`;
- Docmancer output: `eval/results/docmancer_riverpod_results.json`;
- comparison report: `eval/riverpod_benchmark_report.md`.

Findings relevant to project-aware dependency docs:

- Docmancer was close on public guide retrieval (`Hit@1=0.8`, `MRR=0.8`) but lost to Context7 on corpus cleanliness and snippet presentation.
- The benchmark did not yet prove the exact-version advantage because it indexed `riverpod.dev` latest, not exact Pub Dartdoc pages for `nbo`'s Riverpod 2.6.x packages.
- To make Docmancer structurally better than Context7 for Flutter projects, the next iteration must combine:
  - clean docs ingest (no locale mirrors by default);
  - exact Pub package docs from `pubspec.lock`;
  - project-owned docs (`ARCHITECTURE.md`, ADRs, README) in the same answer path;
  - source-class/version attribution in context packs.

Follow-up roadmap: [`../09_riverpod_context7_benchmark_followups.md`](../09_riverpod_context7_benchmark_followups.md).
