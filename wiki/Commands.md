# Commands

Reference for the main docs-RAG commands, vector lifecycle commands, and advanced MCP pack commands. For how these fit into the overall system, see [Architecture](./Architecture.md). For configuration that affects command defaults, see [Configuration](./Configuration.md).

## Core commands

| Command | Description |
|---------|-------------|
| `docmancer setup` | Create config and SQLite database, auto-detect installed agents, and install skill files. Use `--all` for non-interactive installation. |
| `docmancer ingest <path>` | Index local files or directories. Supports Markdown, text, HTML, PDF, DOCX, and RTF out of the box. Embeds and upserts vectors alongside FTS5 by default; add `--no-vectors` for FTS5-only. |
| `docmancer add <url>` | Fetch URL documentation, normalize into sections, and index with SQLite FTS5. Supports GitBook, Mintlify, generic web, and GitHub. See [Supported Sources](./Supported-Sources.md). |
| `docmancer update` | Re-fetch and re-index all existing docs sources. Pass a specific source to update only that one. |
| `docmancer query "<text>"` | Search the index and return a compact context pack within a token budget. Shows token savings and agentic runway. |
| `docmancer list` | List indexed docsets with ingestion dates. Use `--all` to show individual sources. |
| `docmancer inspect` | Show SQLite index stats, source counts, and extract locations. |
| `docmancer remove [source]` | Remove an indexed source or docset root. Use `--all` to clear everything. |
| `docmancer doctor` | Health check: config, SQLite FTS5 availability, index stats, and installed agent skills. |
| `docmancer init` | Create a project-local `docmancer.yaml` for a project-specific index. |
| `docmancer install <agent>` | Install a skill file for a single agent manually. See [Install Targets](./Install-Targets.md). |
| `docmancer fetch <url>` | Download documentation to local Markdown files (default output dir `docmancer-docs/`). Does not update the SQLite index. |
| `docmancer qdrant {up,down,status,upgrade,logs}` | Manage the local Qdrant process used for dense + sparse + hybrid retrieval. See [Qdrant lifecycle](#qdrant-lifecycle) below. |

## Query options

| Option | Description |
|--------|-------------|
| `--budget <tokens>` | Set the docs context token budget (default: 2400). |
| `--expand` | Include adjacent sections around matches. |
| `--expand page` | Include the full matching page, subject to the token budget. |
| `--format json` | Return the context pack as JSON instead of markdown. |
| `--limit <n>` | Maximum number of sections to return. |
| `--mode {lexical,dense,sparse,hybrid}` | Retrieval mode. Defaults to `hybrid` when vectors are populated; falls back to `lexical` otherwise (or when no API key is available for the configured cloud embeddings provider). |
| `--explain` | Show per-source rank contributions (`lexical#1, dense#2, sparse#1`) under each result so you can see which signal placed it. |

## Ingest options

| Option | Description |
|--------|-------------|
| `--include <glob>` | Include only matching paths, relative to the ingest root. Can be passed multiple times. |
| `--exclude <glob>` | Exclude matching paths, relative to the ingest root. Can be passed multiple times. |
| `--format <format>` | Restrict ingest to one or more formats: `md`, `markdown`, `txt`, `pdf`, `docx`, `rtf`, `html`, or `htm`. |
| `--recursive / --no-recursive` | Recurse through directories. Default: recursive. |
| `--skip-known` | Skip files whose content hash is already indexed. |
| `--recreate` | Clear the entire index before ingesting. The vector pipeline detects the orphaned section ids and prunes the corresponding Qdrant points and `embedding_upserts` rows so dense/hybrid retrieval cannot resurrect them. |
| `--no-vectors` | Skip the embedding + vector upsert path entirely. Useful for FTS5-only installs and CI runs that should not download FastEmbed models. |

## Add options

| Option | Description |
|--------|-------------|
| `--provider <name>` | Force a docs platform: `auto`, `gitbook`, `mintlify`, `web`, `github`. Default: `auto`. |
| `--max-pages <n>` | Maximum pages to fetch from web sources (default: 500). |
| `--strategy <name>` | Force a discovery strategy: `llms-full.txt`, `sitemap.xml`, `nav-crawl`. |
| `--browser` | Enable Playwright browser fallback for JS-heavy sites. |
| `--recreate` | Clear the entire index before adding. |

## Update options

| Option | Description |
|--------|-------------|
| `--max-pages <n>` | Maximum pages to fetch when refreshing web sources (default: 500). |
| `--browser` | Enable Playwright browser fallback for JS-heavy sites. |

## MCP pack commands

`docmancer install-pack` installs version-pinned API MCP packs, and `docmancer mcp` manages the local MCP server and installed packs. This is an advanced surface that is not required for local docs retrieval. See [MCP Packs](./MCP-Packs.md) for the full reference and [Architecture > MCP runtime](./Architecture.md#mcp-runtime) for dispatch internals.

| Command | Description |
|---------|-------------|
| `docmancer install-pack <pkg>@<version>` | Install a pack from the registry. Verifies SHA-256 of every artifact and registers it in `~/.docmancer/mcp/manifest.json`. Spec parses from the rightmost `@` so npm-scoped names like `@scope/pkg@1.2.3` work. |
| `docmancer uninstall <pkg>[@<version>]` | Remove an installed pack (all versions if no version given). |
| `docmancer mcp serve` | Run the stdio MCP server. Agents launch this; humans usually do not. |
| `docmancer mcp list` | Show installed packs with mode (curated/expanded), per-pack tool counts, and destructive gate state (`block` or `ALLOW`). |
| `docmancer mcp doctor` | Verify pack SHA-256s, credential resolution per scheme, and agent-config registrations. Reports actionable warnings. |
| `docmancer mcp enable <pkg> [--version <v>]` | Re-enable a previously disabled pack without reinstalling. |
| `docmancer mcp disable <pkg> [--version <v>]` | Hide a pack from the dispatcher's tool surface without removing it on disk. |

### install-pack options

| Option | Description |
|--------|-------------|
| `--expanded` | Use the full tool surface (`tools.full.json`) instead of the curated subset. |
| `--allow-destructive` | Permit destructive calls (POST/PUT/PATCH/DELETE) for this pack. Off by default; the dispatcher refuses such calls and surfaces the exact reinstall command in the error message. |
| `--allow-execute` | Permit executor types like `python_import` that run code in a subprocess. Off by default. |
| `--from-url <url>` | Compile the pack locally from a public OpenAPI 3.x or Swagger 2.0 spec URL. Use this when the package is not in the hosted registry. Without the flag, an interactive shell will prompt for the same URL on a resolver miss. |

### MCP runtime behavior

When the agent calls `docmancer_call_tool`, the dispatcher resolves the slug `package__version__operation` (D15: double-underscore field separators), validates `args` against the operation's input schema, resolves credentials, runs the safety gate, auto-injects an `Idempotency-Key` for non-idempotent operations on sources that declare an idempotency header (UUID4, reused on retry from a 24-hour SQLite fingerprint cache), merges `auth.required_headers` declared in the contract (used by keyed APIs that pin a dated wire version), and dispatches via the operation's executor. Path parameters are percent-encoded as one segment so values like `feat/x?ref=main` do not alter the URL structure. Logs at `~/.docmancer/mcp/calls.jsonl` record `arg_keys` only, never values.

## Qdrant lifecycle

The `docmancer qdrant` group manages a docmancer-owned local Qdrant process. The default `docmancer ingest` runs the full hybrid path: on first ingest it downloads the pinned Qdrant binary, starts it in the background, and embeds + upserts vectors alongside FTS5. Use `ingest --no-vectors` (or set `DOCMANCER_AUTO_VECTORS=0`) for FTS5-only runs.

| Subcommand | Description |
|------------|-------------|
| `docmancer qdrant up` | Download the pinned Qdrant binary (currently `v1.14.1`) to `~/.docmancer/qdrant/qdrant` if absent, start it in the background, write a PID + runtime metadata file, and spawn with telemetry disabled (`QDRANT__TELEMETRY_DISABLED=true`). Pass `--port` to pin a specific port, or `--docker` to print a `docker compose` snippet instead of running the managed binary. |
| `docmancer qdrant down` | Stop a docmancer-managed process. Refuses to touch a PID file docmancer did not write. |
| `docmancer qdrant status` | Report pid, port, url, alive, docmancer-ownership, healthy, and version. Add `--json` for raw JSON. |
| `docmancer qdrant upgrade` | Swap the managed binary in-place against the same on-disk storage. Refuses to run against a live docmancer-owned process without `--force`. Cross-version storage migration is not automated. |
| `docmancer qdrant logs` | Tail the managed binary's stdout (or stderr with `--stderr`) from `~/.docmancer/qdrant/logs/`. |

Environment overrides:

- `DOCMANCER_QDRANT_URL`: point docmancer at an existing Qdrant (managed elsewhere). Skips the local lifecycle entirely.
- `DOCMANCER_QDRANT_API_KEY`: bearer token for the above.
- `DOCMANCER_QDRANT_BINARY`: pre-staged binary path for air-gapped hosts (skips the GitHub download).
- `DOCMANCER_AUTO_VECTORS=0`: opt out of the vector path; `ingest` and `query` stay on FTS5 only.

Safety: `QdrantStore.ensure_collection` refuses to claim a pre-existing collection that does not carry the docmancer ownership sentinel, and `delete_collection` will only operate on docmancer-owned collections. Point `vector_store.collection` at a name docmancer creates.

## Advanced retrieval

Set in `docmancer.yaml`:

- `retrieval.hierarchical.enabled: true` switches the dispatcher to a two-stage retrieval: cast a wide net, aggregate scores by `document_title_hash`, pick the top `documents_limit` documents, then re-retrieve sections filtered to those documents. Good for multi-product docs portals; leave off for flat corpora.
- `retrieval.routers` is an ordered list of `{match: <regex>, filters: {...}}` entries. The first regex that matches the query has its `filters` merged into the dispatcher's filters for that call. Use it when different query patterns should narrow retrieval to known metadata, such as `source_path_prefix=api` or `format=markdown`.
- `retrieval.expand: adjacent` (or `page`) plumbs neighbor expansion through hybrid mode the same way `--expand` works for lexical-only retrieval.

See [Configuration](./Configuration.md) for the full key-by-key reference.

## Optional extras

| Extra | What it enables |
|-------|-----------------|
| `docmancer[embeddings-openai]` | OpenAI cloud embeddings (`text-embedding-3-small` / `-large`) with batched requests and rate-limit retries. Requires `OPENAI_API_KEY`. |
| `docmancer[embeddings-voyage]` | Voyage AI cloud embeddings provider. Requires `VOYAGE_API_KEY`. |
| `docmancer[embeddings-cohere]` | Cohere cloud embeddings provider. Requires `COHERE_API_KEY`. |
| `docmancer[browser]` | Playwright fetcher for JS-heavy sites (used by `add --browser`). |
| `docmancer[crawl4ai]` | Alternative fetcher for hard-to-scrape sites. |

The PDF / DOCX / RTF / HTML loaders, the Qdrant client, sqlite-vec, and FastEmbed all ship in the core install. No extra is needed for the default hybrid path.
