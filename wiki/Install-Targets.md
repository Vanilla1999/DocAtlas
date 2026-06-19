# Install Targets

`doc-atlas setup` auto-detects installed coding agents and installs skill files in one pass. For manual per-agent installation, use `doc-atlas install <agent>`. See [Commands](./Commands.md) for the full option reference and [Architecture](./Architecture.md) for how agents fit into the system.

## Skill locations

| Command | Where the skill lands |
|---------|-----------------------|
| `doc-atlas install claude-code` | `~/.claude/skills/docmancer/SKILL.md` |
| `doc-atlas install cline` | `~/.cline/skills/docmancer/SKILL.md` |
| `doc-atlas install codex` | `~/.codex/skills/docmancer/SKILL.md` (also mirrors to `~/.agents/skills/docmancer/SKILL.md`) |
| `doc-atlas install codex-app` | `~/.codex/skills/docmancer/SKILL.md` (Codex app variant) |
| `doc-atlas install codex-desktop` | `~/.codex/skills/docmancer/SKILL.md` (Codex desktop variant) |
| `doc-atlas install cursor` | `~/.cursor/skills/docmancer/SKILL.md` + marked block in `~/.cursor/AGENTS.md` when needed |
| `doc-atlas install opencode` | `~/.config/opencode/skills/docmancer/SKILL.md` |
| `doc-atlas install gemini` | `~/.gemini/skills/docmancer/SKILL.md` |
| `doc-atlas install claude-desktop` | `~/.docmancer/exports/claude-desktop/docmancer.zip`: upload via **Customize > Skills** |
| `doc-atlas install github-copilot` | `~/.copilot/copilot-instructions.md` (user) or `.github/copilot-instructions.md` (with `--project`) |

## Project-local installs

Use `--project` with `claude-code`, `gemini`, `cline`, or `github-copilot` to install under the current working directory (`.claude/skills/...`, `.gemini/skills/...`, `.cline/skills/...`, or `.github/copilot-instructions.md`). This is useful when different projects need different docmancer configurations.

## Advanced MCP Server Registration

In addition to writing the skill file, `doc-atlas install <agent>` (and `doc-atlas setup`) can register the local MCP server into the agent's MCP config so installed API packs are available. This is only needed for the advanced API-pack surface; local docs retrieval uses the CLI commands taught by the skill file. The entry is written idempotently, so reruns do not duplicate it.

| Agent | MCP config file written |
|-------|--------------------------|
| `claude-code` | `~/.claude/mcp_servers.json` (or `~/.claude/settings.json`) |
| `cursor` | `~/.cursor/mcp.json` |
| `claude-desktop` | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) |

The entry has the shape:

```json
{
  "mcpServers": {
    "docmancer": {
      "command": "docmancer",
      "args": ["mcp", "serve"],
      "env": {}
    }
  }
}
```

Add per-pack credentials (e.g. `<PACKAGE>_API_KEY`) to the `env: {}` block when launching from a GUI-launched agent (Cursor, Claude Desktop) that does not inherit the shell environment. Shell-launched agents (Claude Code, Codex CLI) read process env directly. Keyless packs like `open-meteo` skip the `env` block entirely. See [Configuration > MCP runtime](./Configuration.md#mcp-runtime) for the full credential resolution order.

## What the skill teaches agents

Installed skills cover the core workflow:

- `doc-atlas ingest` to index local documentation sources
- `doc-atlas add` to index URL documentation sources
- `doc-atlas update` to refresh existing sources
- `doc-atlas query` to get compact context packs with token savings
- `doc-atlas list`, `doc-atlas inspect`, `doc-atlas remove`, `doc-atlas doctor` for index management
- Advanced only: `doc-atlas install-pack <pkg>@<version>` installs API MCP packs, and the registered `doc-atlas mcp serve` exposes them through the Tool Search pattern (`docmancer_search_tools`, `docmancer_call_tool`)
- Advanced only: `doc-atlas mcp doctor` and `doc-atlas mcp list` verify pack state and credentials

Agents learn to call `doc-atlas query` for grounded answers instead of relying on stale training data. If API packs are installed, agents can also call MCP packs through the resolved tool name (for example `open_meteo__v1__forecast`) for live API work without losing track of the pinned version.

## Shared index

All installed agent skills call the same docmancer CLI. If multiple agents on the same machine use the same SQLite database, they see the same indexed content. Ingest from Claude Code, query from Cursor, update from Gemini. The cross-agent property is a natural consequence of the shared local database.

## Troubleshooting

If `docmancer` is not found after installation, see [Troubleshooting](./Troubleshooting.md) for PATH and architecture fixes.
