"""Idempotent writers that register `doc-atlas mcp docs-serve` into agent MCP configs."""
from __future__ import annotations

import json
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SERVER_KEY = "docatlas"
LEGACY_SERVER_KEY = "docmancer"
COMMAND = "doc-atlas"
ARGS = ["mcp", "docs-serve"]
OPENCODE_MCP_ENVIRONMENT = {"DOCATLAS_MCP_TEXT_FALLBACK": "1"}


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
        AgentTarget(
            "cline",
            Path(".cline") / "mcp.json" if project else home / ".cline" / "mcp.json",
            "json_mcpServers",
        ),
        AgentTarget(
            "gemini",
            Path(".gemini") / "mcp.json" if project else home / ".gemini" / "mcp.json",
            "json_mcpServers",
        ),
    ])
    if project:
        targets.append(
            AgentTarget(
                "github-copilot",
                Path(".vscode") / "mcp.json",
                "json_vscode_servers",
            )
        )
    return targets


def find_agent(name: str, *, project: bool = False) -> AgentTarget | None:
    if name in {"codex-app", "codex-desktop"}:
        name = "codex"
    for agent in known_agents(project=project):
        if agent.name == name:
            return agent
    return None


def register_server(target: AgentTarget) -> tuple[bool, str]:
    """Idempotently add the primary DocAtlas MCP entry.

    The old ``docmancer`` key is deliberately treated as a separate namespace.
    It is migrated only when its command already proves that DocAtlas created it
    (``doc-atlas mcp docs-serve``). An ambiguous or foreign ``docmancer`` entry
    is left untouched so upstream Docmancer can coexist with DocAtlas.
    """

    if target.style == "toml_mcp_servers":
        return _register_toml_server(target)

    target.config_path.parent.mkdir(parents=True, exist_ok=True)
    config = _load_config(target.config_path)
    servers = _json_server_mapping(config, target.style, create=True)
    desired = _desired_server_entry(target.style)

    existing = servers.get(SERVER_KEY)
    if _matches_command(existing, desired):
        return False, f"already registered in {target.config_path}"
    if existing is not None and not _has_same_command(existing, desired):
        raise ValueError(
            f"Existing MCP server {SERVER_KEY!r} in {target.config_path} has a different command; "
            "refusing to overwrite it."
        )

    migrated = False
    source = existing
    legacy = servers.get(LEGACY_SERVER_KEY)
    if source is None and _is_proven_docatlas_entry(legacy, target.style):
        source = legacy
        del servers[LEGACY_SERVER_KEY]
        migrated = True

    merged = {**(source or {}), **desired}
    if target.style == "json_opencode_mcp":
        environment = {} if source is None or "environment" not in source else source["environment"]
        if not isinstance(environment, dict):
            raise ValueError(
                f"Existing DocAtlas MCP server in {target.config_path} has a non-object environment; "
                "refusing to overwrite it."
            )
        merged["environment"] = {**environment, **OPENCODE_MCP_ENVIRONMENT}
    servers[SERVER_KEY] = merged
    _backup_and_write(target.config_path, config)
    action = "migrated DocAtlas MCP registration to" if migrated else "registered docatlas in"
    return True, f"{action} {target.config_path}"


def unregister_server(target: AgentTarget) -> bool:
    """Remove only an entry that is provably owned by the current DocAtlas CLI."""

    if not target.config_path.exists():
        return False
    if target.style == "toml_mcp_servers":
        return _unregister_toml_server(target)

    config = _load_config(target.config_path)
    servers = _json_server_mapping(config, target.style, create=False)
    if servers is None:
        return False
    desired = _desired_server_entry(target.style)

    for key in (SERVER_KEY, LEGACY_SERVER_KEY):
        existing = servers.get(key)
        # Exact equality is intentional: user-added fields make ownership of the
        # complete entry ambiguous, so uninstall preserves it.
        if existing == desired:
            del servers[key]
            _backup_and_write(target.config_path, config)
            return True
    return False


def _desired_server_entry(style: str) -> dict[str, Any]:
    if style == "json_opencode_mcp":
        return {
            "type": "local",
            "command": [COMMAND, *ARGS],
            "enabled": True,
            "environment": dict(OPENCODE_MCP_ENVIRONMENT),
        }
    if style == "json_vscode_servers":
        return {"type": "stdio", "command": COMMAND, "args": list(ARGS)}
    return {"command": COMMAND, "args": list(ARGS)}


def _json_server_mapping(
    config: dict[str, Any],
    style: str,
    *,
    create: bool,
) -> dict[str, Any] | None:
    key = {
        "json_mcpServers": "mcpServers",
        "json_mcp_servers": "mcp_servers",
        "json_opencode_mcp": "mcp",
        "json_vscode_servers": "servers",
    }.get(style)
    if key is None:
        raise ValueError(f"Unsupported agent config style: {style}")
    if create:
        servers = config.setdefault(key, {})
    else:
        servers = config.get(key)
        if servers is None:
            return None
    if not isinstance(servers, dict):
        raise ValueError(f"Existing {key!r} in agent config must be an object")
    return servers


def _is_proven_docatlas_entry(existing: Any, style: str) -> bool:
    """Return True only when the command itself proves DocAtlas ownership.

    ``docmancer mcp serve`` is intentionally *not* accepted: that spelling is
    shared with the upstream Docmancer product and therefore cannot prove who
    owns the legacy key.
    """

    if not isinstance(existing, dict):
        return False
    if style == "json_opencode_mcp":
        return existing.get("command") == [COMMAND, *ARGS]
    return existing.get("command") == COMMAND and list(existing.get("args", [])) == ARGS


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Existing config at {path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Existing config at {path} must contain a JSON object")
    return payload


def _matches_command(existing: Any, desired: dict[str, Any]) -> bool:
    if not isinstance(existing, dict):
        return False
    for key, value in desired.items():
        if key == "environment":
            if not isinstance(existing.get(key), dict) or any(
                existing[key].get(environment_key) != environment_value
                for environment_key, environment_value in value.items()
            ):
                return False
        elif existing.get(key) != value:
            return False
    return True


def _has_same_command(existing: Any, desired: dict[str, Any]) -> bool:
    if not isinstance(existing, dict):
        return False
    if existing.get("command") != desired.get("command"):
        return False
    if "args" in desired:
        return list(existing.get("args", [])) == desired["args"]
    return True


def has_current_server_entry(config: dict[str, Any], target: AgentTarget) -> bool:
    """Accept the primary key and the bounded legacy-key compatibility form."""

    servers = _json_server_mapping(config, target.style, create=False)
    if servers is None:
        return False
    desired = _desired_server_entry(target.style)
    if _matches_command(servers.get(SERVER_KEY), desired):
        return True
    return _is_proven_docatlas_entry(servers.get(LEGACY_SERVER_KEY), target.style)


def target_has_current_server_entry(target: AgentTarget) -> bool:
    """Return whether a target's on-disk config contains a working DocAtlas Docs MCP entry."""

    if not target.config_path.exists():
        return False
    if target.style == "toml_mcp_servers":
        text = target.config_path.read_text(encoding="utf-8")
        config = tomllib.loads(text) if text.strip() else {}
        servers = config.get("mcp_servers", {}) if isinstance(config, dict) else {}
        if not isinstance(servers, dict):
            return False
        desired = _desired_server_entry(target.style)
        if _matches_command(servers.get(SERVER_KEY), desired):
            return True
        return _is_proven_docatlas_entry(servers.get(LEGACY_SERVER_KEY), target.style)
    return has_current_server_entry(_load_config(target.config_path), target)


def _register_toml_server(target: AgentTarget) -> tuple[bool, str]:
    target.config_path.parent.mkdir(parents=True, exist_ok=True)
    text = target.config_path.read_text(encoding="utf-8") if target.config_path.exists() else ""
    try:
        config = tomllib.loads(text) if text.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Existing config at {target.config_path} is not valid TOML: {exc}") from exc

    servers = config.get("mcp_servers") if isinstance(config, dict) else None
    if servers is not None and not isinstance(servers, dict):
        raise ValueError(f"Existing mcp_servers in {target.config_path} must be a table")
    servers = servers or {}
    desired = _desired_server_entry(target.style)
    existing = servers.get(SERVER_KEY)
    if _matches_command(existing, desired):
        return False, f"already registered in {target.config_path}"
    if existing is not None:
        raise ValueError(
            f"Existing MCP server {SERVER_KEY!r} in {target.config_path} has a different command; "
            "refusing to overwrite it."
        )

    legacy = servers.get(LEGACY_SERVER_KEY)
    if _is_proven_docatlas_entry(legacy, target.style):
        if target.config_path.exists():
            shutil.copy2(target.config_path, target.config_path.with_suffix(target.config_path.suffix + ".bak"))
        migrated = _rename_toml_server_headers(text, LEGACY_SERVER_KEY, SERVER_KEY)
        target.config_path.write_text(migrated, encoding="utf-8")
        return True, f"migrated DocAtlas MCP registration to {target.config_path}"

    if target.config_path.exists():
        shutil.copy2(target.config_path, target.config_path.with_suffix(target.config_path.suffix + ".bak"))
    separator = "" if not text or text.endswith("\n\n") else "\n"
    block = (
        f"[mcp_servers.{SERVER_KEY}]\n"
        f"command = {json.dumps(COMMAND)}\n"
        f"args = {json.dumps(ARGS)}\n"
    )
    target.config_path.write_text(text + separator + block, encoding="utf-8")
    return True, f"registered docatlas in {target.config_path}"


def _unregister_toml_server(target: AgentTarget) -> bool:
    text = target.config_path.read_text(encoding="utf-8")
    try:
        config = tomllib.loads(text) if text.strip() else {}
    except tomllib.TOMLDecodeError:
        return False
    servers = config.get("mcp_servers", {}) if isinstance(config, dict) else {}
    if not isinstance(servers, dict):
        return False
    desired = _desired_server_entry(target.style)

    for key in (SERVER_KEY, LEGACY_SERVER_KEY):
        if servers.get(key) != desired:
            continue
        updated = _remove_toml_server_block(text, key)
        if updated == text:
            return False
        shutil.copy2(target.config_path, target.config_path.with_suffix(target.config_path.suffix + ".bak"))
        target.config_path.write_text(updated, encoding="utf-8")
        return True
    return False


def _rename_toml_server_headers(text: str, old: str, new: str) -> str:
    header = f"[mcp_servers.{old}]"
    nested_prefix = f"[mcp_servers.{old}."
    rewritten: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == header:
            rewritten.append(line.replace(header, f"[mcp_servers.{new}]", 1))
        elif stripped.startswith(nested_prefix) and stripped.endswith("]"):
            rewritten.append(line.replace(nested_prefix, f"[mcp_servers.{new}.", 1))
        else:
            rewritten.append(line)
    return "".join(rewritten)


def _remove_toml_server_block(text: str, key: str) -> str:
    lines = text.splitlines(keepends=True)
    header = f"[mcp_servers.{key}]"
    nested_header_prefix = f"[mcp_servers.{key}."
    start = next((i for i, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        return text
    end = start + 1
    while end < len(lines):
        candidate = lines[end].lstrip()
        if candidate.startswith("[") and not candidate.startswith(nested_header_prefix):
            break
        end += 1
    return "".join(lines[:start] + lines[end:])


def _backup_and_write(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
