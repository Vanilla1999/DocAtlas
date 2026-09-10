# Contributing to DocAtlas

The product and CLI are named DocAtlas and `doc-atlas`; the Python import namespace remains `docmancer`.

Thank you for contributing! This guide covers project layout and common extension points.

## Project structure

New contributors should start by reading `README.md`, this `CONTRIBUTING.md`,
`docs/INDEX.md`, and `docs/PROJECT_MAP.md`. Together they provide the product
overview, repository map, canonical documentation index, and contribution flow.

```text
docmancer/
  agent.py              # DocmancerAgent compatibility facade and component wiring
  core/
    config.py           # DocmancerConfig (pydantic-settings)
    models.py           # Document, Chunk, RetrievedChunk
    chunking.py         # Text/markdown chunking
  connectors/           # Fetchers, document parsing, and optional retrieval backends
  docs/                 # Project/library documentation application and domain services
  mcp/                  # Docs MCP and advanced compatibility runtime
  cli/
    commands.py         # Click commands
    __main__.py         # CLI entry point
tests/                  # pytest tests (mirror docmancer/ where useful)
```

## Adding a new document parser

1. Implement a loader subclassing `BaseLoader` in `docmancer/connectors/parsers/`.
2. Register the file extension in `_PARSERS` in `docmancer/agent.py` (dotted import path to the class).

## Documentation MCP changes

Keep the public Docs MCP inventory to `get_docs_context`, `prepare_docs`, and `docs_status`. Repository files are the source of truth; DocAtlas may index accepted docs but must not silently author or commit them. Read [the canonical Docs MCP reference](./docs/mcp-docs-server.md) before changing this boundary.

`get_docs_context` separates three `kind` values (`docs_answer`, `docs_context`, `patch_context`) from `status` (`ok`, `truncated`, `insufficient_evidence`). Project reads remain retrieval-only `docs_context`; only supported library, dependency, or mixed evidence lanes may certify `docs_answer`, and explicit change tasks use `patch_context`.

## Adding a new doc source (fetcher)

1. Subclass `BaseFetcher` in `docmancer/connectors/fetchers/`.
2. Wire the new source into the CLI `fetch` / `ingest` paths in `docmancer/cli/commands.py` (and any agent helpers) following the GitBook pattern.

## Running tests

**On macOS (to avoid arm64/x86_64 Rosetta issues):**

```bash
arch -arm64 .venv/bin/python -m pytest tests/ -v
```

**On Linux / CI:**

```bash
pytest tests/ -v
```

## Submitting a PR

- Branch name: `feat/<topic>` or `fix/<description>`
- Run the full test suite before opening the PR
- New connectors or fetchers should include tests where practical
