from __future__ import annotations

import re
from pathlib import Path

import tomllib
from click.testing import CliRunner

from docmancer.cli.__main__ import cli
from docmancer.mcp.dispatcher import CALL_TOOL, SEARCH_TOOL
from docmancer.mcp.docs_server import (
    MCP_RESOURCES,
    MCP_RESOURCE_TEMPLATES,
    DocsServerConfig,
    build_docs_surface,
)
from docmancer.support_policy import (
    SHIPPED_SERVICE_SURFACE_IDS,
    load_support_policy,
    validate_support_policy,
)


ROOT = Path(__file__).resolve().parents[1]


def _ids(policy: dict, kind: str) -> set[str]:
    return {item["id"] for item in policy["surfaces"] if item["kind"] == kind}


def _click_surface_ids(group, prefix: str = "cli") -> set[str]:
    result: set[str] = set()
    for name, command in group.commands.items():
        surface_id = f"{prefix}:{name}" if prefix == "cli" else f"{prefix}/{name}"
        result.add(surface_id)
        if hasattr(command, "commands"):
            result.update(_click_surface_ids(command, surface_id))
    return result














def test_retired_compatibility_surfaces_are_not_in_the_inventory() -> None:
    policy = load_support_policy()
    tiers = {item["id"]: item["tier"] for item in policy["surfaces"]}

    assert tiers["cli:add"] == "core"
    assert "cli-compat:add-local-path" not in tiers
    assert "cli:mcp/serve" not in tiers

    result = CliRunner().invoke(cli, ["add", "--help"])
    assert result.exit_code == 0
    assert "[core]" in result.output






def test_cli_help_labels_each_top_level_command_support_tier() -> None:
    policy = load_support_policy()
    tiers = {item["id"]: item["tier"] for item in policy["surfaces"] if item["kind"] == "cli"}

    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    for name in cli.commands:
        assert f"[{tiers[f'cli:{name}']}]" in result.output





