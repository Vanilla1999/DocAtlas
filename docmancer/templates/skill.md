---
name: docmancer
description: Search local documentation context packs with docmancer CLI. Use when the user asks about library docs, API references, vendor docs, version-specific behavior, offline docs, or wants to add docs before answering a technical question.
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

## Ingest Local Documentation

```bash
doc-atlas ingest ./docs
```

Use `ingest` for local files and directories.

| Flag | Purpose |
|------|---------|
| `--include <glob>` | Include only matching relative paths |
| `--exclude <glob>` | Exclude matching relative paths |
| `--format <format>` | Restrict to formats such as `md`, `txt`, `pdf`, `docx`, `rtf`, or `html` |
| `--recursive / --no-recursive` | Recurse through directories |
| `--skip-known` | Skip files whose content hash is already indexed |
| `--recreate` | Drop and rebuild the index; when vector sync is enabled, drops the vector collection first so embedder or dimension changes rebuild cleanly |

## Add URL Documentation

```bash
doc-atlas add https://docs.example.com
```

Use `add` for documentation URLs and GitHub repositories.

| Flag | Purpose |
|------|---------|
| `--provider <auto\|gitbook\|mintlify\|web\|github>` | Force a specific provider |
| `--strategy <strategy>` | Force discovery strategy (`llms-full.txt`, `sitemap.xml`, `nav-crawl`) |
| `--max-pages <n>` | Cap pages fetched |
| `--browser` | Playwright fallback for JS-heavy sites |
| `--recreate` | Drop and rebuild the index |

## Query Documentation

```bash
doc-atlas query "<question>"
```

Primary command. Returns a compact markdown context pack with source attribution and token savings.

| Flag | Purpose |
|------|---------|
| `--budget <n>` | Max estimated output tokens |
| `--limit <n>` | Max sections to return |
| `--expand` | Include adjacent sections around matches |
| `--expand page` | Include the full matching page within the budget |
| `--format <markdown\|json>` | Output format |
| `--allow-degraded` | In dense, sparse, or hybrid modes, fall back to remaining signals (for example lexical) when vector retrieval fails instead of exiting with an error |

## Manage Sources

| Command | Purpose |
|---------|---------|
| `doc-atlas list` | Show indexed documentation sources |
| `doc-atlas list --all` | Show every stored page or file |
| `doc-atlas inspect` | Show index stats, format counts, and extract locations |
| `doc-atlas update [source]` | Re-fetch and re-index all sources, or one specific source |
| `doc-atlas remove <source>` | Remove a source or docset root |
| `doc-atlas remove --all` | Clear the entire index |
| `doc-atlas clear` | Wipe docmancer home, model caches used by docmancer, and managed Qdrant data (destructive; use `--dry-run`, `--keep-config`, or `--keep-models` as needed) |
| `doc-atlas doctor` | Check config, loader availability, index health, and installed skills |
| `doc-atlas fetch <url> --output <dir>` | Download docs to markdown without indexing |

## Advanced: API Tools via MCP

Only use the MCP surface if the user is explicitly working with installed API packs. If the user has run `doc-atlas install-pack <pkg>@<version>`, the agent host can launch `doc-atlas mcp serve` and expose two meta-tools:

- `docmancer_search_tools(query, package?, limit?)`
- `docmancer_call_tool(name, args)`

For API tasks, search first, inspect the returned schema and safety block, then call the resolved tool. Destructive calls are blocked unless the pack was installed with `--allow-destructive`. Run `doc-atlas mcp doctor` when pack credentials need verification.

## Common Mistakes

- Do not use `doc-atlas add` for new local files. Use `doc-atlas ingest <path>`.
- Do not use `doc-atlas ingest` for URLs. Use `doc-atlas add <url>`.
- Do not run `doc-atlas query` before checking indexed sources with `doc-atlas list`.
- Do not assume docs are indexed. Always verify with `doc-atlas list` before querying.
- Do not WebFetch registered docs when Docmancer returns candidates or retry guidance. Retry Docmancer first.
- Do not skip `inspect_project_docs` when the user asks to use Docmancer inside a repo or expects Context7-like help.
- Do not use `prefetch_project_docs` for project-owned files; it is for dependency docs from project metadata/lockfiles.
- Do not cite dependency docs as evidence for project-specific architecture or implementation.
