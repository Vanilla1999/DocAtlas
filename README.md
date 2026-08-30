<img width="1448" height="1086" alt="68c5f033-e8f3-4331-a88e-cc64bf28fb62" src="https://github.com/user-attachments/assets/78458fed-22c5-4e78-bbb0-67a902948f9c" />
<div align="center">

# DocAtlas

**Local-first, version-bound documentation authority and evidence delivery for coding agents.**

[![License: MIT](https://img.shields.io/github/license/Vanilla1999/DocAtlas?style=for-the-badge)](https://github.com/Vanilla1999/DocAtlas/blob/main/LICENSE)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20|%203.12%20|%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/doc-atlas/)

[Install](#one-line-install) | [Docs MCP](#project-docs-mcp-server) | [Advanced surfaces](#advanced-surfaces) | [CLI reference](./docs/capabilities.md#end-to-end-examples-of-current-behavior)

</div>

---

## What DocAtlas is and what problem it solves

Local-first documentation context remains the runtime foundation: DocAtlas solves the problem of coding agents guessing from stale or generic documentation. It turns reviewable project docs, lockfiles, and approved dependency documentation into compact, source-attributed evidence for coding agents. It keeps authority, scope, and version binding explicit and fails closed when mandatory evidence is unavailable. Its default MCP surface is deliberately small so agents select the correct operation reliably.

The primary journey is:

```text
install → get_docs_context → follow a returned prepare_docs action when needed → answer with sources
```

For a normal repository question, the agent starts with `get_docs_context`. If it returns a `prepare_docs` next action, the agent follows it, retries the question, and cites the selected project or dependency sources. This is the product's default workflow.

The advertised runtime ToolSpec objects are the source of truth for the three public tool descriptions and schemas. The packaged `docatlas-agent-contract-v1` workflow fingerprints those exact runtime specs; installed agent guidance carries its SHA-256 identity so schema/guidance drift is detectable.

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
| `prepare_docs` | Lifecycle work only: sync, refresh, index, or prefetch. Call it from bounded `recommended_next_action`, unbounded `next_action`, or an explicit user request. Network actions require approval. |
| `docs_status` | Explicit health, freshness, index, or background-job status requests only. It is not a discovery step. |

### Recommended workflow

For most MCP clients and coding agents:

```text
get_docs_context(question=..., project_path=...)
→ prepare_docs(...) only when returned as recommended_next_action
→ retry get_docs_context(...)
```

This makes `get_docs_context` the single high-level entry point. Narrow typed questions with complete relation-specific proof receive `docs_answer`; broader questions receive cited retrieval-only `docs_context`; coding and patch tasks receive source-bound `patch_context`; missing safe evidence returns fail-closed `insufficient_evidence`. When completeness or the requested relation is uncertain, the server chooses `docs_context`, not `docs_answer`. Delivery strategy, debug shape, and packet budget are server-owned policy.

MCP responses carry the complete payload in `structuredContent` and only a constant marker in text. OpenCode registration automatically sets `DOCATLAS_MCP_TEXT_FALLBACK=1` because current OpenCode releases do not preserve `structuredContent` in model-visible tool output; manually configured OpenCode entries need the same environment setting. Other clients retain the structured lane. Fallback switches to text-only JSON instead of sending the payload twice. Previously accepted advanced arguments remain available during the compatibility transition but are no longer advertised to normal coding agents.

An optional provider-neutral [one-call host-loop contract](./docs/one-call-agent-loop.md) locally enforces cumulative request, retained-history, repair, test, and output budgets after a model initiates DocAtlas retrieval. Existing generic clients remain supported but are not labelled verified unless their host proves every required control.

`prepare_docs(action="sync_project_docs")` replaces the old two-step `inspect → ingest` loop. It:
1. discovers current candidates from the filesystem;
2. prunes orphaned indexed sources (deleted files);
3. removes stale indexed sections (changed files);
4. indexes new and changed candidates;
5. returns `current_count`, `new_count`, `changed_count`, `orphaned_removed`, and `indexed_sources`.

For an unknown library, DocAtlas does not guess a documentation site silently. It asks for a source and offers `prepare_docs(action="discover_library_docs", ...)`. After approval, this action reads bounded package-registry metadata (PyPI or npm) or constructs the canonical Pub/docs.rs API URL, returns reviewable candidates, and requires confirmation before indexing one. If registry metadata has no authoritative docs URL, the response explains that `docs_url` must be supplied manually.

Forced/background library refreshes are staged before publication. When the fetched source set and content hashes match the active corpus, DocAtlas discards the candidate index and skips vector synchronization and embedding work with `reason_code="corpus_unchanged"`. Changed, removed, or canonicalized pages still produce a different corpus digest and follow the normal atomic publish path.

### Reproducible documentation manifests

Use `docmancer.docs.yaml` version 2 when automatic discovery is not precise enough or a large product site must be scoped deliberately. Automatic discovery remains a proposal mechanism; a confirmed manifest records structured package/product identity, version policy, source authority, version binding, network scope, coverage, page limits, and discovery strategy. `prepare_docs(action="inspect_docs_target", ...)` performs a bounded inspection without indexing and returns a reviewable v2 manifest proposal. After a successful `prefetch_docs_manifest`, DocAtlas writes `.docatlas/docs.lock.json` with the manifest digest and resolved target results. A changed manifest is reported as `manifest_outdated` until it is prefetched again.

The v2 validator rejects task-specific queries, false exact-version claims, remote sources without `allowed_domains`, unsupported formats/strategies, and page limits above 500. Keep the retrieval question in the runtime `get_docs_context`/prefetch call rather than persisting it in the manifest. See [`examples/docmancer.docs.universal.yaml`](./examples/docmancer.docs.universal.yaml) for bounded Docker Compose and exact Go module targets.

Go projects are detected from `go.mod` and `go.work`. A `go.mod` requirement is treated as a minimum requirement, not as proof of the selected build version. Exact automatic `pkg.go.dev` binding requires a matching vendored `vendor/modules.txt`; local or remote `replace` directives remain unbound until the source is explicitly confirmed.

Python and Java follow the same evidence rule. Python versions become resolved evidence only from `uv.lock`, `poetry.lock`, `pdm.lock`, or `Pipfile.lock`; a `requirements.txt`/`pyproject.toml` pin remains declared intent. Maven/Gradle inspection is static and never executes build scripts. A `pom.xml` or Gradle declaration is not treated as the selected version; `gradle.lockfile` provides exact evidence. Maven coordinates can produce bounded `javadoc.io` candidates, but that registry mirror still requires authority confirmation when the project does not declare its official documentation source.

Documentation evidence is reported separately for package identity, source authority, and version binding with a deterministic `accept`, `confirm`, or `reject` decision. DocAtlas intentionally does not collapse these dimensions into a confidence percentage: an exact version cannot compensate for an unverified source authority.

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

### Safe index cleanup

`doc-atlas clear-index` previews a bounded cleanup plan before removing derived
SQLite, extracted-document, cache, and verified local vector state. Use
`--scope project-local --project-path ...` for one project or `--scope global`
for all local indexes while preserving configuration. Applying a reviewed plan
can be bound to its `plan_digest`, and live processes, stale plans, remote
Qdrant, and unowned vector directories fail closed. See
[Cleaning DocAtlas index state safely](./docs/index-cleanup.md).

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

DocAtlas can inspect a local Flutter/Dart project. It reads `.fvmrc` for Flutter channel/version hints, `pubspec.lock` for registry package versions, and `.dart_tool/package_config.json` for existing local dependency source roots. Git, path, SDK, and custom-hosted packages are never presented as exact `pub.dev` bindings.

It also reads direct JavaScript/TypeScript dependencies from `package.json` and resolves their exact installed versions from `package-lock.json`, `pnpm-lock.yaml`, or `yarn.lock`. When several lockfiles exist, the `packageManager` declaration selects the authoritative one; local, workspace, and Git dependencies are never presented as exact registry bindings.

Python projects are supported through `pyproject.toml` or `requirements.txt`, with exact versions resolved from `uv.lock`, `poetry.lock`, or `pdm.lock`. Registry dependencies flow into version-aware documentation resolution; path, Git, and direct-URL dependencies remain unbound and require an explicit documentation source.

## License

MIT
