# DocAtlas capability reference

The beginner workflow is documented in [README](../README.md) and the detailed MCP contract is in [Docs MCP server](./mcp-docs-server.md). This page is a compact reference for supported CLI and advanced surfaces.

## Core Docs workflow

| Need | Command or tool |
|---|---|
| Start Docs MCP | `doc-atlas mcp docs-serve` |
| Ask for project/dependency/library documentation | `get_docs_context` |
| Index accepted project docs | `prepare_docs(action="sync_project_docs")` |
| Check a returned job or index health | `docs_status` |
| Review docs affected by a code diff | `doc-atlas docs-impact --base origin/main` |
| Incrementally index accepted docs from an exact diff | `doc-atlas docs-impact --base origin/main --sync-saved-docs` |
| Generate a local agent contract | `doc-atlas agent-contract --project-path . --format markdown` |

Use `doc-atlas --help` and `doc-atlas <command> --help` for the installed command surface. The `mcp` group is visible from root help; use `doc-atlas mcp --help` for its subcommands.

## Local documentation commands

| Command | Purpose |
|---|---|
| `doc-atlas ingest <path>` | Index local files deliberately. |
| `doc-atlas query <question>` | CLI retrieval fallback for already indexed content. |
| `doc-atlas add <url>` | Explicitly acquire a public documentation source. |
| `doc-atlas list` | List local indexed/registered sources. |
| `doc-atlas inspect` | Inspect local configuration or indexed state. |
| `doc-atlas doctor` | Diagnose the local installation. |
| `doc-atlas remove <source>` | Remove a locally registered/indexed source. |

These commands are compatibility and diagnostic surfaces. Coding agents should use the three Docs MCP tools by default.

## Dependency/version evidence

DocAtlas reads supported project manifests and lockfiles to help bind documentation to a dependency version. It must not silently replace an unresolved or ambiguous project version with latest documentation.

Current exact external-source coverage is limited and under evaluation. If a safe source or version is unavailable, the result should request an explicit source or report unsupported coverage.

## Advanced surfaces

The following are intentionally outside the default Docs workflow:

| Surface | Entry point | Notes |
|---|---|---|
| MCP Packs | `doc-atlas mcp packs-serve` | Version-pinned API action packs; `doc-atlas mcp serve` is a compatibility alias. |
| Patch constraints | `DOCMANCER_MCP_ADVANCED_TOOLS=1` | Advisory evidence only; never a safe-to-merge proof. |
| Qdrant lifecycle | `doc-atlas qdrant --help` | Optional local vector administration. |
| USPTO and benchmark tooling | command-specific help | Maintenance/research surfaces. |

## Installation names

Install the PyPI package as `doc-atlas` and use `doc-atlas` in user-facing commands. The internal Python package and some compatibility storage paths still use `docmancer`.

```bash
pipx install doc-atlas
doc-atlas --help
```

## Documentation policy

This file is intentionally short. Detailed tool workflows belong in `docs/mcp-docs-server.md`; do not duplicate its public-tool tables here. See [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) for the documentation size and release verification rules.
