# MCP Packs

MCP packs are version-pinned tool bundles compiled from public API documentation sources such as OpenAPI, GraphQL introspection, TypeDoc, and Sphinx. Installed packs are exposed to agents through one local stdio server, `docmancer mcp serve`, using two meta-tools:

- `docmancer_search_tools(query, package?, limit?)` searches across enabled packs and returns the best matching tool with its input schema.
- `docmancer_call_tool(name, args)` invokes a specific fully qualified tool name returned by search.

Agents launch `docmancer mcp serve` automatically from their MCP config; humans use the management commands below to install, enable/disable, and inspect packs.

## Install a Pack

```bash
docmancer install-pack open-meteo@v1
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
docmancer mcp doctor
docmancer mcp list
docmancer mcp disable open-meteo --version v1
docmancer mcp enable open-meteo --version v1
docmancer uninstall open-meteo@v1
```

| Command | Description |
|---------|-------------|
| `docmancer mcp serve` | Run the stdio MCP server. Agents launch this. |
| `docmancer mcp doctor` | Verify pack artifacts, credential resolution, and agent config registrations. |
| `docmancer mcp list` | Show installed packs, curated or expanded mode, tool counts, and destructive gate state. |
| `docmancer mcp enable <pkg> [--version <v>]` | Re-enable a disabled pack without reinstalling it. |
| `docmancer mcp disable <pkg> [--version <v>]` | Hide a pack from the dispatcher without removing it on disk. |
| `docmancer mcp remove <pkg>[@<version>]` | Remove an installed pack from the MCP manifest and disk cache. |
| `docmancer uninstall <pkg>[@<version>]` | Alias for removing an installed pack. |

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
docmancer install-pack open-meteo@v1
docmancer mcp doctor
docmancer mcp list
```

After installation, agents can search for the forecast tool with `docmancer_search_tools` and call it with `docmancer_call_tool`.
