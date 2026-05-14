---
name: docmancer
description: Search local documentation context packs with docmancer CLI. Use when the user asks about library docs, API references, vendor docs, version-specific behavior, offline docs, or wants to add docs before answering a technical question.
---

# docmancer

Compress documentation context so coding agents spend tokens on code, not on rereading raw docs. Docmancer fetches docs from public sites (GitBook, Mintlify, GitHub, generic web), indexes them locally with SQLite FTS5, and returns compact context packs with source attribution. No API keys, no vector database, no background daemons on the core path.

**MIT open source.** Everything runs locally. The core path has no API keys, no vector database, and no background daemon.

Executable: `{{DOCS_KIT_CMD}}`

**All commands below use `docmancer` as shorthand for the full executable path above.**

## When to Use

- User asks about a third-party library, SDK, or API and you need accurate, up-to-date documentation.
- User references docs from a public site (GitBook, Mintlify, or any web-hosted docs).
- You need to verify version-specific API behavior or check exact method signatures.
- User asks you to search or query previously ingested documentation.

## Workflow

1. Run `docmancer list` to see indexed docs.
2. Run `docmancer query "question"` when relevant docs are present.
3. If docs are missing and the user approves the source, run `docmancer add <url-or-path>` to index it locally.
4. Use the returned sections as source-grounded context for the answer or code change.

## Add documentation

```bash
docmancer add <url-or-path>
```

Fetch and index docs from a URL or local path. Auto-detects the docs platform.

| Flag | Purpose |
|------|---------|
| `--provider <auto\|gitbook\|mintlify\|web\|github>` | Force a specific provider |
| `--strategy <strategy>` | Force discovery strategy (`llms-full.txt`, `sitemap.xml`, `nav-crawl`) |
| `--max-pages <n>` | Cap pages fetched (default: 500) |
| `--browser` | Playwright fallback for JS-heavy sites |
| `--recreate` | Drop and rebuild the index for this source |

## Query documentation

```bash
docmancer query "<question>"
```

Primary command. Returns a compact markdown context pack with source attribution and token savings.

| Flag | Purpose |
|------|---------|
| `--budget <n>` | Max estimated output tokens (default: 2400) |
| `--limit <n>` | Max sections to return |
| `--expand` | Include adjacent sections around matches |
| `--expand page` | Include the full matching page within the budget |
| `--format <markdown\|json>` | Output format (default: markdown) |

## Manage sources

| Command | Purpose |
|---------|---------|
| `docmancer list` | Show indexed documentation sources |
| `docmancer list --all` | Show every stored page or file |
| `docmancer inspect` | Show index stats and extract locations |
| `docmancer update [source]` | Re-fetch and re-index all sources, or one specific source |
| `docmancer remove <source>` | Remove a source or docset root |
| `docmancer remove --all` | Clear the entire index |
| `docmancer doctor` | Check config, index health, and installed skills |
| `docmancer fetch <url> --output <dir>` | Download docs to markdown without indexing |

## API tools via MCP (when packs are installed)

If the user has run `docmancer install-pack <pkg>@<version>` (e.g. `open-meteo@v1` for the keyless weather demo), the agent host launches a local stdio MCP server (`docmancer mcp serve`) that exposes exactly two meta-tools:

- `docmancer_search_tools(query, package?, limit?)`: search for tools by task description. Always call this first to discover the fully qualified tool name and its input schema.
- `docmancer_call_tool(name, args)`: invoke a specific tool returned from search.

Workflow when the user asks to do something against a real API:

1. Call `docmancer_search_tools` with a short task description (and `package` if you know which pack is in use). The top match returns its full input schema inlined.
2. Validate that the returned `safety` block is acceptable. If `destructive: true`, the call is blocked unless the user has installed with `--allow-destructive`.
3. Call `docmancer_call_tool` with the fully qualified `name` and an `args` object that conforms to the inlined schema.
4. If the response includes `_docmancer.idempotency_key`, retry with the same `args._docmancer_idempotency_key` to deduplicate safely.

Credential setup the user may need:

- Shell-launched agents (Claude Code, Codex CLI): `export <PACK>_API_KEY=...` in the shell.
- GUI-launched agents (Cursor, Claude Desktop): edit the agent's MCP config and add `"env": {"<PACK>_API_KEY": "..."}` under the `docmancer` server entry, or write `~/.docmancer/secrets/<package>.env` with `<PACK>_API_KEY=...`.

Run `docmancer mcp doctor` to verify which credential source resolves for each installed pack.

## Common mistakes

- Do not run `docmancer query` before adding a source with `docmancer add`. Check `docmancer list` first.
- Do not assume docs are indexed. Always verify with `docmancer list` before querying.
- Legacy evaluation command surfaces have been removed.
