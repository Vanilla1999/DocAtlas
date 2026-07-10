"""Idempotent writers that register `doc-atlas mcp docs-serve` into agent MCP configs."""
from __future__ import annotations

import json
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SERVER_KEY = "docmancer"
COMMAND = "doc-atlas"
ARGS = ["mcp", "docs-serve"]


@dataclass
class AgentTarget:
    name: str
    config_path: Path
    style: str


def known_agents(*, project: bool = False) -> list[AgentTarget]:
    home = Path.home()
    targets = [
        AgentTarget("claude-code", home / ".claude" / "settings.json", "json_mcpServers"),
        AgentTarget(
            "cursor",
            Path(".cursor") / "mcp.json" if project else home / ".cursor" / "mcp.json",
            "json_mcpServers",
        ),
        AgentTarget(
            "claude-desktop",
            home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
            "json_mcpServers",
        ),
    ]
    targets.extend([
        AgentTarget(
            "codex",
            Path(".codex") / "config.toml" if project else home / ".codex" / "config.toml",
            "toml_mcp_servers",
        ),
        AgentTarget(
            "opencode",
            Path("opencode.json") if project else home / ".config" / "opencode" / "opencode.json",
            "json_opencode_mcp",
        ),
    ])
    if project:
        targets.append(AgentTarget("github-copilot", Path(".vscode") / "mcp.json", "json_vscode_servers"))
    return targets


def find_agent(name: str, *, project: bool = False) -> AgentTarget | None:
    if name in {"codex-app", "codex-desktop"}:
        name = "codex"
    for a in known_agents(project=project):
        if a.name == name:
            return a
    return None


def register_server(target: AgentTarget) -> tuple[bool, str]:
    """Idempotently add the docmancer MCP server entry. Returns (changed, message)."""
    if target.style == "toml_mcp_servers":
        return _register_toml_server(target)

    target.config_path.parent.mkdir(parents=True, exist_ok=True)
    config = _load_config(target.config_path)
    if target.style == "json_mcpServers":
        servers = config.setdefault("mcpServers", {})
        desired: dict[str, Any] = {"command": COMMAND, "args": list(ARGS)}
    elif target.style == "json_mcp_servers":
        servers = config.setdefault("mcp_servers", {})
        desired = {"command": COMMAND, "args": list(ARGS)}
    elif target.style == "json_opencode_mcp":
        servers = config.setdefault("mcp", {})
        desired = {"type": "local", "command": [COMMAND, *ARGS], "enabled": True}
    elif target.style == "json_vscode_servers":
        servers = config.setdefault("servers", {})
        desired = {"type": "stdio", "command": COMMAND, "args": list(ARGS)}
    else:
        raise ValueError(f"Unsupported agent config style: {target.style}")

    existing = servers.get(SERVER_KEY)
    if existing == desired or _matches_command(existing, desired):
        return False, f"already registered in {target.config_path}"
    servers[SERVER_KEY] = {**(existing or {}), **desired}
    _backup_and_write(target.config_path, config)
    return True, f"registered docmancer in {target.config_path}"


def unregister_server(target: AgentTarget) -> bool:
    if not target.config_path.exists():
        return False
    if target.style == "toml_mcp_servers":
        return False
    config = _load_config(target.config_path)
    key = {
        "json_mcpServers": "mcpServers",
        "json_mcp_servers": "mcp_servers",
        "json_opencode_mcp": "mcp",
        "json_vscode_servers": "servers",
    }.get(target.style)
    if key is None:
        return False
    if key in config and SERVER_KEY in config[key]:
        del config[key][SERVER_KEY]
        _backup_and_write(target.config_path, config)
        return True
    return False


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text().strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Existing config at {path} is not valid JSON: {exc}") from exc


def _matches_command(existing: Any, desired: dict[str, Any]) -> bool:
    if not isinstance(existing, dict):
        return False
    if desired.get("type") == "local":
        return existing.get("command") == desired["command"]
    return existing.get("command") == desired["command"] and list(existing.get("args", [])) == desired["args"]


def has_current_server_entry(config: dict[str, Any], target: AgentTarget) -> bool:
    key = {
        "json_mcpServers": "mcpServers",
        "json_mcp_servers": "mcp_servers",
        "json_opencode_mcp": "mcp",
        "json_vscode_servers": "servers",
    }.get(target.style)
    if key is None:
        return False
    servers = config.get(key)
    if not isinstance(servers, dict):
        return False
    desired = (
        {"type": "local", "command": [COMMAND, *ARGS], "enabled": True}
        if target.style == "json_opencode_mcp"
        else {"command": COMMAND, "args": list(ARGS)}
    )
    return _matches_command(servers.get(SERVER_KEY), desired)


def _register_toml_server(target: AgentTarget) -> tuple[bool, str]:
    target.config_path.parent.mkdir(parents=True, exist_ok=True)
    text = target.config_path.read_text(encoding="utf-8") if target.config_path.exists() else ""
    try:
        config = tomllib.loads(text) if text.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Existing config at {target.config_path} is not valid TOML: {exc}") from exc
    servers = config.get("mcp_servers") if isinstance(config, dict) else None
    existing = servers.get(SERVER_KEY) if isinstance(servers, dict) else None
    desired = {"command": COMMAND, "args": list(ARGS)}
    if _matches_command(existing, desired):
        return False, f"already registered in {target.config_path}"
    if existing is not None:
        raise ValueError(f"Existing MCP server {SERVER_KEY!r} in {target.config_path} has a different command; refusing to overwrite it.")
    if target.config_path.exists():
        shutil.copy2(target.config_path, target.config_path.with_suffix(target.config_path.suffix + ".bak"))
    separator = "" if not text or text.endswith("\n\n") else "\n"
    block = (
        f"[mcp_servers.{SERVER_KEY}]\n"
        f"command = {json.dumps(COMMAND)}\n"
        f"args = {json.dumps(ARGS)}\n"
    )
    target.config_path.write_text(text + separator + block, encoding="utf-8")
    return True, f"registered docmancer in {target.config_path}"


def _backup_and_write(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
