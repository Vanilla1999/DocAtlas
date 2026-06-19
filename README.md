<div align="center">

# Docmancer

**Local, offline-first context packs for coding agents — from your own repository docs.**

[![License: MIT](https://img.shields.io/github/license/Vanilla1999/DocAtlas?style=for-the-badge)](https://github.com/Vanilla1999/DocAtlas/blob/main/LICENSE)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20|%203.12%20|%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/doc-atlas/)

[Quickstart](#quickstart) | [Project docs](#project-docs-mcp-server) | [Commands](./docs/commands.md)

</div>

---

Docmancer compresses documentation context so coding agents spend tokens on code, not rereading raw docs. It ingests local repository files, fetches public docs, indexes everything offline with SQLite FTS5, and returns compact context packs with source attribution.

The executable is at `/home/viadmin/.local/bin/docmancer --config /home/viadmin/StudioProjects/hermes/docmancer/docmancer.yaml`.

## Quickstart

```bash
docmancer list                        # see indexed docs
docmancer ingest ./docs               # index local files
docmancer add https://docs.example.com
docmancer query "how to authenticate"
```

`query` prints estimated raw docs tokens, context-pack tokens, percent saved, and agentic runway:

```text
Context pack: ~900 tokens vs ~4800 raw docs (81.2% less overhead, 5.33x agentic runway)
```

Prefer the compact default. Use `--expand` for adjacent sections and `--expand page` only when the whole page is necessary.

## Core commands

```bash
docmancer setup
docmancer ingest ./docs
docmancer add https://docs.example.com
docmancer update
docmancer query "how to authenticate"
docmancer query "how to authenticate" --limit 10
docmancer query "how to authenticate" --expand
docmancer query "how to authenticate" --expand page
docmancer query "how to authenticate" --format json
docmancer list
docmancer inspect
docmancer remove <source>
docmancer doctor
docmancer fetch <url> --output <dir>
```

## Project-docs MCP server

Docmancer exposes its documentation runtime through a Context7-style MCP server:

```bash
docmancer mcp docs-serve
```

Project-docs tools let agents work with the reviewable documentation files that belong to a repository:

| Tool | Purpose |
|---|---|
| `sync_project_docs` | **Canonical lifecycle action.** Discovers, reconciles, prunes orphaned/stale, and indexes project docs in one call. Prefer over `ingest_project_docs`. |
| `inspect_project_docs` | Read-only discovery: reports discovered candidates, indexed docs, stale/ignored/orphaned sources, reason_code, and next_action. |
| `ingest_project_docs` | Legacy low-level index operation. Does not reconcile — use `sync_project_docs`. |
| `bootstrap_project_docs` | Safe high-level onboarding: inspect, sync if needed, inspect again. Stops before repo writes or network fetches. |
| `get_project_docs` | Query indexed project docs for repo-specific architecture, conventions, README, ADRs, runbooks, or module docs. |
| `get_project_context` | Compact repo-grounded context pack combining project docs with optional dependency-doc evidence and a Trust Contract. |

### Recommended workflow

```text
sync_project_docs(project_path, with_vectors=true)     # discover + reconcile + index
get_project_context(project_path, question)             # compact grounded context
```

For safe high-level onboarding:

```text
bootstrap_project_docs(project_path, question?)
get_project_context(project_path, question)
```

`sync_project_docs` replaces the old two-step `inspect → ingest` loop. It:
1. discovers current candidates from the filesystem;
2. prunes orphaned indexed sources (deleted files);
3. removes stale indexed sections (changed files);
4. indexes new and changed candidates;
5. returns `current_count`, `new_count`, `changed_count`, `orphaned_removed`, and `indexed_sources`.

### Compact MCP responses

All project-docs lifecycle tools return compact responses by default:

```json
{
  "tool": "sync_project_docs",
  "status": "success",
  "current_count": 3,
  "new_count": 1,
  "changed_count": 0,
  "orphaned_removed": 1
}
```

Pass `"details": true` for the full structured response.

### When to use each tool

| Situation | Tool |
|---|---|
| First time in a repo | `sync_project_docs` or `bootstrap_project_docs` |
| Check what docs exist | `inspect_project_docs` (read-only) |
| Reconcile after file changes | `sync_project_docs` |
| Old low-level index (no reconcile) | `ingest_project_docs` |
| Answer "how does this repo work?" | `get_project_context` or `get_project_docs` |

## Project-aware Flutter/Dart docs

Docmancer can inspect a local Flutter/Dart project. It reads `.fvmrc` for Flutter channel/version hints and `pubspec.lock` for pub package versions. This enables exact-version documentation for the dependencies your project actually uses.

## License

MIT
