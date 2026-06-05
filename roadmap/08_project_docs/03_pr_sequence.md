# 08.03 — PR Sequence

## PR 1 — Project docs source discovery

Scope:

- Add detector for project-owned docs candidates.
- Support README/docs/wiki/architecture/ADR/roadmap/changelog/contributing.
- Add exclude rules for `.git`, dependencies, build outputs, virtualenvs.
- Return reasons for each candidate.

Tests:

- fixtures for common repo layouts;
- no source code auto-ingest by default;
- symlink/path traversal safety if relevant.

## PR 2 — Project docs source model

Scope:

- Add model for `ProjectDocsSource`.
- Add `source_class` enum: `project_file`, `local_memory`, `dependency_docs`, `public_docs`.
- Add freshness metadata: file mtime/hash if feasible.

Tests:

- parse/render JSON;
- stable output for MCP responses.

## PR 3 — `inspect_project_docs` MVP

Scope:

- MCP tool and/or CLI command.
- Show candidate/indexed/stale/ignored sources.
- Include dependency manifests/lockfiles if available.
- Include `recommended_next_actions` and `agent_guidance`.

Non-goal:

- no automatic ingest yet.

Tests:

- empty repo response;
- repo with README/wiki/docs;
- repo with lockfile returns dependency docs recommendations;
- stale detection if index metadata exists.

## PR 4 — Discovery-first MCP descriptions

Scope:

- Update MCP tool descriptions so agents know `inspect_project_docs` is the default entrypoint inside a repo.
- Add guidance: if user says “use Docmancer” or “like Context7” while in a repo, inspect project docs first.
- Clarify confirmation boundaries: local inspect/read-only vs local ingest vs network fetch.

Tests:

- snapshot tests for tool descriptions if available;
- generated MCP schema includes discovery-first wording.

## PR 5 — `ingest_project_docs` MVP

Scope:

- Ingest detected project docs candidates.
- Use existing local ingest/index path.
- Apply project-scoped metadata/filter tags.

Tests:

- indexes only candidates;
- excludes code/deps/build outputs;
- idempotent re-run.

## PR 6 — Project-scoped query filters

Scope:

- Allow retrieval to filter by project identity/path/source class.
- Ensure context packs include project file attribution.

Tests:

- query does not leak unrelated indexed docs;
- multiple projects in same Docmancer home do not collide.

## PR 7 — `get_project_docs` MVP

Scope:

- MCP tool wrapping project-scoped query.
- If docs missing, return structured next actions, not generic failure.
- If stale, warn but allow query if requested.

Tests:

- happy path with README/wiki;
- missing docs returns `inspect/ingest` remediation;
- stale docs warning is machine-readable.

## PR 8 — Agent guidance update

Scope:

- Update installed skills/instructions.
- Add rules:
  - for repo architecture/project questions, use `get_project_docs` before WebFetch;
  - for dependency API questions, use library/project dependency docs;
  - do not write official architecture to hidden memory;
  - if project docs are not indexed, call `inspect_project_docs` and offer `ingest_project_docs`.

Tests:

- snapshot tests for generated skill text if existing.

## PR 9 — Project docs demo on Docmancer itself

Scope:

- Add demo script or docs page indexing Docmancer README/wiki/roadmap/product brief.
- Demo questions:
  - “What is Docmancer architecture?”
  - “What is the next strategic milestone?”
  - “How do Docs and Packs differ?”
  - “I thought Docmancer was like Context7; what should I do in this repo?”

Success:

- answers cite project files;
- compact context pack shows token savings;
- no WebFetch needed;
- agent offers project docs workflow.

## PR 10 — Tiny eval set for project docs

Scope:

- 20–30 gold queries over Docmancer project docs.
- Classes: architecture, roadmap, command reference, registry identity, Docs vs Packs, discovery-first onboarding.
- Hit@k/MRR baseline.

Non-goal:

- no LLM-as-judge gate.

## PR 11 — README quickstart lane

Scope:

- Add “Index this project’s docs for your coding agent”.
- Add “I thought this was like Context7 — what else does it do?” lane.
- Explain project-owned docs vs project dependency docs vs library docs.
- Show official docs as files principle.
- Tell agents/users to start with `inspect_project_docs` in a repo.
