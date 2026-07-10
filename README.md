<img width="1448" height="1086" alt="68c5f033-e8f3-4331-a88e-cc64bf28fb62" src="https://github.com/user-attachments/assets/78458fed-22c5-4e78-bbb0-67a902948f9c" />
<div align="center">

# DocAtlas

**Local-first documentation context for coding agents — project docs and exact dependency evidence with source attribution.**

[![License: MIT](https://img.shields.io/github/license/Vanilla1999/DocAtlas?style=for-the-badge)](https://github.com/Vanilla1999/DocAtlas/blob/main/LICENSE)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20|%203.12%20|%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/doc-atlas/)

[Quickstart](#quickstart) | [Project docs](#project-docs-mcp-server) | [Commands](./docs/commands.md)

</div>

---

DocAtlas turns reviewable project docs, lockfiles, and dependency documentation into compact, source-attributed context for coding agents. Its default MCP surface is deliberately small so agents select the correct operation reliably.

The default path for repository work is:

```text
get_docs_context → follow a returned prepare_docs action when needed → retry get_docs_context
```

Advanced patch-planning and constraint tools remain available behind `DOCMANCER_MCP_ADVANCED_TOOLS=1`. Their output is advisory and does not replace tests or human review.

## One-line install

Install `uv`, the `doc-atlas` CLI, and register the docs MCP server into your agent — in a single command:

```bash
curl -LsSf https://raw.githubusercontent.com/Vanilla1999/DocAtlas/main/scripts/install.sh | sh
```

The installer sets up `uv` (if missing), runs `uv tool install --upgrade doc-atlas`, then lets you pick which agent(s) to register the DocAtlas docs MCP server (`doc-atlas mcp docs-serve`) into — **Claude Code**, **OpenCode**, and/or **Codex** — and finishes with a version/health check. It is idempotent, so re-running it is safe.

Non-interactive (CI or scripted) usage — pass the agent(s) via env var or positional args:

```bash
# env var must be set on the `sh` process (right of the pipe), not on curl:
curl -LsSf https://raw.githubusercontent.com/Vanilla1999/DocAtlas/main/scripts/install.sh | DOCATLAS_AGENT=claude-code sh
# or pass the agent(s) as positional args:
curl -LsSf https://raw.githubusercontent.com/Vanilla1999/DocAtlas/main/scripts/install.sh | sh -s -- claude-code opencode
# several clients via env var:
curl -LsSf https://raw.githubusercontent.com/Vanilla1999/DocAtlas/main/scripts/install.sh | DOCATLAS_AGENT="claude-code codex opencode" sh
```

Accepted values: `claude-code`, `opencode`, `codex`, `all`, `none`. An unknown value passed via args or `DOCATLAS_AGENT` is a hard error. macOS and Linux only. Prefer the manual steps below on Windows.

For OpenCode, the installer honors `OPENCODE_CONFIG` (full path), falling back to `$XDG_CONFIG_HOME/opencode/opencode.json`. Existing JSONC configs (comments / trailing commas) are parsed; a `.bak` backup is kept on rewrite.

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

By default the server exposes exactly three mutually exclusive tools:

| Tool | Purpose |
|---|---|
| `get_docs_context` | Default first call for project, library, dependency, or mixed documentation questions. It performs read-only preflight and returns the next action when preparation is required. |
| `prepare_docs` | Lifecycle work only: sync, refresh, index, or prefetch. Call it from the returned `next_action`, or for an explicit user request. Network actions require approval. |
| `docs_status` | Explicit health, freshness, index, or background-job status requests only. It is not a discovery step. |

### Recommended workflow

For most MCP clients and coding agents:

```text
get_docs_context(question=..., project_path=...)
→ prepare_docs(...) only when returned as next_action
→ retry get_docs_context(...)
```

This makes `get_docs_context` the single high-level entry point. To expose low-level inspection and patch-contract compatibility tools, set `DOCMANCER_MCP_ADVANCED_TOOLS=1`:

```text
get_docs_context
→ get_patch_plan_context
→ get_patch_constraints
→ edit
→ validate_patch_against_constraints
```

`get_patch_plan_context` is a source/dependency/design evidence map for implementation planning. It is not a docs retriever, not a patch generator, and not a constraints validator. Use `get_patch_constraints` separately before editing, then call `validate_patch_against_constraints` after the patch. The workflow is advisory and non-blocking; it does not prove merge safety.

Expected result summary for a Flutter menu planning task: exact relevant files for menu/system/tabs code, `showBottomDialog: not_found`, `PBBottomSheet.open` found in dependency source, a minimal patch path for replacing the inline menu with a bottom sheet, and `verification` including `flutter analyze`. See [`docs/mcp-docs-server.md`](./docs/mcp-docs-server.md) for the example call.

Non-goals: `get_patch_plan_context` does not generate a patch, does not guarantee safe merge, does not index the whole `.pub-cache`, does not replace code reading by the agent, and does not replace constraints validation.

For coding/API/command questions, tools accept `response_style` with `auto`, `snippet-first`, or `evidence-first`. In `auto`, DocAtlas returns a trusted `primary_snippet` first when the selected sources contain a usable code/config/command example, while preserving `context_pack`, source attribution, exact-version diagnostics, and the Trust Contract. Snippets are extracted from indexed documentation; DocAtlas does not synthesize code.

```json
{
  "question": "How do I use FastAPI Depends?",
  "library": "fastapi",
  "response_style": "snippet-first"
}
```

Explicit lifecycle requests can route directly through the public unified tool.

```text
prepare_docs(action="sync_project_docs", project_path=..., with_vectors=true)  # discover + reconcile + index
get_docs_context(project_path=..., question=..., mode="project")               # compact grounded context
```

MCP Packs are an advanced layer for version-pinned API action tools exposed by `doc-atlas mcp packs-serve`. They are useful when an agent needs executable external API operations. They are not an alternative to the three-tool Docs MCP workflow. `doc-atlas mcp serve` remains a compatibility alias for the Packs gateway.

`prepare_docs(action="sync_project_docs")` replaces the old two-step `inspect → ingest` loop. It:
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
| First time in a repo | `get_docs_context`; follow its `next_action` if preparation is needed |
| Check what docs are relevant | `get_docs_context` |
| Check health, freshness, or a job | `docs_status` |
| Reconcile after file changes | `prepare_docs(action="sync_project_docs")` |
| Low-level inspection and patch tools | advanced compatibility surface only |
| Answer "how does this repo work?" | `get_docs_context(mode="project")` |

## Project-aware exact dependency docs

DocAtlas can inspect a local Flutter/Dart project. It reads `.fvmrc` for Flutter channel/version hints and `pubspec.lock` for pub package versions. This enables exact-version documentation for the dependencies your project actually uses.

It also reads direct JavaScript/TypeScript dependencies from `package.json` and resolves their exact installed versions from `package-lock.json`, `pnpm-lock.yaml`, or `yarn.lock`. When several lockfiles exist, the `packageManager` declaration selects the authoritative one; local, workspace, and Git dependencies are never presented as exact registry bindings.

## License

MIT
