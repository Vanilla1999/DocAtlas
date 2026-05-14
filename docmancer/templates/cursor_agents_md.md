> Prefer `~/.cursor/skills/docmancer/SKILL.md` when present; this block is a fallback.

# docmancer

Docmancer compresses documentation context so coding agents spend tokens on code, not on rereading raw docs. Docs are fetched from public sites, indexed locally with SQLite FTS5, and returned as compact context packs with source attribution. No API keys, no vector database, no background daemons on the core path.

**MIT open source.** Everything runs locally. The core path has no API keys, no vector database, and no background daemon.

Executable: `{{DOCS_KIT_CMD}}`

**All commands below use `docmancer` as shorthand for the full executable path above.**

Use docmancer when the user asks about library docs, API references, vendor docs, version-specific behavior, offline docs, or wants to add docs before answering a technical question.

## Workflow

1. Run `docmancer list` to see indexed docs.
2. Run `docmancer query "question"` when relevant docs are present.
3. If docs are missing and the user approves the source, run `docmancer add <url-or-path>` to index it locally.
4. Use returned sections as source-grounded context for the answer or code change.

## Core commands

- `docmancer setup`
- `docmancer add https://docs.example.com`
- `docmancer add ./docs`
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

## API tools via MCP (when packs are installed)

If the user has run `docmancer install-pack <pkg>@<version>`, Cursor launches `docmancer mcp serve` (auto-registered during `docmancer install cursor`). Two meta-tools are exposed:

- `docmancer_search_tools(query, package?, limit?)`: discover tools by task; top match returns its input schema inlined.
- `docmancer_call_tool(name, args)`: invoke a tool returned by search.

Cursor is GUI-launched. Add credentials to `mcpServers.docmancer.env` in `~/.cursor/mcp.json`, or write `~/.docmancer/secrets/<package>.env`. Run `docmancer mcp doctor` to verify.

Destructive calls are blocked unless the user installed the pack with `--allow-destructive`. Non-idempotent successes return `_docmancer.idempotency_key`; pass it back as `args._docmancer_idempotency_key` on retry.

## Common mistakes

- Do not run `docmancer query` before adding a source with `docmancer add`. Check `docmancer list` first.
- Legacy evaluation command surfaces have been removed.
