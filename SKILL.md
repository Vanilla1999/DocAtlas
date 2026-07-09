---
name: docmancer
description: Search and query local documentation knowledge bases using the DocAtlas CLI. Use when the user asks about third-party library docs, API references, vendor documentation, version-specific API behavior, GitBook or Mintlify public docs, offline or local doc search, or needs to ground agent responses in up-to-date external documentation.
version: 0.4.6
author: docmancer
tags:
  - documentation
  - rag
  - local-first
  - knowledge-base
  - sqlite
install: pipx install docmancer --python python3.13
---

# Project Patch Contract Runtime for coding agents

For patch-like tasks, use DocAtlas as a Patch Contract runtime, not only as docs search.

Required agent ritual:

1. Call `get_docs_context(question, project_path)` when task scope is unclear.
2. If the response has `next_action.name == "get_patch_constraints"`, call `get_patch_constraints` before editing.
3. Treat `forbidden_edits`, `source_of_truth_rules`, `dependency_contracts`, `suggested_checks`, and `unknowns/manual_review` as the pre-patch contract.
4. Edit code.
5. Call `validate_patch_against_constraints` with `changed_files` and/or `patch_diff`.
6. Report `violated` and `manual_review` constraints clearly.
7. Never claim the patch is safe-to-merge from DocAtlas validation alone; this output is advisory and does not replace tests or human review.


# DocAtlas / docmancer

Docmancer compresses documentation context so coding agents spend tokens on code, not on rereading raw docs. It ingests local files, fetches public docs, indexes everything locally with SQLite FTS5, and returns compact context packs with source attribution. The core retrieval path needs no API keys, vector database, hosted query API, or background daemon.

**MIT open source.** The CLI runs locally and is intended for source-grounded documentation lookup.

## When to Use

- User asks about a third-party library, SDK, or API and you need accurate documentation.
- User references docs from a public site, GitHub repository, or local files.
- You need to verify version-specific API behavior or exact method signatures.
- User asks you to search or query previously indexed documentation.

## Workflow

1. **Check indexed docs:** `doc-atlas list`
2. **Query existing docs:** `doc-atlas query "<question>"`
3. **Index local docs if needed:** `doc-atlas ingest <path>`
4. **Fetch URL docs if needed:** `doc-atlas add <url>`
5. **Use the returned context** to ground your response with source-attributed sections.

For MCP docs tools, registered sources are registry-owned. If `get_library_docs` returns candidates or `next_actions`, retry through Docmancer with the returned `arguments_patch`/guidance. Never WebFetch registered docs before that Docmancer retry.

## Core Commands

### Ingest Local Documentation

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
| `--recreate` | Drop and rebuild the index |

### Add URL Documentation

```bash
doc-atlas add https://docs.example.com
```

Use `add` for documentation URLs and GitHub repositories.

| Flag | Purpose |
|------|---------|
| `--provider <auto\|gitbook\|mintlify\|web\|github>` | Force a specific provider |
| `--strategy <strategy>` | Force discovery strategy |
| `--max-pages <n>` | Cap pages fetched |
| `--browser` | Playwright fallback for JS-heavy sites |
| `--recreate` | Drop and rebuild the index |

### Query Documentation

```bash
doc-atlas query "<question>"
```

Returns a compact markdown context pack with source attribution and token savings. This is the primary command agents should call.

| Flag | Purpose |
|------|---------|
| `--budget <n>` | Max estimated output tokens |
| `--limit <n>` | Max sections to return |
| `--expand` | Include adjacent sections around matches |
| `--expand page` | Include full page content within budget |
| `--format <markdown\|json>` | Output format |

### Manage Sources

| Command | Purpose |
|---------|---------|
| `doc-atlas list` | Show indexed documentation sources |
| `doc-atlas list --all` | Show every stored page or file |
| `doc-atlas inspect` | Show index stats, format counts, and extract locations |
| `doc-atlas remove <source>` | Remove a source or docset root |
| `doc-atlas remove --all` | Clear the entire index |
| `doc-atlas update [source]` | Re-fetch and re-index all sources, or one specific source |
| `doc-atlas doctor` | Check config, loader availability, index health, and agent skill installs |
| `doc-atlas init` | Create project-local `docmancer.yaml` |
| `doc-atlas fetch <url> --output <dir>` | Download docs to markdown files without indexing |

## Advanced: API Tools via MCP

Only use the MCP Packs surface if the user is explicitly working with installed API packs. It is an advanced API-action layer, not an alternative documentation workflow. If the user has run `doc-atlas install-pack <pkg>@<version>`, the agent host can launch `doc-atlas mcp serve` and expose two meta-tools:

- `docmancer_search_tools(query, package?, limit?)`
- `docmancer_call_tool(name, args)`

For API tasks, search first, inspect the returned schema and safety block, then call the resolved tool. Destructive calls are blocked unless the pack was installed with `--allow-destructive`. Run `doc-atlas mcp doctor` when pack credentials need verification.

## Recommended MCP Docs Workflow for Agents

For repository-specific architecture, conventions, runbooks, roadmap, README/wiki, or module-doc questions, use the Docs MCP tools before generic WebFetch or model memory:

1. Call `inspect_project_docs(project_path)` first for read-only discovery.
2. If reconciliation is needed, call `prepare_docs(action="sync_project_docs", project_path=..., with_vectors=true)`.
3. Call `get_docs_context(project_path=..., question=..., mode="project")` for the answer context pack.
4. Read `answer_outline.recommended_reading_order` before composing the answer.
5. Use `trust_contract.selected` / `trust_contract.selected_sources` to cite trusted sources. Treat `CHANGELOG.md` as primary only for release-history/change questions.
6. Prefer nested `context_pack[].source` and `context_pack[].section` metadata; the flat fields are kept for compatibility.
7. If the user asks vaguely about "the MCP server", distinguish `doc-atlas mcp docs-serve` (canonical documentation context and Patch Contract workflows) from `doc-atlas mcp serve` (advanced installed MCP Packs/API action tools).

## Common Mistakes

- Do not use `doc-atlas add` for new local files. Use `doc-atlas ingest <path>`.
- Do not use `doc-atlas ingest` for URLs. Use `doc-atlas add <url>`.
- Do not run `doc-atlas query` before checking indexed sources with `doc-atlas list`.
- Do not assume docs are indexed. Always verify with `doc-atlas list` before querying.
- Do not WebFetch registered docs when Docmancer returns candidates or retry guidance. Retry Docmancer first.
