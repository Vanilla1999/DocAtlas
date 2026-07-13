<img width="1448" height="1086" alt="68c5f033-e8f3-4331-a88e-cc64bf28fb62" src="https://github.com/user-attachments/assets/78458fed-22c5-4e78-bbb0-67a902948f9c" />
<div align="center">

# DocAtlas

**Local-first documentation context for coding agents — project docs and exact dependency evidence with source attribution.**

[![License: MIT](https://img.shields.io/github/license/Vanilla1999/DocAtlas?style=for-the-badge)](https://github.com/Vanilla1999/DocAtlas/blob/main/LICENSE)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20|%203.12%20|%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/doc-atlas/)

[Install](#one-line-install) | [Docs MCP](#project-docs-mcp-server) | [Advanced surfaces](#advanced-surfaces) | [CLI reference](./docs/capabilities.md#end-to-end-examples-of-current-behavior)

</div>

---

DocAtlas turns reviewable project docs, lockfiles, and dependency documentation into compact, source-attributed context for coding agents. Its default MCP surface is deliberately small so agents select the correct operation reliably.

The primary journey is:

```text
install → get_docs_context → follow a returned prepare_docs action when needed → answer with sources
```

For a normal repository question, the agent starts with `get_docs_context`. If it returns a `prepare_docs` next action, the agent follows it, retries the question, and cites the selected project or dependency sources. This is the product's default workflow.

```text
get_docs_context → follow a returned prepare_docs action when needed → retry get_docs_context
```

## One-line install

Install `uv`, the `doc-atlas` CLI, and register the docs MCP server into your agent — in a single command:

```bash
curl -LsSf https://raw.githubusercontent.com/Vanilla1999/DocAtlas/main/scripts/install.sh | sh
```

The installer sets up `uv` (if missing), runs `uv tool install --upgrade doc-atlas`, then lets you pick which agent(s) to register the DocAtlas docs MCP server (`doc-atlas mcp docs-serve`) into — **Claude Code**, **OpenCode**, and/or **Codex** — and finishes with a version/health check. It is idempotent, so re-running it is safe.

> It installs the latest published PyPI package, not unreleased code from `main`. Check `doc-atlas --version` before relying on a workflow newly documented on `main`; use a deliberately checked-out source installation for development changes that have not been released.

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
get_docs_context(question=..., project_path=..., delivery_strategy="bounded_direct")
→ prepare_docs(...) only when returned as next_action
→ retry get_docs_context(..., delivery_strategy="bounded_direct")
```

This makes `get_docs_context` the single high-level entry point. Coding and patch tasks should use `delivery_strategy="bounded_direct"`, which returns a source-bound ActionPacket within the requested total payload budget. For API questions, combine it with `response_style="snippet-first"`.

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

### Change-aware documentation review

`doc-atlas docs-impact` maps a code diff to the maintained repository docs that should be reviewed. It never edits documentation automatically:

```bash
doc-atlas docs-impact --base origin/main
doc-atlas docs-impact --changed-file packages/auth/src/token_service.ts --format json
doc-atlas docs-impact --base origin/main --sync-saved-docs --format json
```

The report includes a bounded authoring brief for the host model: exact files/sections it may edit, repository facts it must verify, and claims it must not invent. After the documentation patch is reviewed and saved, `prepare_docs(action="sync_project_docs", changed_paths=..., deleted_paths=..., renamed_paths=...)` updates only affected index rows. The optional `--sync-saved-docs` CI mode performs that local indexing step from an exact Git diff; it never edits, commits, comments, or fetches from the network.

The bundled GitHub Actions workflow publishes the advisory report in every pull request summary. It highlights module docs that need review and module changes with no maintained documentation, while leaving the final documentation edit to an explicit, reviewable change.

### Agent contract for a local project

Before handing a repository to a coding agent, generate a compact, machine-readable contract. It tells the agent which local documents are authoritative, which dependency versions were detected, and how to select the minimal DocAtlas MCP tool surface:

```bash
doc-atlas agent-contract --project-path . --format json
doc-atlas agent-contract --project-path . --format markdown
```

The contract is read-only. For an explicit health, freshness, index, or job-status request, agents use `docs_status`; otherwise they start with `get_docs_context`. Agents call `prepare_docs` only when that tool returns it as `next_action`, or when a user explicitly requests a refresh or sync.

## Advanced surfaces

MCP Packs are an advanced layer (**support tier: advanced-supported**) of version-pinned API action tools, exposed by `doc-atlas mcp packs-serve`. They are separate from the Docs MCP and are not needed for the workflow above. `doc-atlas mcp serve` is retained only as a deprecated compatibility alias.

Patch planning and patch constraints are **advanced-supported compatibility** tools behind `DOCMANCER_MCP_ADVANCED_TOOLS=1`. They are advisory: they help an agent gather evidence and validate a proposed edit, but never prove that a change is safe to merge or replace tests and review. Detailed usage lives in [the Docs MCP reference](./docs/mcp-docs-server.md).

Qdrant administration, USPTO ingestion, and benchmark operations are **maintenance-only**. Other compatibility CLI commands are labelled directly in `doc-atlas --help`. See the [support-surface policy and machine inventory](./docs/support-surface-policy.md) for ownership, CI tier, network boundaries, compatibility deadlines, and failure budgets; use the [capability reference](./docs/capabilities.md) for command-specific guidance.

## Project-aware exact dependency docs

DocAtlas can inspect a local Flutter/Dart project. It reads `.fvmrc` for Flutter channel/version hints and `pubspec.lock` for pub package versions. This enables exact-version documentation for the dependencies your project actually uses.

It also reads direct JavaScript/TypeScript dependencies from `package.json` and resolves their exact installed versions from `package-lock.json`, `pnpm-lock.yaml`, or `yarn.lock`. When several lockfiles exist, the `packageManager` declaration selects the authoritative one; local, workspace, and Git dependencies are never presented as exact registry bindings.

## License

MIT
