---
name: docmancer
description: Search local documentation context packs with docmancer CLI. Use when the user asks about library docs, API references, vendor docs, version-specific behavior, offline docs, or wants to add docs before answering a technical question.
---

# docmancer

Docmancer compresses documentation context so coding agents spend tokens on code, not on rereading raw docs. It ingests local files, fetches public docs, indexes everything locally with SQLite FTS5, and returns compact context packs with source attribution.

Executable: `{{DOCS_KIT_CMD}}`

**All commands below use `docmancer` as shorthand for the full executable path above.**

## Workflow

1. If the user is working inside a repository and asks to use Docmancer, asks how this project works, asks about architecture, or compares Docmancer to Context7, start with project docs discovery.
2. Run `doc-atlas list` to see indexed docs.
3. Run `doc-atlas query "question"` when relevant docs are present.
4. If local docs are missing and the user approves the path, run `doc-atlas ingest <path>`.
5. If URL docs are missing and the user approves the source, run `doc-atlas add <url>`.
6. Use returned sections as source-grounded context for the answer or code change.

For MCP docs tools, registered sources are registry-owned. If `get_library_docs` returns candidates or `next_actions`, retry through Docmancer with the returned `arguments_patch`/guidance. Never WebFetch registered docs before that Docmancer retry.

## Project Docs Discovery with MCP

When MCP docs tools are available, call `inspect_project_docs(project_path=".")` first inside a repo when the user asks to use Docmancer, asks about project architecture, asks how this repo works, or expects Context7-like help. This read-only step discovers reviewable project-owned docs (`README`, `docs/`, `wiki/`, `ARCHITECTURE`, ADR, roadmap) and dependency manifests/lockfiles.

Use the returned `recommended_next_actions`:

- `ingest_project_docs` indexes local project docs; ask briefly unless local indexing was already approved.
- `get_project_docs` queries indexed project-owned docs and returns source class, file path, heading, and stale/next-action guidance. Use it before WebFetch for repo-specific architecture, implementation, roadmap, ADR, or README questions.
- `create_reviewable_project_doc` is a manual agent/user action, not hidden memory: if no project docs exist, ask the user before studying the codebase and creating `ARCHITECTURE.md`; then run `inspect_project_docs`, `ingest_project_docs`, and `get_project_docs`.
- `prefetch_project_docs` fetches exact dependency docs from manifests/lockfiles; ask before running because it may use the network.
- Do not write official architecture or ADR into hidden memory. Official project docs should remain files in the repo.

For repo-specific implementation or architecture answers, use `get_project_docs` after `inspect_project_docs`/`ingest_project_docs` before WebFetch. If `get_project_docs` reports `not_indexed`, `stale`, or `no_project_docs`, follow its `next_actions` instead of guessing. For dependency API questions in a project, prefer exact dependency docs discovered from the project before latest-only hosted docs.

Golden path for repo questions: `inspect_project_docs` -> `ingest_project_docs` when requested -> `get_project_context` -> review the Trust Contract -> inspect source code only for current implementation facts. Bad path: answer from generic package docs or WebFetch before checking project-owned docs.

Evidence types must stay separate: project docs prove repository architecture, decisions, runbooks, and conventions; dependency docs prove external package APIs; source code proves current implementation. Do not use dependency docs as proof of repo-specific architecture.

If `source_state_guidance` mentions `indexed_source_not_discovered`, do not treat that as automatically deleted or invalid. It means an indexed source was not selected by the current project-doc discovery pass; link it from `docs/INDEX.md` or root docs, move it under a discovered docs location, adjust discovery, or refresh/remove obsolete index entries.

When a repository has many docs, treat a maintained `docs/INDEX.md` as the canonical map of project-owned docs. After docs are added, refreshed, or reorganized, recommend a verification loop: `inspect_project_docs` -> `ingest_project_docs` if needed -> `inspect_project_docs` again -> ask smoke-test questions with `get_project_context`/`get_project_docs` and confirm expected files are cited.

## Core Commands

- `doc-atlas setup`: create config, database, and agent integrations.
- `doc-atlas ingest <path>`: index local files or directories.
- `doc-atlas add <url>`: fetch and index documentation from a URL or GitHub repository.
- `doc-atlas update [source]`: re-fetch and re-index all sources, or one specific source.
- `doc-atlas query "question"`: return a compact markdown context pack.
- `doc-atlas query "question" --expand`: include adjacent sections.
- `doc-atlas query "question" --expand page`: include the full matching page within the budget.
- `doc-atlas query "question" --format json`: return machine-readable context.
- `doc-atlas query "question" --allow-degraded`: in dense, sparse, or hybrid modes, fall back when vector retrieval fails instead of erroring.
- `doc-atlas clear --dry-run`: preview wiping docmancer home and related caches (`--yes` to run for real; see `--keep-config` and `--keep-models`).
- `doc-atlas list`, `doc-atlas inspect`, `doc-atlas remove`, `doc-atlas doctor`: manage the local index.
- `doc-atlas fetch <url> --output <dir>`: download docs to markdown without indexing.

`query` prints estimated raw docs tokens, context-pack tokens, percent saved, and agentic runway. Prefer the compact default first.

## Advanced: API Tools via MCP

Only use the MCP surface if the user is explicitly working with installed API packs. If the user has run `doc-atlas install-pack <pkg>@<version>`, Claude Desktop can launch `doc-atlas mcp serve` and expose two meta-tools:

- `docmancer_search_tools(query, package?, limit?)`
- `docmancer_call_tool(name, args)`

Claude Desktop is GUI-launched, so shell `export` will not propagate. Add credentials to the `env` block under the `docmancer` server in `claude_desktop_config.json`, or write `~/.docmancer/secrets/<package>.env`. Run `doc-atlas mcp doctor` to verify.

Destructive calls are blocked unless the user installed the pack with `--allow-destructive`.

## Common Mistakes

- Do not use `doc-atlas add` for new local files. Use `doc-atlas ingest <path>`.
- Do not use `doc-atlas ingest` for URLs. Use `doc-atlas add <url>`.
- Do not run `doc-atlas query` before checking indexed sources with `doc-atlas list`.
- Do not WebFetch registered docs when Docmancer returns candidates or retry guidance. Retry Docmancer first.
- Do not skip `inspect_project_docs` when the user asks to use Docmancer inside a repo or expects Context7-like help.
- Do not use `prefetch_project_docs` for project-owned files; it is for dependency docs from project metadata/lockfiles.
- Do not cite dependency docs as evidence for project-specific architecture or implementation.
