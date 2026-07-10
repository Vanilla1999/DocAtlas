---
name: docmancer
description: Search local documentation context packs with docmancer CLI. Use when the user asks about library docs, API references, vendor docs, version-specific behavior, offline docs, or wants to add docs before answering a technical question.
allowed-tools:
  - Bash(docmancer *)
  - Bash({{DOCS_KIT_CMD}} *)
---

# docmancer

Docmancer compresses documentation context so coding agents spend tokens on code, not on rereading raw docs. It ingests local files, fetches public docs, indexes everything locally with SQLite FTS5, and returns compact context packs with source attribution. The core retrieval path needs no API keys, vector database, hosted query API, or background daemon.

Executable: `{{DOCS_KIT_CMD}}`

**All commands below use `docmancer` as shorthand for the full executable path above.**

## When to Use

- User asks about a third-party library, SDK, or API and you need accurate documentation.
- User references docs from a public site, GitHub repository, or local files.
- You need to verify version-specific API behavior or exact method signatures.
- User asks you to search or query previously indexed documentation.

## Workflow

1. If the user is working inside a repository and asks to use Docmancer, asks how this project works, asks about architecture, or compares Docmancer to Context7, start with project docs discovery.
2. Run `doc-atlas list` to see indexed docs.
3. Run `doc-atlas query "question"` when relevant docs are present.
4. If local docs are missing and the user approves the path, run `doc-atlas ingest <path>`.
5. If URL docs are missing and the user approves the source, run `doc-atlas add <url>`.
6. Use the returned sections as source-grounded context for the answer or code change.

For MCP docs tools, registered sources are registry-owned. If `get_library_docs` returns candidates or `next_actions`, retry through Docmancer with the returned `arguments_patch`/guidance. Never WebFetch registered docs before that Docmancer retry.

## Project Docs Discovery with MCP

When MCP docs tools are available, call `get_docs_context(project_path=".", question=..., mode="project")` first inside a repo. It performs read-only preflight and searches reviewable project-owned docs (`README`, `docs/`, `wiki/`, `ARCHITECTURE`, ADR, roadmap) plus exact dependency evidence.

Use the returned `next_action` / `recommended_next_actions`:

- `prepare_docs(action="sync_project_docs")` is the public lifecycle path for local project docs. Run it only when `get_docs_context` returns it as `next_action`, or when the user explicitly requests synchronization.
- `get_docs_context(mode="project")` is the public query path for repo-specific architecture, implementation, roadmap, ADR, README, wiki, or module-doc questions. Use it before WebFetch.
- `docs_status` is only for explicit health, freshness, index, or background-job status requests.
- `create_reviewable_project_doc` is a manual agent/user action, not hidden memory: if no project docs exist, ask the user before studying the codebase and creating `ARCHITECTURE.md`; then sync through the returned `prepare_docs` action and retry `get_docs_context(mode="project")`.
- Dependency-doc prefetch may use the network. Use `prepare_docs(action="prefetch_project_dependency_docs")` only after explicit approval.
- Do not write official architecture or ADR into hidden memory. Official project docs should remain files in the repo.

For repo-specific implementation or architecture answers, start with `get_docs_context(mode="project")` before WebFetch. If the response reports not-indexed, stale, or missing project docs, follow its `next_action` instead of guessing, then retry context. For dependency API questions in a project, prefer exact dependency docs discovered from the project before latest-only hosted docs.

Golden path for repo questions: `get_docs_context(mode="project")` -> follow a returned `prepare_docs` action if needed -> retry context -> review the Trust Contract -> inspect source code only for current implementation facts. Bad path: choose a lifecycle or status tool speculatively, or answer from generic package docs before checking project-owned docs.

Evidence types must stay separate: project docs prove repository architecture, decisions, runbooks, and conventions; dependency docs prove external package APIs; source code proves current implementation. Do not use dependency docs as proof of repo-specific architecture.

If `source_state_guidance` mentions `indexed_source_not_discovered`, do not treat that as automatically deleted or invalid. It means an indexed source was not selected by the current project-doc discovery pass; link it from `docs/INDEX.md` or root docs, move it under a discovered docs location, adjust discovery, or refresh/remove obsolete index entries.

When a repository has many docs, treat a maintained `docs/INDEX.md` as the canonical map of project-owned docs. After docs are added, refreshed, or reorganized, recommend a verification loop: `prepare_docs(action="sync_project_docs")` -> ask smoke-test questions with `get_docs_context(mode="project")` and confirm expected files are cited.

## Core Commands

```bash
doc-atlas ingest ./docs
doc-atlas add https://docs.example.com
doc-atlas query "how to authenticate"
doc-atlas query "how to authenticate" --expand
doc-atlas query "how to authenticate" --expand page
doc-atlas query "how to authenticate" --format json
doc-atlas query "how to authenticate" --allow-degraded
doc-atlas clear --dry-run
doc-atlas list
doc-atlas inspect
doc-atlas update
doc-atlas remove <source>
doc-atlas doctor
```

Use `ingest` for local files and `add` for URLs. `query` is the primary retrieval command. It returns compact, source-attributed context plus estimated token savings.

## Advanced: API Tools via MCP

Only use the MCP Packs surface if the user is explicitly working with installed API packs. It is an advanced API-action layer, not an alternative documentation workflow. If the user has run `doc-atlas install-pack <pkg>@<version>`, the agent host can launch `doc-atlas mcp packs-serve` and expose two meta-tools. `doc-atlas mcp serve` is a compatibility alias:

- `docmancer_search_tools(query, package?, limit?)`
- `docmancer_call_tool(name, args)`

For API tasks, search first, inspect the returned schema and safety block, then call the resolved tool. Destructive calls are blocked unless the pack was installed with `--allow-destructive`. Run `doc-atlas mcp doctor` when pack credentials need verification.

## Common Mistakes

- Do not use `doc-atlas add` for new local files. Use `doc-atlas ingest <path>`.
- Do not use `doc-atlas ingest` for URLs. Use `doc-atlas add <url>`.
- Do not run `doc-atlas query` before checking indexed sources with `doc-atlas list`.
- Do not assume docs are indexed. Always verify with `doc-atlas list` before querying.
- Do not WebFetch registered docs when Docmancer returns candidates or retry guidance. Retry Docmancer first.
- Do not skip `get_docs_context` when the user asks to use Docmancer inside a repo or expects Context7-like help.
- Do not call `prepare_docs` speculatively or use `docs_status` as discovery.
- Do not use `prefetch_project_docs` for project-owned files; it is for dependency docs from project metadata/lockfiles.
- Do not cite dependency docs as evidence for project-specific architecture or implementation.
