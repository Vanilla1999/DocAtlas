# Architecture

Docmancer runs two cooperating local pipelines.

The **docs-RAG pipeline** fetches documentation with `docmancer add` (URL) or `docmancer ingest` (local files), normalizes it into sections, indexes those sections in a local SQLite FTS5 database plus a managed local Qdrant for dense and sparse vectors, and retrieves compact context packs on `docmancer query` through a hybrid dispatcher with RRF fusion. No hosted query API; the only background process is the docmancer-owned Qdrant.

The **MCP runtime** installs version-pinned API packs from a registry with `docmancer install-pack <package>@<version>`, then exposes every installed pack to your agent through a single shared stdio MCP server (`docmancer mcp serve`) using the Tool Search pattern: two meta-tools regardless of how many packs you install. The dispatcher enforces auth, destructive-call gating, schema validation, idempotency-key auto-injection and reuse, version pinning on the wire, and SHA-256 verification of every artifact before install.

For the full command reference, see [Commands](./Commands.md). For configuration options, see [Configuration](./Configuration.md).

## Indexing

Documentation is fetched from URLs or read from local files, then normalized into semantic sections based on heading structure. Each section is stored in SQLite with its title, heading level, source URL, content hash, and token estimate. A FTS5 virtual table indexes titles and section text for fast full-text search.

Extracted markdown and JSON files are written to `.docmancer/extracted/` so the indexed content is always inspectable on disk.

Alongside the FTS5 index, each section is embedded with FastEmbed (local dense + SPLADE sparse) and upserted into a managed local Qdrant. The dispatcher reads both stores at query time. For which documentation sites and file types work with `add`, see [Supported Sources](./Supported-Sources.md).

## Retrieval

Queries run against the FTS5 index using BM25 ranking. This is a good fit for documentation retrieval because most queries are dominated by exact API names, option flags, config keys, error strings, and code identifiers.

Results are sections, not whole pages. The query respects a configurable token budget (default: 2400) and returns only the sections that fit. Adjacent sections or full pages can be included with `--expand`. See [Configuration](./Configuration.md) for query budget and expansion defaults.

## Hybrid retrieval

A fresh install runs hybrid retrieval out of the box: each section gets a dense FastEmbed vector and a SPLADE sparse vector in Qdrant, alongside the FTS5 index. Set `DOCMANCER_AUTO_VECTORS=0` (or run `ingest --no-vectors`) to stay on FTS5 only.

Components:

- **`docmancer.runtime.qdrant_manager`** owns the local Qdrant lifecycle: binary acquisition from the pinned `v1.14.1` GitHub release, port selection under `filelock`, background spawn with telemetry disabled, ownership sentinel, foreign-process refusal, and a `SqliteVecStore` fallback when the platform has no matching binary.
- **`docmancer.embeddings`** wraps the embedding providers (`FastEmbedProvider` for local dense + sparse; cloud providers for OpenAI / Voyage / Cohere). A content-hash-keyed disk cache under `~/.docmancer/embeddings-cache/` avoids re-embedding unchanged chunks. The cloud providers retry on 429/5xx with bounded exponential backoff; when a configured cloud provider has no API key in env, ingest falls back to FTS5-only with a warning rather than aborting.
- **`docmancer.embeddings.pipeline.sync_vector_store`** reconciles SQLite sections against existing Qdrant points: it skips unchanged content via the `embedding_upserts` bookkeeping table, prunes points whose chunk ids no longer exist in SQLite (so `ingest --recreate` cannot leave stale dense hits behind), embeds the rest in batches, and bulk-upserts.
- **`docmancer.stores`** wraps both backends behind a `VectorStore` interface. `QdrantStore.ensure_collection` refuses to claim a pre-existing collection that lacks the docmancer ownership sentinel, and `delete_collection` will only operate on docmancer-owned collections.
- **`docmancer.retrieval.dispatch.RetrievalDispatcher`** fans out across `lexical` (FTS5), `dense` (Qdrant or sqlite-vec), and `sparse` (SPLADE in Qdrant) via a thread pool, fuses the per-source ranks with Reciprocal Rank Fusion (vanilla or weighted), and hydrates the top-K section ids back into `RetrievedChunk` rows. Two extensions sit on this path:
    - **Hierarchical retrieval** (`retrieval.hierarchical.enabled: true`) runs in two stages: a wide-net pass aggregates scores by `document_title_hash` and picks the top documents; a second pass re-retrieves sections filtered to those documents before fusion.
    - **Query-aware routing** (`retrieval.routers: [...]`) walks an ordered list of regex matchers; the first match merges its declared filters into the dispatcher filters for that call, for example routing API-reference queries to `source_path_prefix=api`.
- **Neighbor expansion** plumbs through hybrid mode the same way as lexical: after the top section ids are picked, prev/next siblings are appended so partial bullets arrive with their surrounding context.

`docmancer query --mode {lexical,dense,sparse,hybrid} --explain` exposes the mode and shows per-source rank contributions (e.g. `lexical#1, dense#3, sparse#2`) under each result.

## Context packs

The output of `docmancer query` is a compact context pack: the top matching sections, their heading paths, source URLs, version/timestamp metadata, and a token estimate. Each query also reports:

- **Tokens saved** versus the raw full-page docs context
- **Agentic runway multiplier** showing how much more context budget is available for actual work

This feedback loop makes the compression value visible on every query.

## MCP runtime

`docmancer install-pack <package>@<version>` downloads the pack's five artifacts (`contract.json`, `tools.curated.json`, `tools.full.json`, `auth.schema.json`, `provenance.json`) plus a `manifest.json` with SHA-256s, verifies every artifact hash, and writes them under `~/.docmancer/servers/<package>@<version>/`. The package is added to `~/.docmancer/mcp/manifest.json` with per-package state (mode = curated/expanded, allow_destructive, allow_execute, enabled).

When an agent launches `docmancer mcp serve` (registered automatically by `docmancer setup` or `install <agent>`), the server exposes exactly **two** tools to the agent regardless of how many packs are installed:

- `docmancer_search_tools(query, package?, limit)`: token-overlap search across the curated (or full) tool surfaces of every enabled pack. Returns name, description, safety, and inlined `inputSchema` for the top match (lazy schema fetch for the rest).
- `docmancer_call_tool(name, args)`: dispatches the resolved tool through the matching executor.

Every dispatch passes through the gate chain (in order):

1. **Resolve.** Look up the slug `package__version__operation` (D15: double-underscore field separators, single-underscore intra-field replacement of `.`/`-`/`/`) against the manifest.
2. **Validate.** Run `args` through the operation's `inputSchema` with `jsonschema`. Tool Search hides per-tool schemas from the MCP `tools/list` surface, so the dispatcher must validate (spec 2.8.5).
3. **Auth.** Resolve credentials by precedence: per-call override, process env, agent-config env, then the per-package credential fallback. For OpenAPI `apiKey` schemes, place the resolved value in the right slot per `in: header|query|cookie`.
4. **Safety gate.** If the operation is destructive and the package was not installed with `--allow-destructive`, refuse with a remediation message naming the exact `install-pack ... --allow-destructive` command. If the executor is `python_import` or `shell` and the package was not installed with `--allow-execute`, refuse similarly.
5. **Idempotency.** For non-idempotent operations on sources that declare an idempotency header, generate a UUID4 `Idempotency-Key`. A SQLite fingerprint cache (24 h TTL, key = tool + canonicalized args) reuses the same key on retry; the agent can also pass `args._docmancer_idempotency_key` explicitly.
6. **Execute.** Hand off to the executor (`http`, `noop_doc`, `python_import`). The HTTP executor merges `auth.required_headers` declared in the contract (used by keyed APIs that pin a dated wire version), auth headers/params/cookies, and the per-operation `http.encoding` (`json | form | multipart | query_only | path_only`). Path parameters are percent-encoded as one segment, so values containing `/`, `?`, or `#` do not alter the URL structure.
7. **Log.** Append a redacted entry to `~/.docmancer/mcp/calls.jsonl` (only `arg_keys`, never values).

Pack paths are validated and resolved before use: `..` segments, NUL, backslashes, leading `@` in the version, and absolute paths are rejected, and the resolved candidate must remain inside `~/.docmancer/servers`. This keeps a malicious or malformed registry entry from escaping the storage root.

## Concurrency

Multiple CLI calls from parallel agents or terminals are safe. SQLite handles concurrent reads natively, and write operations are serialized by SQLite's built-in locking.

## Flow

```text
Docs:
  GitBook / Mintlify / web / GitHub / local files
    -> SQLite FTS5 sections + Qdrant vectors
    -> docmancer query
    -> context pack + token savings

Agents:
  docmancer setup
    -> skill files for Claude Code, Cursor, Codex, Cline, Gemini, OpenCode,
       GitHub Copilot, and Claude Desktop

MCP packs:
  docmancer install-pack <pkg>@<version>
    -> contract.json, tools.curated.json, tools.full.json, auth.schema.json,
       provenance.json, manifest SHA-256s
    -> docmancer mcp serve
    -> docmancer_search_tools + docmancer_call_tool
```

For details on which documentation sites and file types work with `add`, see [Supported Sources](./Supported-Sources.md). For where skill files land, see [Install Targets](./Install-Targets.md).
