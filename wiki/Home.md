# DocAtlas Wiki

This wiki is the deep-dive reference for DocAtlas's local, version-aware documentation runtime for coding agents. The [README](../README.md) is the on-ramp: install, quickstart lanes, and a high-level overview. Once you need flags, YAML keys, or internals, you're in the right place.

## Pick a page

| Page | What's there |
|------|--------------|
| **[Commands](./Commands.md)** | Core docs runtime commands, docs MCP commands, advanced pack commands, and options |
| **[Patch-review bot artifacts](./Patch-Review-Bot-Artifacts.md)** | Advisory PR-bot JSON artifact discovery, schema, and safe-usage contract |
| **[Configuration](./Configuration.md)** | `docmancer.yaml` reference, env vars, **API keys**, and a tuned hybrid example |
| **[Architecture](./Architecture.md)** | Indexing pipeline, hybrid retrieval, registry/source identity, version-aware resolution, project docs pipeline, docs MCP tools, job tracking, manifests, packs runtime, concurrency |
| **[Supported Sources](./Supported-Sources.md)** | File formats, URL providers, and the MCP pack source standards |
| **[Install Targets](./Install-Targets.md)** | Where `doc-atlas install <agent>` drops skill files for each supported agent |
| **[MCP Packs](./MCP-Packs.md)** | Advanced layer: installing version-pinned API action packs and how the dispatcher routes calls |
| **[Troubleshooting](./Troubleshooting.md)** | Common errors and their fixes |

## What lives where

- **`~/.docmancer/docmancer.yaml`**: global config (auto-created on first run).
- **`~/.docmancer/docmancer.db`**: SQLite FTS5 index.
- **`~/.docmancer/extracted/`**: inspectable Markdown + JSON copy of every indexed section.
- **`~/.docmancer/qdrant/`**: managed Qdrant binary, storage, runtime metadata, logs.
- **`~/.docmancer/models/`**: FastEmbed dense and sparse model cache.
- **`~/.docmancer/embeddings-cache/`**: content-hash-keyed cache of embedded chunks.
- **`./docmancer.yaml`**: project-local config when present (overrides the global one).

Override the storage root with `DOCMANCER_HOME=/some/path`.

## Licensing

docmancer is MIT-licensed and runs entirely on your machine. The default retrieval stack (FastEmbed embeddings, local Qdrant) needs no API keys. Cloud embedding providers are opt-in; see [Configuration > API keys](./Configuration.md#api-keys).
