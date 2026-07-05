<img width="1448" height="1086" alt="68c5f033-e8f3-4331-a88e-cc64bf28fb62" src="https://github.com/user-attachments/assets/78458fed-22c5-4e78-bbb0-67a902948f9c" />
<div align="center">

# DocAtlas

**Project Patch Contract Runtime for coding agents — local, source-attributed constraints from your repository docs and dependency evidence.**

[![License: MIT](https://img.shields.io/github/license/Vanilla1999/DocAtlas?style=for-the-badge)](https://github.com/Vanilla1999/DocAtlas/blob/main/LICENSE)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20|%203.12%20|%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/doc-atlas/)

[Quickstart](#quickstart) | [Project docs](#project-docs-mcp-server) | [Commands](./docs/commands.md)

</div>

---

DocAtlas turns reviewable project docs, lockfiles/dependency docs, and local code evidence into source-attributed Patch Contracts for coding agents. The runtime keeps agents on the project-owned path before they edit, then provides deterministic advisory validation and PR artifacts after a patch.

The first path for repository work is:

```text
get_docs_context → get_patch_constraints → edit → validate_patch_against_constraints → advisory PR artifacts
```

Patch Contract output is advisory and non-blocking: it highlights source-backed constraints, deterministic violations, and unknown/manual-review areas, but it does not prove a patch is safe to merge.

## Naming and compatibility

The product name is **DocAtlas**.

The PyPI package and CLI command are:

```bash
pipx install doc-atlas
doc-atlas --help
```

Some internal Python modules, storage paths, and older documentation may still use the legacy name `docmancer`, for example `docmancer/` or `~/.docmancer/`. Treat those as compatibility/internal names unless this README explicitly says otherwise.

Use `doc-atlas ...` for user-facing commands in new documentation. Configuration files may still be named `docmancer.yaml` for compatibility.

## Quickstart

```bash
doc-atlas list                        # see indexed docs
doc-atlas ingest ./docs               # index local files
doc-atlas add https://docs.example.com
doc-atlas query "how to authenticate"
```

`query` prints estimated raw docs tokens, context-pack tokens, percent saved, and agentic runway:

```text
Context pack: ~900 tokens vs ~4800 raw docs (81.2% less overhead, 5.33x agentic runway)
```

Prefer the compact default. Use `--expand` for adjacent sections and `--expand page` only when the whole page is necessary.

## Core commands

```bash
doc-atlas setup
doc-atlas ingest ./docs
doc-atlas add https://docs.example.com
doc-atlas update
doc-atlas query "how to authenticate"
doc-atlas query "how to authenticate" --limit 10
doc-atlas query "how to authenticate" --expand
doc-atlas query "how to authenticate" --expand page
doc-atlas query "how to authenticate" --format json
doc-atlas list
doc-atlas inspect
doc-atlas remove <source>
doc-atlas doctor
doc-atlas fetch <url> --output <dir>
```

## Project-docs MCP server

DocAtlas exposes its local project-constraint and documentation runtime through an MCP docs server:

```bash
doc-atlas mcp docs-serve
```

Project-docs tools let agents start from reviewable repository files, then move into a source-attributed Patch Contract before editing:

| Tool | Purpose |
|---|---|
| `get_docs_context` | Recommended first call. Returns project, library, dependency, or mixed documentation context and routes patch-like tasks toward `get_patch_constraints`. |
| `get_patch_constraints` | Builds a compact, source-attributed Patch Contract for the requested coding change. |
| `validate_patch_against_constraints` | Performs deterministic advisory checks after a patch and keeps semantic uncertainty as unknown/manual review. |
| `sync_project_docs` | **Canonical lifecycle action.** Discovers, reconciles, prunes orphaned/stale, and indexes project docs in one call. Prefer over `ingest_project_docs`. |
| `inspect_project_docs` | Read-only discovery: reports discovered candidates, indexed docs, stale/ignored/orphaned sources, reason_code, and next_action. |
| `ingest_project_docs` | Legacy low-level index operation. Does not reconcile — use `sync_project_docs`. |
| `bootstrap_project_docs` | Safe high-level onboarding: inspect, sync if needed, inspect again. Stops before repo writes or network fetches. |
| `get_project_docs` | Query indexed project docs for repo-specific architecture, conventions, README, ADRs, runbooks, or module docs. |
| `get_project_context` | Compact repo-grounded context pack combining project docs with optional dependency-doc evidence and a Trust Contract. |

### Recommended workflow

For most MCP clients and coding agents, start with the unified high-level tool:

```text
get_docs_context(question, project_path?, library?, mode="auto")
```

DocAtlas provides one high-level MCP entry point for project, library, dependency, and mixed documentation context. For patch-like tasks, follow its next action to `get_patch_constraints`, make the code change, then call `validate_patch_against_constraints` and attach the non-blocking review artifacts. It does not replace the lane-specific tools, and it does not fetch missing docs automatically unless the caller explicitly allows network work.

For coding/API/command questions, tools accept `response_style` with `auto`, `snippet-first`, or `evidence-first`. In `auto`, DocAtlas returns a trusted `primary_snippet` first when the selected sources contain a usable code/config/command example, while preserving `context_pack`, source attribution, exact-version diagnostics, and the Trust Contract. Snippets are extracted from indexed documentation; DocAtlas does not synthesize code.

```json
{
  "question": "How do I use FastAPI Depends?",
  "library": "fastapi",
  "response_style": "snippet-first"
}
```

Advanced users can still call lane-specific tools directly.

```text
sync_project_docs(project_path, with_vectors=true)     # discover + reconcile + index
get_project_context(project_path, question)             # compact grounded context
```

MCP Packs are an advanced layer for version-pinned API action tools. They are useful when an agent needs executable API operations, but the default repository workflow is the Patch Contract Runtime above.

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

DocAtlas can inspect a local Flutter/Dart project. It reads `.fvmrc` for Flutter channel/version hints and `pubspec.lock` for pub package versions. This enables exact-version documentation for the dependencies your project actually uses.

## License

MIT
