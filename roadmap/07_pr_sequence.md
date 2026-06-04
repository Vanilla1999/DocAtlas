# 07 — Recommended PR Sequence and Milestones

## Guiding rule

Do not start with large schema migrations. Start with failing tests for the live bug, then implement the smallest behavior change that fixes it.

## Milestone 1 — Kill `docs_url` trap

### PR 1 — Failing tests for registered docs without docs_url

Scope:

- Add test fixtures for registered web docs source.
- Assert `get_library_docs({ library, topic })` succeeds without `docs_url`.
- Assert no `needs_docs_url` for registered source.
- Assert unknown source still needs registration/docs_url.

Expected: tests fail before implementation.

### PR 2 — Internal resolver MVP

Scope:

- Extract/introduce resolver used by `get_library_docs`.
- Resolver returns effective source metadata and stored locator.
- Keep current registry schema if possible.

Non-goal: full `source_id`/`canonical_id` migration.

### PR 3 — Refactor get_library_docs

Scope:

- Call resolver first.
- Use stored `docs_url` for unique registered source.
- Restrict `needs_docs_url` to genuine miss.
- Return minimal structured diagnostics.

### PR 4 — Ambiguity and next actions

Scope:

- Candidate response for ambiguous source/version.
- Retry patches.
- Blocking/non-blocking warning objects.

### PR 5 — Agent guidance update

Scope:

- Update tool descriptions.
- Update agent skill templates.
- Add explicit “never WebFetch registered docs before Docmancer retry” guidance.

## Milestone 2 — Registry identity stabilization

### PR 6 — Registry model types

Scope:

- Introduce model-level `source_id`, `canonical_id`, `requested_version`, `resolved_version`, `docs_snapshot_exact`.
- Add parse/render helpers.
- Unit tests.

### PR 7 — DB extension / backfill compatibility

Scope:

- Add nullable/new fields or compatibility view.
- Backfill existing entries.
- Add `legacy_ids`/alias lookup if needed.

### PR 8 — Inspect/list source identity

Scope:

- Make list/inspect expose source/docset status.
- Show stored docs URL, freshness, exactness.

## Milestone 3 — Product narrative and DX

### PR 9 — README split

Scope:

- Hero narrative: local version-aware docs runtime.
- Quickstarts: Local Docs, Versioned MCP Docs, Action Packs.
- Move Packs to advanced/secondary section.

### PR 10 — Doctor action-oriented output MVP

Scope:

- Severity levels.
- Exact remediation commands.
- JSON output if missing.
- Top failure modes.

## Milestone 4 — Project-aware versioning MVP

### PR 11 — Normalized dependency record

Scope:

- Shared parser output type.
- Fixtures.

### PR 12 — Flutter/Dart hardening

Scope:

- Separate version resolution and docs exactness.
- Explicit stable/main handling.

### PR 13 — Rust pilot

Scope:

- Parse Cargo.lock/Cargo.toml.
- docs.rs adapter.
- MCP resolution metadata.

## Milestone 5 — Eval MVP

### PR 14 — Dataset schema and tiny gold set

Scope:

- Taxonomy.
- Dataset JSON schema.
- 20–50 initial queries.

### PR 15 — Offline evaluator MVP

Scope:

- Hit@k / MRR / latency.
- CLI/JSON report.

### PR 16 — Explain trace MVP

Scope:

- `--explain-json` or equivalent artifact.
- Trace schema validation tests.

## Quality gates

### Before merging Milestone 1

- Registered web docs without docs_url test passes.
- Unknown source behavior preserved.
- No direct WebFetch guidance in happy path.

### Before beta

- Registry identity visible in MCP responses.
- README lanes updated.
- Doctor reports top failure modes.
- Eval baseline exists.

### Before GA

- Registered-source success rate target met.
- Version/exactness semantics visible.
- Attribution/version correctness monitored.
- First-run quickstarts validated.

## Open questions before implementation

- What is the current exact DB schema for docs registry?
- Does existing MCP SDK support `structuredContent`, or do we mirror JSON only in text for now?
- Are `inspect_library_docs` and `list_library_docs` already implemented in current code?
- What canonical id format is easiest to support without breaking existing rows?
- Is there already a migration framework in Docmancer?
