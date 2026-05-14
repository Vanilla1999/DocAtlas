---
name: docmancer
description: Search local documentation context packs with docmancer CLI. Use when the user asks about library docs, API references, vendor docs, version-specific behavior, offline docs, or wants to add docs before answering a technical question.
---

# docmancer

Compress documentation context so coding agents spend tokens on code, not on rereading raw docs. Docmancer fetches docs from public sites, indexes them locally with SQLite FTS5, and returns compact context packs with source attribution. No API keys required on the core path.

**MIT open source.** Everything runs locally. The core path has no API keys, no vector database, and no background daemon.

Executable: `{{DOCS_KIT_CMD}}`

**All commands below use `docmancer` as shorthand for the full executable path above.**

## Workflow

1. Run `docmancer list` to see indexed docs.
2. Run `docmancer query "question"` when relevant docs are present.
3. If docs are missing and the user approves the source, run `docmancer add <url-or-path>` to index it locally.
4. Use returned sections as source-grounded context for the answer or code change.

## Core commands

- `docmancer setup`: create config, database, and agent integrations.
- `docmancer add <url-or-path>`: index documentation from a URL, GitHub repository, local directory, markdown file, or text file.
- `docmancer update [source]`: re-fetch and re-index all sources, or one specific source.
- `docmancer query "question"`: return a compact markdown context pack.
- `docmancer query "question" --expand`: include adjacent sections.
- `docmancer query "question" --expand page`: include the full matching page within the budget.
- `docmancer query "question" --format json`: return machine-readable context.
- `docmancer list`, `docmancer inspect`, `docmancer remove`, `docmancer doctor`: manage the local index.
- `docmancer fetch <url> --output <dir>`: download docs to markdown without indexing.

`query` prints estimated raw docs tokens, context-pack tokens, percent saved, and agentic runway. Prefer the compact default first.

## API tools via MCP (when packs are installed)

If the user has run `docmancer install-pack <pkg>@<version>`, Claude Desktop launches `docmancer mcp serve`. Two meta-tools are exposed:

- `docmancer_search_tools(query, package?, limit?)`: discover tools by task; top match returns its input schema inlined.
- `docmancer_call_tool(name, args)`: invoke a tool returned by search.

Claude Desktop is GUI-launched, so shell `export` will not propagate. Add credentials to the `env` block under the `docmancer` server in `claude_desktop_config.json`, or write `~/.docmancer/secrets/<package>.env`. Run `docmancer mcp doctor` to verify.

Destructive calls are blocked unless the user installed the pack with `--allow-destructive`. Non-idempotent successes return `_docmancer.idempotency_key`; retry with `args._docmancer_idempotency_key` to deduplicate.

## Common mistakes

- Do not run `docmancer query` before adding a source with `docmancer add`. Check `docmancer list` first.
- Legacy evaluation command surfaces have been removed.
