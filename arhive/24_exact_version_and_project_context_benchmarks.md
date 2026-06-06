# 24 - Exact-Version and Project-Context Benchmarks

## Goal

Prove that Docmancer is better than Context7 where Docmancer should structurally win.

The claim to prove is not:

> Docmancer is always better at public docs lookup.

The claim to prove is:

> Inside a repo, Docmancer prevents wrong-version and project-context mistakes that Context7-only workflows can make.

## Benchmark lanes

### Lane 1 - Public-doc parity

Keep and expand the saved public-doc suites:

- Riverpod;
- FastAPI;
- pytest;
- React or Next.js;
- one docs.rs crate.

Metrics:

- Hit@1;
- Hit@5;
- MRR;
- snippet relevance@3;
- unique sources@5;
- locale contamination;
- stale/degraded mode visibility.

Purpose: ensure Docmancer is not bad at Context7's core public-doc lane after indexing.

### Lane 2 - Exact-version suites

Fixtures:

- Flutter project pinned to Riverpod 2.x while latest docs include 3.x concepts.
- Rust project pinned to a crate version with API differences from latest.

Metrics:

- exact version selected;
- forbidden version avoided;
- warning emitted for non-exact docs;
- correct API facts for pinned version;
- latest docs listed as rejected/risky when appropriate.

Example failure Context7-only should be able to make:

```text
Project: flutter_riverpod 2.6.1 in pubspec.lock
Task: add provider using project-supported syntax
Context7-only risk: retrieves latest docs and suggests syntax/API from newer docs
Docmancer target: resolves 2.6.1 docs or warns if exact docs unavailable
```

### Lane 3 - Project-context suites

Fixtures:

- repo docs define architecture constraints;
- ADR bans a public-doc-supported pattern;
- wrapper utilities must be used instead of raw library APIs;
- local docs include migration notes not present in public docs.

Metrics:

- project source included;
- dependency source included;
- project constraint applied;
- banned API avoided;
- hallucinated API rate;
- tests passed.

Example:

```text
Project doc: "Do not call HTTP client directly from features; use ApiGateway wrapper."
Public docs: show direct HTTP client usage.
Context7-only risk: implements direct call.
Docmancer target: includes project doc and dependency doc, causing wrapper-based implementation.
```

### Lane 4 - Agent task benchmark

Run the same model with controlled tool access:

- Context7-only;
- Docmancer-only cold;
- Docmancer-only warm;
- both tools available, measuring which one the agent chooses.

Metrics:

- task completion;
- tests passed;
- wrong-version API usage;
- project-rule violation rate;
- number of docs/tool calls;
- total docs tokens;
- wall-clock time;
- correction loops.

## First benchmark slice

Create one small fixture that requires both:

1. a project-owned rule; and
2. an exact dependency doc.

Minimum pass criteria:

- `get_project_context` returns both project and dependency sources;
- Trust Contract lists at least one rejected/risky source;
- Docmancer-only agent follows the local rule;
- Context7-only either misses the rule or uses wrong/latest docs;
- result is saved as reviewable artifact.

## Acceptance criteria

- Benchmarks make the product wedge visible to a reviewer.
- Scores are not only retrieval metrics; they include task-level correctness.
- Setup cost is measured separately for cold and warm Docmancer runs.
- Remaining Context7 advantages are documented honestly.

## Non-goals

- Do not overfit ranking to one fixture.
- Do not claim global superiority from a small benchmark.
- Do not hide cases where Context7 is still better for quick public-doc lookup.
