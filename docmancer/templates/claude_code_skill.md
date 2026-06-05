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
2. Run `docmancer list` to see indexed docs.
3. Run `docmancer query "question"` when relevant docs are present.
4. If local docs are missing and the user approves the path, run `docmancer ingest <path>`.
5. If URL docs are missing and the user approves the source, run `docmancer add <url>`.
6. Use the returned sections as source-grounded context for the answer or code change.

For MCP docs tools, registered sources are registry-owned. If `get_library_docs` returns candidates or `next_actions`, retry through Docmancer with the returned `arguments_patch`/guidance. Never WebFetch registered docs before that Docmancer retry.

## Project Docs Discovery with MCP

When MCP docs tools are available, call `inspect_project_docs(project_path=".")` first inside a repo when the user asks to use Docmancer, asks about project architecture, asks how this repo works, or expects Context7-like help. This read-only step discovers reviewable project-owned docs (`README`, `docs/`, `wiki/`, `ARCHITECTURE`, ADR, roadmap) and dependency manifests/lockfiles.

Use the returned `recommended_next_actions`:

- `ingest_project_docs` indexes local project docs; ask briefly unless local indexing was already approved.
- `get_project_docs` queries indexed project-owned docs and returns source class, file path, heading, and stale/next-action guidance. Use it before WebFetch for repo-specific architecture, implementation, roadmap, ADR, or README questions.
- `prefetch_project_docs` fetches exact dependency docs from manifests/lockfiles; ask before running because it may use the network.
- Do not write official architecture or ADR into hidden memory. Official project docs should remain files in the repo.

For repo-specific implementation or architecture answers, use `get_project_docs` after `inspect_project_docs`/`ingest_project_docs` before WebFetch. If `get_project_docs` reports `not_indexed`, `stale`, or `no_project_docs`, follow its `next_actions` instead of guessing. For dependency API questions in a project, prefer exact dependency docs discovered from the project before latest-only hosted docs.

## Core Commands

```bash
docmancer ingest ./docs
docmancer add https://docs.example.com
docmancer query "how to authenticate"
docmancer query "how to authenticate" --expand
docmancer query "how to authenticate" --expand page
docmancer query "how to authenticate" --format json
docmancer query "how to authenticate" --allow-degraded
docmancer clear --dry-run
docmancer list
docmancer inspect
docmancer update
docmancer remove <source>
docmancer doctor
```

Use `ingest` for local files and `add` for URLs. `query` is the primary retrieval command. It returns compact, source-attributed context plus estimated token savings.

## Advanced: API Tools via MCP

Only use the MCP surface if the user is explicitly working with installed API packs. If the user has run `docmancer install-pack <pkg>@<version>`, the agent host can launch `docmancer mcp serve` and expose two meta-tools:

- `docmancer_search_tools(query, package?, limit?)`
- `docmancer_call_tool(name, args)`

For API tasks, search first, inspect the returned schema and safety block, then call the resolved tool. Destructive calls are blocked unless the pack was installed with `--allow-destructive`. Run `docmancer mcp doctor` when pack credentials need verification.

## Common Mistakes

- Do not use `docmancer add` for new local files. Use `docmancer ingest <path>`.
- Do not use `docmancer ingest` for URLs. Use `docmancer add <url>`.
- Do not run `docmancer query` before checking indexed sources with `docmancer list`.
- Do not assume docs are indexed. Always verify with `docmancer list` before querying.
- Do not WebFetch registered docs when Docmancer returns candidates or retry guidance. Retry Docmancer first.
- Do not skip `inspect_project_docs` when the user asks to use Docmancer inside a repo or expects Context7-like help.
- Do not use `prefetch_project_docs` for project-owned files; it is for dependency docs from project metadata/lockfiles.
