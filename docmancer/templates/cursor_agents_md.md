> Prefer `~/.cursor/skills/docmancer/SKILL.md` when present; this block is a fallback.

# docmancer

Docmancer compresses documentation context so coding agents spend tokens on code, not on rereading raw docs. It ingests local files, fetches public docs, indexes everything locally with SQLite FTS5, and returns compact context packs with source attribution.

Executable: `{{DOCS_KIT_CMD}}`

**All commands below use `docmancer` as shorthand for the full executable path above.**

Use docmancer when the user asks about library docs, API references, vendor docs, version-specific behavior, offline docs, or wants to add docs before answering a technical question.

## Workflow

1. Run `doc-atlas list` to see indexed docs.
2. Run `doc-atlas query "question"` when relevant docs are present.
3. If local docs are missing and the user approves the path, run `doc-atlas ingest <path>`.
4. If URL docs are missing and the user approves the source, run `doc-atlas add <url>`.
5. Use returned sections as source-grounded context for the answer or code change.

## Core Commands

- `doc-atlas setup`
- `doc-atlas ingest ./docs`
- `doc-atlas add https://docs.example.com`
- `doc-atlas update`
- `doc-atlas query "how to authenticate"`
- `doc-atlas query "how to authenticate" --limit 10`
- `doc-atlas query "how to authenticate" --expand`
- `doc-atlas query "how to authenticate" --expand page`
- `doc-atlas query "how to authenticate" --format json`
- `doc-atlas query "how to authenticate" --allow-degraded`
- `doc-atlas clear --dry-run`
- `doc-atlas list`
- `doc-atlas inspect`
- `doc-atlas remove <source>`
- `doc-atlas doctor`
- `doc-atlas fetch <url> --output <dir>`

## Advanced: API Tools via MCP

Only use the MCP Packs surface if the user is explicitly working with installed API packs. It is an advanced API-action layer, not an alternative documentation workflow. If the user has run `doc-atlas install-pack <pkg>@<version>`, Cursor can launch `doc-atlas mcp serve` and expose two meta-tools:

- `docmancer_search_tools(query, package?, limit?)`
- `docmancer_call_tool(name, args)`

Cursor is GUI-launched. Add credentials to `mcpServers.docmancer.env` in `~/.cursor/mcp.json`, or write `~/.docmancer/secrets/<package>.env`. Run `doc-atlas mcp doctor` to verify.

## Common Mistakes

- Do not use `doc-atlas add` for new local files. Use `doc-atlas ingest <path>`.
- Do not use `doc-atlas ingest` for URLs. Use `doc-atlas add <url>`.
- Do not run `doc-atlas query` before checking indexed sources with `doc-atlas list`.
