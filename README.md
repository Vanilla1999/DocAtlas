<div align="center">

**Local, version-aware docs runtime for coding agents.**

[![PyPI version](https://img.shields.io/pypi/v/docmancer?style=for-the-badge)](https://pypi.org/project/docmancer/)
[![License: MIT](https://img.shields.io/github/license/docmancer/docmancer?style=for-the-badge)](https://github.com/docmancer/docmancer/blob/main/LICENSE)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20|%203.12%20|%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/docmancer/)

[Install](#install) | [Quickstart lanes](#quickstart-lanes) | [What you get](#what-you-get) | [Docs MCP server](#documentation-mcp-server) | [Wiki](./wiki/Home.md)

<img src="readme-assets/demo.gif" alt="Local docs ingest and query demo" style="width: 67%; max-width: 720px; height: auto;" />

</div>

---

Docmancer gives coding agents local, version-aware docs context. It indexes repo docs, docs sites, package references, and private documentation into compact context packs with source attribution, then serves them locally through a CLI or MCP docs server.

The main product is **Docmancer Docs**: a local docs runtime that lets agents answer from the documentation your project actually uses instead of relying on model memory, latest-only hosted pages, or repeated WebFetch calls. **Docmancer Packs** are the advanced layer: version-pinned API action tools for agents that need to call APIs, not just read docs.

A fresh install ships everything you need: SQLite FTS5, a docmancer-owned local Qdrant for dense and sparse vectors, FastEmbed for embeddings (no API key), and a hybrid retriever that fuses lexical, dense, and sparse signals with Reciprocal Rank Fusion.

## Install

```bash
pipx install docmancer    # Python 3.11, 3.12, or 3.13
```

If `pipx` picks an unsupported interpreter, pin one: `pipx install docmancer --python python3.13`.

## Quickstart lanes

Pick the lane that matches the outcome you want. First success comes before optimization: the default setup path is local-first and works without an API key.

### 1. Index docs for CLI and coding agents

Fastest first success uses lexical retrieval now, then you can opt into local hybrid later:

```bash
docmancer setup --profile cli-docs --yes            # config + database, no prompt
docmancer ingest ./docs                             # index local files
docmancer query "How do I authenticate?" --explain  # grounded local context
```

`setup` creates `~/.docmancer/` with the config and SQLite database, then prints a readiness summary and the next best command. To connect an agent non-interactively:

```bash
docmancer setup --profile agent --agent claude-code --yes
```

Prefer a project-local config and no vector/model downloads during first run?

```bash
docmancer setup --project-local --offline --vectors off --yes
```

When you are ready for higher-quality retrieval, switch to local hybrid:

```bash
docmancer setup --retrieval-profile local-hybrid --yes
```

Prefer to index a docs site instead of local files?

```bash
docmancer add https://docs.pytest.org
docmancer query "How do I parametrize a fixture?" --mode hybrid
```

### 2. Versioned MCP Docs

Run the docs MCP server when you want an agent to resolve and query registered library docs from inside its normal tool loop:

```bash
docmancer setup --profile mcp-docs --yes
docmancer mcp docs-serve
```

Register docs once, then query them without repeating the URL:

```json
{
  "library": "pytest",
  "topic": "parametrize fixture",
  "docs_url": "https://docs.pytest.org/"
}
```

Later calls can use just the library and topic. Project-aware version resolution currently focuses on Flutter/Dart metadata such as `.fvmrc` and `pubspec.lock`; other ecosystems are roadmap items.

### 3. Action Packs

When an agent needs to call APIs, install a version-pinned pack:

```bash
docmancer install-pack open-meteo@v1
docmancer mcp serve
```

Packs are an advanced workflow. Start with Docs when your goal is grounded answers from local/version-aware documentation.

## What you get

**Local, version-aware docs context.** Docmancer can keep separate entries for package versions, channels, and sources. MCP docs responses include version metadata such as requested/resolved version and whether the docs snapshot is exact.

**Compact context packs.** Results are source-grounded sections, not raw pages. The token budget keeps responses small so your agent has room for actual work:

```text
Context pack: ~900 tokens vs ~4800 raw docs tokens (81.2% less docs overhead, 5.33x agentic runway)
```

**No API keys required.** FastEmbed runs locally. The optional OpenAI / Voyage / Cohere providers exist if you want them; if the key is missing, ingest falls back to FTS5-only and warns rather than aborting.

**Hybrid search by default.** `query` fans out across SQLite FTS5 (lexical, BM25-reranked), Qdrant dense vectors (FastEmbed `bge-base-en-v1.5`), and SPLADE sparse vectors, then fuses results with Reciprocal Rank Fusion.

**Inspectable.** Every section is written to `~/.docmancer/extracted/` as Markdown plus JSON. `docmancer list` shows source status, freshness, content counts, vector state, failures, and next actions. `docmancer inspect <source>` shows a source card. `docmancer query --explain` or `--explain-json trace.json` shows why results were selected.

**Actionable diagnostics.** `docmancer doctor` answers “what prevents docs context in this path?” with severity, impact, exact fix command, expected result, restart requirement, and auto-fix availability. Use `docmancer doctor --json`, `--list-checks`, or `--check sources` for automation.

**Agent integration built in.** `docmancer setup` drops skill files for Claude Code, Cursor, Codex, Cline, Claude Desktop, Gemini, GitHub Copilot, and OpenCode. Your agent can call `docmancer query` directly from its conversation loop.

## Documentation MCP server

Docmancer Docs includes a Context7-style MCP server for local, version-aware library documentation:

```bash
docmancer mcp docs-serve
```

Example MCP client config:

```json
{
  "mcpServers": {
    "docmancer-docs": {
      "command": "docmancer",
      "args": ["mcp", "docs-serve"]
    }
  }
}
```

Tools:

- `resolve_library_id`
- `get_library_docs`
- `refresh_library_docs`
- `prefetch_library_docs`
- `prefetch_project_docs`
- `prefetch_docs_targets`
- `prefetch_docs_manifest`
- `list_library_docs`
- `inspect_library_docs`
- `get_docs_job_status`
- `list_docs_jobs`
- `cancel_docs_job`

The docs server uses the same local ingest, index, update, and query path as the CLI. It keeps a small persistent library registry in the Docmancer SQLite database. Libraries are stale when they have never been refreshed or when `last_refreshed_at` is older than 30 days. `get_library_docs` refreshes stale docs before querying, and `force_refresh: true` refreshes even fresh docs.

Pass `docs_url` the first time you ask for an unknown library. After registration, later queries can use the stored source and do not need the URL again. The server resolves existing registry entries, project-aware versions, or explicit URLs; it does not guess arbitrary package documentation URLs.

```json
{
  "library": "pytest",
  "topic": "parametrize fixture",
  "docs_url": "https://docs.pytest.org/"
}
```

### Prefetch progress

Long-running docs prefetch operations can run synchronously or asynchronously.

By default, `prefetch_docs_targets` and `prefetch_docs_manifest` run synchronously (`async: false`) and return after downloading/indexing finishes. Synchronous results include final metrics such as `duration_ms`, `pages_indexed`, `pages_failed`, `chunks_indexed`, `targets_completed`, and `targets_failed`.

Pass `async: true` to start a background job and return immediately:

```json
{
  "targets": [
    {
      "library": "riverpod-guides",
      "ecosystem": "web",
      "version": "latest",
      "source_type": "guides",
      "seed_urls": ["https://riverpod.dev/docs/introduction/getting_started"],
      "allowed_domains": ["riverpod.dev"],
      "path_prefixes": ["/docs/"]
    }
  ],
  "async": true
}
```

The async response contains a job id:

```json
{
  "job_id": "string",
  "status": "running",
  "message": "Started docs prefetch job."
}
```

Poll progress with `get_docs_job_status`:

```json
{
  "job_id": "string"
}
```

Job status includes target/page/chunk counters, current target, compact per-target summaries, warnings, errors, timestamps, and phases such as `validating`, `resolving`, `fetching`, `indexing`, `finalizing`, and `done`.

Use `list_docs_jobs` to see recent jobs, optionally filtered by `status`, and `cancel_docs_job` to request cancellation. Cancellation is checked between targets/pages; an in-progress indexing step may finish before the job stops.

Async jobs are in-memory and process-local. Jobs disappear when the MCP server process restarts, and the in-memory history is capped at 100 jobs. Polling with `get_docs_job_status` is the reliable progress path. MCP progress notifications are not implemented. `chunks_indexed` may be approximate because the current indexing API reports pages, not exact chunk counts.

### Versioned documentation

Docs MCP can keep separate local entries per library version. Canonical ids include source identity and version metadata, for example:

- `pub:go_router@14.8.1:api`
- `pub:go_router@16.2.0:api`
- `pub:go_router@latest:api`
- `flutter:flutter-api@stable:api`
- `flutter:flutter-api@main:api`

Use `prefetch_library_docs` to download and index multiple versions ahead of time:

```json
{
  "library": "go_router",
  "ecosystem": "pub",
  "versions": ["14.8.1", "15.0.0", "16.2.0", "latest"],
  "docs_url_template": "https://pub.dev/documentation/{library}/{version}/"
}
```

`docs_url_template` supports `{library}` and `{version}`. For pub.dev packages, `{library}` preserves underscores, so `go_router` renders as `go_router`, not `go-router`. Each rendered URL is stored and refreshed independently, so stale checks and force refresh apply per version.

Use `refresh_library_docs` when you want to refresh one registered library/version. It still accepts `versions` for compatibility, but `prefetch_library_docs` is the clearer tool for ahead-of-time multi-version indexing.

Query a specific version:

```json
{
  "library": "go_router",
  "ecosystem": "pub",
  "version": "14.8.1",
  "topic": "ShellRoute nested navigation"
}
```

If no version is provided and a `latest` entry exists, the server uses it and returns a warning: `No version was provided; using latest/default docs.`

### Project-aware Flutter/Dart docs

`get_library_docs` can inspect a local Flutter/Dart project when `project_path` is provided. It reads `.fvmrc` for Flutter channel/version hints and `pubspec.lock` for pub package versions. Explicit `version` always wins over project metadata.

```json
{
  "library": "go_router",
  "ecosystem": "pub",
  "topic": "ShellRoute nested navigation",
  "project_path": "/path/to/flutter_app"
}
```

If `pubspec.lock` contains `go_router: 14.8.1`, the server resolves `go_router@14.8.1` and uses:

```text
https://pub.dev/documentation/{library}/{version}/
```

Pub package versions from `pubspec.lock` are treated as exact docs snapshots. Responses include version metadata such as `requested_version`, `resolved_version`, `version_source`, `docs_snapshot_exact`, and `warnings` when available.

For Flutter/Dart API references generated by Dartdoc, prefer concrete class or library pages over package/API root pages. Root pages on `api.flutter.dev` and `pub.dev/documentation/...` can be sparse or JavaScript-heavy, while class/library pages often include useful static HTML.

Use `doc_format: "dartdoc"` for Dartdoc targets. This enables a Dartdoc-specific extractor for class/library descriptions, constructors, properties, methods, signatures, code examples, and list/table-heavy API sections without turning on browser rendering by default:

```json
{
  "library": "flutter-layout-widgets-api",
  "ecosystem": "flutter",
  "version": "stable",
  "source_type": "api",
  "doc_format": "dartdoc",
  "seed_urls": [
    "https://api.flutter.dev/flutter/widgets/SizedBox-class.html",
    "https://api.flutter.dev/flutter/widgets/Container-class.html"
  ],
  "allowed_domains": ["api.flutter.dev"],
  "path_prefixes": ["/flutter/widgets/"],
  "docs_snapshot_exact": false
}
```

For pub.dev package APIs, pin exact versions when possible:

```json
{
  "library": "go_router-api",
  "ecosystem": "pub",
  "version": "17.2.3",
  "source_type": "api",
  "doc_format": "dartdoc",
  "seed_urls": [
    "https://pub.dev/documentation/go_router/17.2.3/go_router/ShellRoute-class.html",
    "https://pub.dev/documentation/go_router/17.2.3/go_router/GoRouter-class.html"
  ],
  "allowed_domains": ["pub.dev"],
  "path_prefixes": ["/documentation/go_router/17.2.3/"],
  "docs_snapshot_exact": true
}
```

`browser: true` remains available for JavaScript-heavy pages, but it is not the first choice for Dartdoc class/library pages because those pages usually expose static HTML that the Dartdoc extractor can read directly.

For ahead-of-time project prefetch, use `prefetch_project_docs`. It does not index every transitive dependency; pass the packages you want:

```json
{
  "project_path": "/path/to/flutter_app",
  "include_flutter": true,
  "include_dart": false,
  "include_packages": ["go_router", "riverpod"]
}
```

If a selected package is missing from `pubspec.lock`, the result includes `Package was not found in pubspec.lock.` If no version can be resolved, the result includes `No version was found in project metadata; using latest/default docs.`

For Flutter, keep the stable API docs and main API docs as separate versions:

```json
{"library": "flutter-api", "version": "stable", "docs_url": "https://api.flutter.dev/"}
{"library": "flutter-api", "version": "main", "docs_url": "https://main-api.flutter.dev/"}
```

Flutter channels can be represented directly as `version: "stable"` and `version: "main"`. Keep the API docs separate from the broader Flutter website if you need channel-specific API answers.

If `.fvmrc` contains a pinned Flutter SDK such as `3.24.5`, Docmancer uses it as a project version hint, but it does not create `flutter-api@3.24.5` for `https://api.flutter.dev/`. That URL is current stable API docs, so the canonical id is `flutter-api@stable`, `docs_snapshot_exact` is `false`, and the response warns that the docs are not an exact archived snapshot.

For pub.dev package APIs, prefer explicit package versions plus `latest`:

```json
{
  "library": "riverpod",
  "ecosystem": "pub",
  "versions": ["2.6.1", "3.0.0", "latest"],
  "docs_url_template": "https://pub.dev/documentation/{library}/{version}/"
}
```

Limitations: the server does not discover package versions automatically, does not infer release channels from source files, and does not guess documentation URLs. Pass explicit versions and URLs/templates when registering docs.

## Where to next

The wiki is the authoritative reference for everything else. Pick a page based on what you need:

| Page | When to read it |
|------|-----------------|
| **[Commands](./wiki/Commands.md)** | Core docs commands and advanced pack commands |
| **[Configuration](./wiki/Configuration.md)** | All YAML keys, env vars, and the API-key reference |
| **[Architecture](./wiki/Architecture.md)** | How ingest, retrieval, and MCP runtime actually work |
| **[Supported Sources](./wiki/Supported-Sources.md)** | What file formats and URL providers are covered |
| **[Install Targets](./wiki/Install-Targets.md)** | Where each agent's skill file lands |
| **[MCP Packs](./wiki/MCP-Packs.md)** | Version-pinned API tool packs |
| **[Troubleshooting](./wiki/Troubleshooting.md)** | Common errors and fixes |

[Wiki home](./wiki/Home.md) | [Changelog](./CHANGELOG.md) | [PyPI](https://pypi.org/project/docmancer/)
