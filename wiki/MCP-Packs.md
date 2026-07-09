# MCP Packs

MCP Packs are Docmancer's advanced product layer. If your goal is source-grounded answers from documentation, start with Docmancer Docs: `doc-atlas ingest`, `doc-atlas add`, `doc-atlas query`, or `doc-atlas mcp docs-serve`. Use Packs when an agent needs version-pinned API action tools.

MCP packs are version-pinned tool bundles compiled from public API documentation sources such as OpenAPI, GraphQL introspection, TypeDoc, and Sphinx. Installed packs are exposed to agents through one local stdio server, `doc-atlas mcp serve`, using two meta-tools:

- `docmancer_search_tools(query, package?, limit?)` searches across enabled packs and returns the best matching tool with its input schema.
- `docmancer_call_tool(name, args)` invokes a specific fully qualified tool name returned by search.

Agents launch `doc-atlas mcp serve` automatically from their MCP config; humans use the management commands below to install, enable/disable, and inspect packs.

## Install a Pack

```bash
doc-atlas install-pack open-meteo@v1
```

`install-pack` resolves artifacts in this order:

1. Local cache.
2. The hosted Docmancer artifact API.
3. Built-in known-source fallback. Open-Meteo packs can be compiled locally from the public OpenAPI spec when precompiled artifacts are not available.

Package specs parse from the rightmost `@`, so scoped names like `@scope/pkg@1.2.3` work.

## install-pack Options

| Option | Description |
|--------|-------------|
| `--expanded` | Use the full tool surface from `tools.full.json` instead of the curated subset. |
| `--allow-destructive` | Permit destructive calls such as POST, PUT, PATCH, or DELETE. Off by default. |
| `--allow-execute` | Permit executor types like `python_import` that run code in a subprocess. Off by default. |
| `--from-url <url>` | Compile a pack locally from a public OpenAPI 3.x or Swagger 2.0 spec URL. |

## Manage Packs

```bash
doc-atlas mcp doctor
doc-atlas mcp list
doc-atlas mcp disable open-meteo --version v1
doc-atlas mcp enable open-meteo --version v1
doc-atlas uninstall open-meteo@v1
```

| Command | Description |
|---------|-------------|
| `doc-atlas mcp serve` | Run the advanced stdio MCP Packs/API-pack gateway. The default documentation workflow uses `doc-atlas mcp docs-serve`. |
| `doc-atlas mcp doctor` | Verify pack artifacts, credential resolution, and agent config registrations. |
| `doc-atlas mcp list` | Show installed packs, curated or expanded mode, tool counts, and destructive gate state. |
| `doc-atlas mcp enable <pkg> [--version <v>]` | Re-enable a disabled pack without reinstalling it. |
| `doc-atlas mcp disable <pkg> [--version <v>]` | Hide a pack from the dispatcher without removing it on disk. |
| `doc-atlas mcp remove <pkg>[@<version>]` | Remove an installed pack from the MCP manifest and disk cache. |
| `doc-atlas uninstall <pkg>[@<version>]` | Alias for removing an installed pack. |

## Runtime Behavior

When an agent calls `docmancer_call_tool`, the dispatcher resolves the slug `package__version__operation`, validates `args` against the operation input schema, resolves credentials, applies safety checks, injects idempotency keys when configured, and dispatches via the operation executor.

Credential resolution checks these sources:

1. Per-call credential override.
2. Process environment variable.
3. Agent MCP config `env` block.
4. User-managed env file under `~/.docmancer/secrets/<package>.env`.

Destructive operations are blocked unless the pack was installed with `--allow-destructive`. Executor types that can run local code are blocked unless the pack was installed with `--allow-execute`.

For non-idempotent operations that declare an idempotency header, docmancer injects a UUID4 idempotency key and reuses it on retry from a 24-hour SQLite fingerprint cache. Successful responses can include `_docmancer.idempotency_key`; retry with `args._docmancer_idempotency_key` to deduplicate.

Call logs are written to `~/.docmancer/mcp/calls.jsonl`. Logs record argument keys only, not argument values.

## Source-Kind Support

| Source | Compiled by pipeline | Runtime executor |
|--------|----------------------|------------------|
| OpenAPI 3.0 / 3.1 | Yes | `http` for live wire calls |
| GraphQL introspection | Yes | `noop_doc`, documentation only for now |
| TypeDoc / Sphinx | Yes | `noop_doc`, documentation only for now |

## Open-Meteo Smoke Test

Open-Meteo is a public read-only weather API that needs no API key, so it is the cleanest pack smoke test:

```bash
doc-atlas install-pack open-meteo@v1
doc-atlas mcp doctor
doc-atlas mcp list
```

After installation, agents can search for the forecast tool with `docmancer_search_tools` and call it with `docmancer_call_tool`.
