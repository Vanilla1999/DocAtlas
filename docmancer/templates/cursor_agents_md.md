> Prefer `~/.cursor/skills/docmancer/SKILL.md` when present; this block is a fallback.

# docmancer

Docmancer compresses documentation context so coding agents spend tokens on code, not on rereading raw docs. It ingests local files, fetches public docs, indexes everything locally with SQLite FTS5, and returns compact context packs with source attribution.

Executable: `{{DOCS_KIT_CMD}}`

**All commands below use `docmancer` as shorthand for the full executable path above.**

Use docmancer when the user asks about library docs, API references, vendor docs, version-specific behavior, offline docs, or wants to add docs before answering a technical question.

## Workflow

1. Run `docmancer list` to see indexed docs.
2. Run `docmancer query "question"` when relevant docs are present.
3. If local docs are missing and the user approves the path, run `docmancer ingest <path>`.
4. If URL docs are missing and the user approves the source, run `docmancer add <url>`.
5. Use returned sections as source-grounded context for the answer or code change.

## Core Commands

- `docmancer setup`
- `docmancer ingest ./docs`
- `docmancer add https://docs.example.com`
- `docmancer update`
- `docmancer query "how to authenticate"`
- `docmancer query "how to authenticate" --limit 10`
- `docmancer query "how to authenticate" --expand`
- `docmancer query "how to authenticate" --expand page`
- `docmancer query "how to authenticate" --format json`
- `docmancer list`
- `docmancer inspect`
- `docmancer remove <source>`
- `docmancer doctor`
- `docmancer fetch <url> --output <dir>`

## Advanced: API Tools via MCP

Only use the MCP surface if the user is explicitly working with installed API packs. If the user has run `docmancer install-pack <pkg>@<version>`, Cursor can launch `docmancer mcp serve` and expose two meta-tools:

- `docmancer_search_tools(query, package?, limit?)`
- `docmancer_call_tool(name, args)`

Cursor is GUI-launched. Add credentials to `mcpServers.docmancer.env` in `~/.cursor/mcp.json`, or write `~/.docmancer/secrets/<package>.env`. Run `docmancer mcp doctor` to verify.

## Common Mistakes

- Do not use `docmancer add` for new local files. Use `docmancer ingest <path>`.
- Do not use `docmancer ingest` for URLs. Use `docmancer add <url>`.
- Do not run `docmancer query` before checking indexed sources with `docmancer list`.
