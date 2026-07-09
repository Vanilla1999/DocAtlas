# Architecture

Docmancer is a local, version-aware docs runtime for coding agents. It has two product layers: **Docmancer Docs**, the primary docs context/runtime layer, and **Docmancer Packs**, the advanced API action-tool layer.

Docmancer runs two cooperating local pipelines.

The primary **Docmancer Docs pipeline** fetches documentation with `doc-atlas add` (URL), `doc-atlas ingest` (local files), or the docs MCP server's prefetch tools, normalizes it into sections, indexes those sections in a local SQLite FTS5 database plus a managed local Qdrant for dense and sparse vectors, and retrieves compact context packs through the CLI or MCP docs tools. No hosted query API; the only background process is the docmancer-owned Qdrant.

The advanced **Docmancer Packs runtime** installs version-pinned API packs from a registry with `doc-atlas install-pack <package>@<version>`, then exposes every installed pack to your agent through a single shared stdio MCP server (`doc-atlas mcp serve`) using the Tool Search pattern: two meta-tools regardless of how many packs you install. The dispatcher enforces auth, destructive-call gating, schema validation, idempotency-key auto-injection and reuse, version pinning on the wire, and SHA-256 verification of every artifact before install.

For the full command reference, see [Commands](./Commands.md). For configuration options, see [Configuration](./Configuration.md).

## Indexing

Documentation is fetched from URLs or read from local files, then normalized into semantic sections based on heading structure. Each section is stored in SQLite with its title, heading level, source URL, content hash, and token estimate. A FTS5 virtual table indexes titles and section text for fast full-text search.

Extracted markdown and JSON files are written to `.docmancer/extracted/` so the indexed content is always inspectable on disk.

Alongside the FTS5 index, each section is embedded with FastEmbed (local dense + SPLADE sparse) and upserted into a managed local Qdrant. The dispatcher reads both stores at query time. For which documentation sites and file types work with `add`, see [Supported Sources](./Supported-Sources.md).

## Per-library index isolation

Each library+version has its own independent SQLite index. The `LibraryDocsService._index_config_for` method creates a separate database under `~/.docmancer/docs-indexes/<normalized_name>.db` and a separate extracted directory. This prevents cross-library contamination, enables independent refresh/recreate per target, and keeps the global `docmancer.db` registry lightweight (metadata only).

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

`doc-atlas query --mode {lexical,dense,sparse,hybrid} --explain` exposes the mode and shows per-source rank contributions (e.g. `lexical#1, dense#3, sparse#2`) under each result.

## Context packs

The output of `doc-atlas query` is a compact context pack: the top matching sections, their heading paths, source URLs, version/timestamp metadata, and a token estimate. Each query also reports:

- **Tokens saved** versus the raw full-page docs context
- **Agentic runway multiplier** showing how much more context budget is available for actual work

This feedback loop makes the compression value visible on every query.

## Docs source registry

The `LibraryRegistry` is a SQLite-backed persistent store for known documentation sources. Each entry is identified by three levels of identity:

- **`source_id`** — identity without version (e.g. `pub:go_router:api`). Used for grouping all versions of one library.
- **`canonical_id`** — version-pinned identity (e.g. `pub:go_router@14.8.1:api`). The primary key for upsert and lookup.
- **`library_id`** — current canonical identity (aliased to `canonical_id`). Migrated when the naming scheme changes.

The registry stores per-entry metadata:

| Field | Purpose |
|-------|---------|
| `version`, `source_type` | Resolution axes |
| `docs_url`, `docs_url_template` | Source locator (template supports version interpolation) |
| `docs_url_resolved` | Pre-rendered effective URL |
| `docs_snapshot_exact` | Whether the indexed docs are an exact version snapshot (not latest/stable) |
| `requested_version`, `resolved_version`, `version_source`, `version_confidence`, `version_inferred` | Version provenance audit trail |
| `target_spec_json` | Full fetch target specification (seed URLs, allowed domains, path prefixes, etc.) |
| `last_refreshed_at`, `last_error`, `status` | Lifecycle tracking |
| `legacy_ids_json` | Previous library IDs for backward-compatible lookup |
| `aliases_json` | Alternative names used for matching |

**Lookup cascade**: `get()` tries exact `library_id` match first, then `canonical_id`, then `legacy_id`, then `(normalized_name + ecosystem + version + source_type)`, then partial matches by alias or legacy ID. This handles both version-precise lookups and fuzzy name resolution.

**Migration**: When the canonical naming scheme changes, `migrate_library_id()` renames the entry and stores the old ID in `legacy_ids_json` so existing references still resolve.

## Version-aware dependency resolution

The `ProjectMetadataReader` inspects project metadata to choose the exact documentation version the project uses:

- **`.fvmrc`** — reads Flutter SDK version or channel (stable/beta/main). Determines which `api.flutter.dev` docs to fetch.
- **`pubspec.lock`** — extracts pinned package versions from `packages` map. Used as exact version sources for pub.dev Dartdoc and docs.rs bindings.
- **`pubspec.yaml`** — reads direct dependencies and specifier kinds (exact, range, path, git).
- **`Cargo.toml`** / **`Cargo.lock`** — extracts Rust dependency versions and sources (registry, path, git). Non-registry sources produce warnings about inexact docs binding.

The resolution happens in `LibraryDocsService.get_docs()` when `project_path` is provided and `version` is not explicitly set. For Flutter SDK docs, the version is resolved from `.fvmrc`; for pub packages, from `pubspec.lock`; for Rust packages, from `Cargo.lock`.

## Docs MCP runtime

`doc-atlas mcp docs-serve` exposes the docs runtime to coding agents as MCP tools. It uses the same local ingest, index, update, and query path as the CLI, plus the persistent SQLite registry for known documentation sources.

For repository-specific questions, agents should call `inspect_project_docs(project_path)` first, run `prepare_docs(action="sync_project_docs", project_path=..., with_vectors=true)` when reconciliation is needed, then call `get_docs_context(project_path=..., question=..., mode="project")`. `get_docs_context` returns an answer outline/context pack with a Trust Contract (`selected_sources` plus compatibility aliases where present). Agents should cite trusted sources from the Trust Contract, prefer nested metadata for machine reads, and treat `CHANGELOG.md` as primary evidence only for release-history or "what changed" questions.

If the user asks broadly about "the MCP server", distinguish the two surfaces explicitly:

- **Docs MCP server:** `doc-atlas mcp docs-serve` provides documentation/project/dependency context tools such as `get_library_docs` and `get_project_context`.
- **MCP Packs runtime:** `doc-atlas mcp serve` exposes installed API action packs through `docmancer_search_tools` and `docmancer_call_tool`.

The server exposes the following tools:

### Library docs tools
- **`resolve_library_id`** — Resolve a library from the registry or explicit `docs_url`. Returns source/version metadata. Never requires WebFetch for registered sources.
- **`get_library_docs`** — Resolve, ingest or refresh if needed, then query local documentation. Returns compact context pack with full source identity, version provenance, docs policy (WebFetch rules), and diagnostics. Registered sources do not require `docs_url` on later calls.
- **`refresh_library_docs`** — Refresh one library/version. Supports multi-version refresh.
- **`prefetch_library_docs`** — Download and index one or more versions ahead of time.
- **`inspect_library_docs`** — Inspect one exact documentation target by canonical ID. Returns size, staleness, version provenance.
- **`remove_library_docs`** — Remove one exact target by canonical ID. Deletes index and registry entry.
- **`prune_library_docs`** — Prune old documentation targets with dry-run support.
- **`list_library_docs`** — List locally registered libraries, optionally filtered by stale-only.

### Project docs tools
- **`inspect_project_docs`** — Read-only discovery of project-owned docs candidates and exact dependency metadata. Returns recommended next actions (ingest project docs, prefetch dependency docs, or create architecture doc).
- **`ingest_project_docs`** — Index discovered project-owned docs files (README, docs/, wiki/, ARCHITECTURE, ADR, roadmap). Does not ingest source code, dependency directories, or build outputs.
- **`get_project_docs`** — Query indexed project-owned docs with project-scoped filters. Returns results with staleness indicators; if docs are missing, returns structured next actions instead of a generic failure.
- **`prefetch_project_docs`** — Read project manifests/lockfiles and prefetch exact dependency documentation. Supports Flutter SDK docs, pub.dev Dartdoc, and docs.rs bindings.

### Manifest tools
- **`validate_docs_manifest`** — Validate a `docmancer.docs.yaml` manifest without fetching. Checks target structure, URL security, duplicate IDs, source types, and project-version resolution.
- **`prefetch_docs_manifest`** — Validate and prefetch all targets declared in a `docmancer.docs.yaml`.

### Prefetch and job tools
- **`prefetch_docs_targets`** — Download and index one or more explicit documentation targets with full control over seed URLs, allowed domains, path prefixes, max pages, browser rendering, doc format, and per-target warnings.
- **`get_docs_job_status`** — Return persistent progress for one docs indexing/prefetch job.
- **`list_docs_jobs`** — List docs indexing/prefetch jobs, optionally filtered by status.
- **`cancel_docs_job`** — Request cancellation for a docs indexing/prefetch job.

### docs_url template

The `docs_url_template` parameter supports version interpolation: `template.format(library=library, version=version)`. This is used for ecosystem-standard doc hosts:
- Pub: `https://pub.dev/documentation/{library}/{version}/`
- Docs.rs: `https://docs.rs/{library}/{version}/`

When a template is provided without an explicit `docs_url`, the service renders the template at resolution time.

### Async prefetch and job tracking

`prefetch_library_docs`, `prefetch_docs_manifest`, `prefetch_docs_targets`, and `prefetch_project_docs` support an `async_` parameter. When `async_: true`, the service:
1. Creates a `DocsJob` entry with a UUID4 job ID and `pending` status
2. Starts a daemon background thread to run the fetch/index pipeline
3. Returns immediately with a `DocsJobStartResult` containing the `job_id`

The `DocsJobTracker` maintains an in-memory dictionary of jobs (trimmed to `MAX_DOCS_JOB_HISTORY = 100`). Each job tracks:
- **Lifecycle**: `status` (pending/running/succeeded/partial/failed/cancelled), `phase` (validating/resolving/fetching/indexing/done), timestamps
- **Progress**: `total_targets`, `completed_targets`, `failed_targets`, `current_target`, `current_url`
- **Page tracking**: `discovered_pages`, `fetched_pages`, `indexed_pages`, `total_pages`, `completed_pages`, `failed_pages`, `total_chunks`, `completed_chunks`
- **Events**: ordered event log with phase, URL, and message per target/page

Call `get_docs_job_status(job_id)` to poll progress. Jobs can be cancelled via `cancel_docs_job(job_id)`; the cancellation flag is checked between targets and between seed URLs during a target.

### docmancer.docs.yaml manifest

The manifest is a YAML file that declares a batch of documentation targets:

```yaml
version: 1
defaults:
  source_type: api
  allowed_domains:
    - docs.example.com
targets:
  - id: my-lib
    library: my-lib
    version: "2.1.0"
    docs_url: https://docs.example.com/my-lib/2.1/
    allowed_domains:
      - docs.example.com
  - id: project-dep
    library: some-dep
    ecosystem: pub
    version: project-version
    project_version:
      package: some-dep
      fallback: latest
```

`validate_docs_manifest` checks structure, duplicate IDs/`canonical_id`, URL security (no private/localhost URLs, allowed domain validation), source type validity, and `project-version` resolution. `prefetch_docs_manifest` runs validation then delegates to `prefetch_docs_targets`.

### Dartdoc discovery

For pub.dev Dartdoc targets (ecosystem `pub`, source type `api`), the service can automatically discover seed URLs from the package's documentation index page. `discover_pub_dartdoc_seed_urls` parses the package root HTML with BeautifulSoup, extracting entity pages (`-class.html`, `-library.html`, etc.) and library pages. This produces precise seed URLs instead of crawling the entire pub.dev domain, reducing fetch time and network load.

Fallback: if discovery fails or returns no URLs, the service falls back to the root documentation URL as a single seed.

### URL security and docs policy

All remote URLs pass through security validation:
- Only `http`/`https` schemes allowed
- Localhost, private network, loopback, link-local, and multicast addresses rejected
- URL host must match one of the `allowed_domains`
- URL path must match one of the `path_prefixes` (if specified)

The docs policy system in `_docs_policy` produces machine-readable WebFetch rules for agents:

```json
{"direct_webfetch": "forbidden", "reason_code": "registered_source_exists"}
{"direct_webfetch": "discovery_only", "reason_code": "no_registered_source"}
```

Registered sources forbid direct WebFetch (agent must use Docmancer). Unknown sources permit discovery-mode WebFetch only.

### Version provenance on every response

Every `DocsResult` includes a full version identity block:
- `requested_version` — what was asked for
- `resolved_version` — what was actually resolved
- `version_source` — how the version was determined (`explicit`, `project`, `lockfile_exact`, `manifest_exact`, `manifest_range`, `registry`)
- `docs_snapshot_exact` — whether the indexed docs are an exact version snapshot
- `docs_exactness` — categorized value (`exact_snapshot`, `exact_version_url`, `no_docs`)
- `docs_binding_source` — where the docs were bound from (`registry`, `pub_dartdoc`, `docs_rs`, `flutter_api_current_channel`)
- `confidence` — high-level confidence indicator
- `tool` / `schema_version` — always `get_library_docs` / `2.0-mvp`

When the input `docs_url` conflicts with a registered source's stored locator, the service returns `docs_url_conflict` status with the registered source's identity, guiding the agent to retry without `docs_url`.

## Project Docs pipeline

The project-aware docs pipeline runs alongside the library docs pipeline, using the same ingestion engine but with project-scoped source classes and metadata.

### Discovery

`ProjectMetadataReader.discover_docs` scans the repository for documentation files:
- **Root doc files**: README, ARCHITECTURE.md, CHANGELOG, CONTRIBUTING, SECURITY, LICENSE (by name at project root)
- **Doc directories**: `docs/`, `doc/`, `wiki/`, `adr/`, `roadmap/`, `runbooks/` (recursively)
- **Excluded**: `.git`, `venv`, `node_modules`, build directories, caches

Each candidate is hashed (SHA-256, chunked) and tracked with path, reason, size, and mtime for staleness detection.

### Staleness detection

The service partitions project docs into three states:
- **Current** — indexed with matching content hash and mtime
- **Stale** — indexed but content hash or mtime differs; re-index recommended
- **Ignored** — indexed but no longer discovered (file was deleted or moved)

`get_project_docs` returns results with per-chunk `stale` flags. When stale sources exist, the response includes a `next_actions` entry recommending `ingest_project_docs` before relying on the answers.

### Next action orchestration

When project docs are missing, `get_project_docs` returns structured `next_actions` instead of a generic failure:

1. **No candidates found** — suggests creating a reviewable `ARCHITECTURE.md`, then running `inspect_project_docs` -> `ingest_project_docs` -> `get_project_docs`
2. **Candidates found but not indexed** — suggests `ingest_project_docs`
3. **Indexed but stale** — suggests re-ingest
4. **Exact dependency versions available** — suggests `prefetch_project_docs` (requires network, so marked `requires_confirmation: true`)

This creates an agent-discoverable onboarding path where the agent guides itself through the setup steps.

## Packs MCP runtime

`doc-atlas install-pack <package>@<version>` downloads the pack's five artifacts (`contract.json`, `tools.curated.json`, `tools.full.json`, `auth.schema.json`, `provenance.json`) plus a `manifest.json` with SHA-256s, verifies every artifact hash, and writes them under `~/.docmancer/servers/<package>@<version>/`. The package is added to `~/.docmancer/mcp/manifest.json` with per-package state (mode = curated/expanded, allow_destructive, allow_execute, enabled).

When an agent launches `doc-atlas mcp serve` (registered automatically by `doc-atlas setup` or `install <agent>`), the server exposes exactly **two** tools to the agent regardless of how many packs are installed:

- `docmancer_search_tools(query, package?, limit)`: BM25-style search with lightweight synonym expansion across the curated (or full) tool surfaces of every enabled pack. Returns name, description, safety, and inlined `inputSchema` for every returned match.
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

Per-library locks (`filelock`-based under `~/.docmancer/locks/`) serialize refresh/ingest operations for the same library to prevent concurrent modification of a per-library index.

## Flow

```text
Docs (library):
  GitBook / Mintlify / web / GitHub / local files
    -> SQLite FTS5 sections + Qdrant vectors (per-library index)
    -> doc-atlas query / get_library_docs
    -> context pack + token savings + version provenance

Docs (project-aware):
  Repo files: README, docs/, wiki/, ADR, ARCHITECTURE, roadmap
    -> SHA-256 content hash, staleness check
    -> ingest_project_docs / get_project_docs
    -> project-scoped context pack + stale indicators + next actions

  Dependencies: pubspec.lock, Cargo.lock, .fvmrc
    -> exact version resolution
    -> prefetch_project_docs / get_library_docs(project_path=...)
    -> version-pinned docs from pub.dev Dartdoc / docs.rs / api.flutter.dev

Manifest:
  docmancer.docs.yaml
    -> validate_docs_manifest / prefetch_docs_manifest
    -> batch prefetch with job tracking

Agents:
  doc-atlas setup
    -> skill files for Claude Code, Cursor, Codex, Cline, Gemini, OpenCode,
       GitHub Copilot, and Claude Desktop

MCP packs:
  doc-atlas install-pack <pkg>@<version>
    -> contract.json, tools.curated.json, tools.full.json, auth.schema.json,
       provenance.json, manifest SHA-256s
    -> doc-atlas mcp serve
    -> docmancer_search_tools + docmancer_call_tool
```

For details on which documentation sites and file types work with `add`, see [Supported Sources](./Supported-Sources.md). For where skill files land, see [Install Targets](./Install-Targets.md).
