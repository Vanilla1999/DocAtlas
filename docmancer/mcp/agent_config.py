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
        AgentTarget(
            "claude-code",
            Path(".mcp.json") if project else home / ".claude" / "settings.json",
            "json_mcpServers",
        ),
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
        AgentTarget("cline", Path(".cline") / "mcp.json" if project else home / ".cline" / "mcp.json", "json_mcpServers"),
        AgentTarget("gemini", Path(".gemini") / "mcp.json" if project else home / ".gemini" / "mcp.json", "json_mcpServers"),
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
    if existing is not None and not (
        _is_legacy_docmancer_entry(existing, target.style)
        or _has_same_command(existing, desired)
    ):
        raise ValueError(
            f"Existing MCP server {SERVER_KEY!r} in {target.config_path} has a different command; refusing to overwrite it."
        )
    servers[SERVER_KEY] = {**(existing or {}), **desired}
    _backup_and_write(target.config_path, config)
    return True, f"registered docmancer in {target.config_path}"


def unregister_server(target: AgentTarget) -> bool:
    if not target.config_path.exists():
        return False
    if target.style == "toml_mcp_servers":
        text = target.config_path.read_text(encoding="utf-8")
        config = tomllib.loads(text) if text.strip() else {}
        existing = config.get("mcp_servers", {}).get(SERVER_KEY)
        if existing != {"command": COMMAND, "args": list(ARGS)}:
            return False
        lines = text.splitlines(keepends=True)
        header = f"[mcp_servers.{SERVER_KEY}]"
        nested_header_prefix = f"[mcp_servers.{SERVER_KEY}."
        start = next((i for i, line in enumerate(lines) if line.strip() == header), None)
        if start is None:
            return False
        end = start + 1
        while end < len(lines):
            candidate = lines[end].lstrip()
            if candidate.startswith("[") and not candidate.startswith(nested_header_prefix):
                break
            end += 1
        shutil.copy2(target.config_path, target.config_path.with_suffix(target.config_path.suffix + ".bak"))
        target.config_path.write_text("".join(lines[:start] + lines[end:]), encoding="utf-8")
        return True
    config = _load_config(target.config_path)
    key = {
        "json_mcpServers": "mcpServers",
        "json_mcp_servers": "mcp_servers",
        "json_opencode_mcp": "mcp",
        "json_vscode_servers": "servers",
    }.get(target.style)
    if key is None:
        return False
    desired = _desired_server_entry(target.style)
    if key in config and config[key].get(SERVER_KEY) == desired:
        del config[key][SERVER_KEY]
        _backup_and_write(target.config_path, config)
        return True
    return False


def _desired_server_entry(style: str) -> dict[str, Any]:
    if style == "json_opencode_mcp":
        return {"type": "local", "command": [COMMAND, *ARGS], "enabled": True}
    return {"command": COMMAND, "args": list(ARGS)}


def _is_legacy_docmancer_entry(existing: Any, style: str) -> bool:
    """Allow migration only from the previously shipped Docmancer command."""
    if not isinstance(existing, dict):
        return False
    if style == "json_opencode_mcp":
        return existing.get("command") == ["docmancer", "mcp", "serve"]
    return existing.get("command") == "docmancer" and list(existing.get("args", [])) == ["mcp", "serve"]


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
    return all(existing.get(key) == value for key, value in desired.items())


def _has_same_command(existing: Any, desired: dict[str, Any]) -> bool:
    if not isinstance(existing, dict):
        return False
    if existing.get("command") != desired.get("command"):
        return False
    if "args" in desired:
        return list(existing.get("args", [])) == desired["args"]
    return True


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


def target_has_current_server_entry(target: AgentTarget) -> bool:
    """Return whether a target's on-disk config contains the active Docs MCP entry."""
    if not target.config_path.exists():
        return False
    if target.style == "toml_mcp_servers":
        text = target.config_path.read_text(encoding="utf-8")
        config = tomllib.loads(text) if text.strip() else {}
        existing = config.get("mcp_servers", {}).get(SERVER_KEY)
        return _matches_command(existing, _desired_server_entry(target.style))
    return has_current_server_entry(_load_config(target.config_path), target)


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
