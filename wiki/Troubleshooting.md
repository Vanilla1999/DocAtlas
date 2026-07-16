# Troubleshooting

Common issues when installing or running DocAtlas. See also [Configuration](./Configuration.md), [Install Targets](./Install-Targets.md), and the [Docs MCP reference](../docs/mcp-docs-server.md).

## `pipx install doc-atlas` succeeds, but `doc-atlas` is `command not found`

This usually means the scripts directory is not on your `PATH`. The install output will show the path:

```text
WARNING: The script doc-atlas is installed in '/Users/your-user/.local/bin' which is not on PATH.
```

Recommended fix:

```bash
brew install pipx
pipx ensurepath
pipx install doc-atlas --python python3.13
```

Or confirm the install by running the script directly:

```bash
~/Library/Python/3.13/bin/doc-atlas doctor
```

## `pipx install doc-atlas` says `No matching distribution found`

This means `pipx` picked an unsupported Python version. DocAtlas requires Python 3.11-3.13.

```bash
pipx install doc-atlas --python python3.13
```

If Python 3.13 is not installed:

```bash
brew install python@3.13
pipx install doc-atlas --python python3.13
```

## `pipx install` fails: Apple Silicon / architecture mismatch

On macOS, `pipx` and Python can end up on different architectures (`arm64` vs `x86_64`). Use the native Homebrew Python explicitly:

```bash
pipx install doc-atlas --python /opt/homebrew/bin/python3.13
```

If needed:

```bash
arch -arm64 pipx install doc-atlas --python /opt/homebrew/bin/python3.13
```

## `doc-atlas doctor` crashes with `pydantic_core` or architecture error

The virtualenv was created with the wrong architecture. Recreate it:

```bash
deactivate
rm -rf .venv
arch -arm64 /opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## SQLite FTS5 is not available

docmancer requires SQLite with FTS5 support. Most Python distributions include it by default. If you see a `RuntimeError` about FTS5, install a Python build that includes it:

```bash
brew install python@3.13
pipx install doc-atlas --python /opt/homebrew/bin/python3.13
```

## `doc-atlas add` hangs or returns empty content for a JS-heavy site

Some documentation sites rely on client-side JavaScript to render content. If `doc-atlas add <url>` produces empty or incomplete results, use the `--browser` flag to enable Playwright browser fallback:

```bash
doc-atlas add <url> --browser
```

This requires the `browser` optional dependency: `pip install 'doc-atlas[browser]'`.

## Agent does not use the Docs MCP workflow

Confirm that the agent is registered with `doc-atlas mcp docs-serve`. The first tool for documentation questions is `get_docs_context`; follow a returned `prepare_docs` action and use `docs_status` only for returned jobs or explicit health/freshness requests. See [Docs MCP server](../docs/mcp-docs-server.md).

## MCP packs

### `doc-atlas install-pack` says `Spec must be \`<package>@<version>\``

Pack specs must include both name and version. The parser splits from the rightmost `@` so npm-scoped names like `@scope/pkg@1.2.3` work; if the spec has no `@`, supply one explicitly:

```bash
doc-atlas install-pack open-meteo@v1
doc-atlas install-pack @acme/widgets@1.4.2
```

### `Pack <pkg>@<version> is not available locally, from the hosted registry, or from a known OpenAPI fallback`

The resolver tried local cache, the hosted compatibility Docmancer artifact API, and the built-in known-source fallback, and none of them had the pack. From an interactive shell, `install-pack` then prompts you for an OpenAPI 3.x or Swagger 2.0 spec URL. Paste the URL of any public spec for the API and DocAtlas will compile a pack locally.

For non-interactive use (CI, scripts), pass the URL up front:

```bash
doc-atlas install-pack bun@v1 --from-url https://example.com/openapi.yaml
```

If the URL does not look like an OpenAPI 3.x or Swagger 2.0 document (no top-level `openapi: 3.x` / `swagger: 2.0`, or no `paths` map), the install fails with `<url> does not look like an OpenAPI 3.x or Swagger 2.0 document`.

### Tool returns `destructive_call_blocked`

The pack was installed without `--allow-destructive`, and the agent tried to call a POST/PUT/PATCH/DELETE operation. The error message names the exact remediation command. Reinstall with the flag, then restart your agent:

```bash
doc-atlas install-pack <package>@<version> --allow-destructive
```

`doc-atlas mcp list` will show `destructive=ALLOW` once the gate is open. Read-only packs (e.g. `open-meteo@v1`) never trip this gate because their contracts declare no destructive operations.

### Tool returns `missing_credentials`

The dispatcher tried every configured credential source and none resolved. For shell-launched agents, export the env var and restart the agent. For GUI-launched agents (Cursor, Claude Desktop), add the env var to the `env: {}` block in the agent's `mcp.json`. `doc-atlas mcp doctor` reports which source resolved each credential.

### `doc-atlas mcp doctor` reports SHA-256 mismatch

The pack on disk does not match the SHA-256 in `manifest.json`. Either the registry was tampered with, the file was edited locally, or an install failed mid-write. Reinstall the pack:

```bash
doc-atlas uninstall open-meteo@v1
doc-atlas install-pack open-meteo@v1
```

### Path with `/` or `?` returns the wrong resource

The HTTP executor percent-encodes path parameters as one segment, so values like branch names (`feat/x`) or S3 keys with slashes are sent as `feat%2Fx`. If your API expects multiple path segments from one parameter, the contract should declare separate parameters; otherwise the encoded value is correct.

### `doc-atlas install-pack` rejects the spec with `path traversal`

Pack and version components cannot contain `..`, NUL, backslashes, absolute paths, or (for the version component) a leading `@`. This protects the storage root from escape via crafted registry metadata. The npm scope form (`@scope/pkg`) is allowed in the package name, but the version cannot start with `@`.

## Hybrid retrieval and Qdrant

### macOS asks "qdrant is attempting to connect to ec2-...amazonaws.com"

That is Qdrant's own anonymous telemetry, not docmancer. The managed lifecycle spawns Qdrant with `QDRANT__TELEMETRY_DISABLED=true`, so the prompt should not appear from new spawns. If you see it from an older manually started binary, deny the prompt (Qdrant runs fine offline) and restart with `doc-atlas qdrant down && doc-atlas qdrant up`.

### `doc-atlas ingest` does not embed anything

The default ingest path embeds + upserts vectors via the managed local Qdrant. If you see FTS5-only behaviour, check:

- `DOCMANCER_AUTO_VECTORS=0` is set in env (or `--no-vectors` was passed). Unset the env var to re-enable.
- The configured embeddings provider is a cloud one (`openai`, `voyage`, `cohere`) but its API key env var is missing. DocAtlas falls back to FTS5-only and logs the missing key; set the env var or switch to `embeddings.provider: fastembed`.
- The Qdrant binary is unavailable for your platform. Run `doc-atlas doctor` to see the platform matrix decision. `SqliteVecStore` is used as a fallback when possible.

### `PermissionError: qdrant collection 'X' already exists on http://... but does not carry the docmancer ownership sentinel`

You pointed `vector_store.collection` at a collection that docmancer did not create. We refuse to write into a collection that lacks our sentinel, so a future `delete_collection` cannot wipe a shared dataset. Either drop the existing collection through the Qdrant client, point `vector_store.collection` at a different name, or rename your collection.

### `doc-atlas query --mode hybrid` says "lexical-fallback" or returns no contributions

The dispatcher fell back to lexical because either the vector store could not be reached, the embeddings provider failed to load, or no Qdrant collection exists yet. Run `doc-atlas doctor` to see Qdrant + embeddings status, and `doc-atlas ingest --recreate` once to populate the collection.

### `Section count drifts from vector count after `ingest --recreate``

This should not happen: `sync_vector_store` prunes orphaned vector points and `embedding_upserts` rows for chunk ids that have vanished from SQLite. If `doc-atlas doctor` reports drift, run `doc-atlas ingest --recreate` once more to re-reconcile, then file an issue with the drift numbers.

### macOS Apple Silicon: managed Qdrant won't start

Confirm with `file ~/.docmancer/qdrant/qdrant` that the binary is `arm64` if you are on Apple Silicon. The `qdrant_manager` selects the right artefact from the verified matrix, but a mixed-arch venv can pick the wrong path. Reinstall the binary with `doc-atlas qdrant upgrade`.
