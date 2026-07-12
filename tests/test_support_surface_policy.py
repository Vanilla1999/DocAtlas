from __future__ import annotations

import re
from copy import deepcopy
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
from docmancer.support_policy import load_support_policy, validate_support_policy


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


def test_support_policy_classifies_every_shipped_cli_and_mcp_surface() -> None:
    policy = load_support_policy()

    assert validate_support_policy(policy) == []
    assert _click_surface_ids(cli) == _ids(policy, "cli")

    expected_mcp = set()
    configurations = (
        DocsServerConfig(),
        DocsServerConfig(expose_advanced=True),
        DocsServerConfig(expose_legacy=True),
        DocsServerConfig(expose_admin=True),
    )
    for config in configurations:
        expected_mcp.update(f"mcp:docs/{tool.name}" for tool in build_docs_surface(config).tools)
    assert expected_mcp == _ids(policy, "mcp_tool")


def test_support_policy_classifies_mcp_resources_templates_and_packs_namespace() -> None:
    expected_resources = {f"mcp-resource:{item['uri']}" for item in MCP_RESOURCES}
    expected_templates = {f"mcp-template:{item['uriTemplate']}" for item in MCP_RESOURCE_TEMPLATES}
    expected_packs = {f"mcp-packs:{SEARCH_TOOL}", f"mcp-packs:{CALL_TOOL}", "mcp-packs:dynamic-namespace"}
    policy = load_support_policy()

    assert expected_resources == _ids(policy, "mcp_resource")
    assert expected_templates == _ids(policy, "mcp_template")
    assert expected_packs == _ids(policy, "mcp_dynamic")


def test_support_policy_classifies_every_installed_extra() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = set(project["project"]["optional-dependencies"])

    assert {f"extra:{name}" for name in extras} == _ids(load_support_policy(), "extra")


def test_dependency_policy_tracks_current_core_and_task24_candidates() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_names = {
        re.split(r"[<>=!~;\[]", requirement, maxsplit=1)[0].strip()
        for requirement in project["project"]["dependencies"]
    }
    dependency_policy = load_support_policy()["dependency_policy"]

    assert set(dependency_policy["current_core"]) == package_names
    assert set(dependency_policy["task24_extra_candidates"]) <= package_names
    assert "Task 24" in dependency_policy["decision"]


def test_support_policy_classifies_every_public_connector_and_store() -> None:
    fetcher_dir = ROOT / "docmancer" / "connectors" / "fetchers"
    ignored = {"__init__", "base", "factory"}
    connectors = {
        f"connector:{path.stem.replace('_', '-')}"
        for path in fetcher_dir.glob("*.py")
        if path.stem not in ignored
    }
    connectors.add("connector:uspto-tm")
    stores = {
        f"store:{path.stem.removesuffix('_store').replace('_', '-')}"
        for path in (ROOT / "docmancer" / "stores").glob("*_store.py")
    }

    policy = load_support_policy()
    assert connectors == _ids(policy, "connector")
    assert stores == _ids(policy, "store")


def test_non_core_surfaces_have_complete_ownership_and_release_policy() -> None:
    required = {
        "owner",
        "docs",
        "test_tier",
        "network_dependencies",
        "compatibility",
        "removal_rule",
        "failure_budget",
    }
    for surface in load_support_policy()["surfaces"]:
        if surface["tier"] != "core":
            assert required <= surface.keys(), surface["id"]
            assert all(surface[field] not in (None, "", []) for field in required - {"network_dependencies"}), surface["id"]


def test_expired_deprecations_have_explicit_resolution() -> None:
    deprecated = [item for item in load_support_policy()["surfaces"] if item["tier"] == "deprecated"]

    assert deprecated
    for surface in deprecated:
        assert surface["deprecation"]["resolution"] in {"remove_in_breaking_release", "deadline_extended"}
        assert surface["deprecation"]["deadline"]


def test_deprecation_validator_rejects_malformed_and_expired_deadlines() -> None:
    malformed = deepcopy(load_support_policy())
    deprecated = next(item for item in malformed["surfaces"] if item["tier"] == "deprecated")
    deprecated["deprecation"]["deadline"] = "someday"
    assert any("dotted release version" in error for error in validate_support_policy(malformed))

    expired = deepcopy(load_support_policy())
    deprecated = next(item for item in expired["surfaces"] if item["tier"] == "deprecated")
    deprecated["deprecation"]["deadline"] = "1.0.0"
    assert any("has expired" in error for error in validate_support_policy(expired))


def test_cli_help_labels_each_top_level_command_support_tier() -> None:
    policy = load_support_policy()
    tiers = {item["id"]: item["tier"] for item in policy["surfaces"] if item["kind"] == "cli"}

    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    for name in cli.commands:
        assert f"[{tiers[f'cli:{name}']}]" in result.output


def test_ci_separates_offline_core_from_optional_advanced_and_live_suites() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "DOCMANCER_OFFLINE: \"1\"" in workflow
    assert "pytest tests/ -m \"not advanced and not live and not live_network\"" in workflow
    assert "advanced-contract:" in workflow
    assert "pytest tests/ -m advanced" in workflow
    assert "live:" not in workflow


def test_support_policy_docs_define_failure_budgets_and_bounded_deprecations() -> None:
    text = (ROOT / "docs" / "support-surface-policy.md").read_text(encoding="utf-8")

    assert "Core offline CI" in text
    assert "Advanced network outage" in text
    assert "2.0.0" in text
    assert "shared security and storage regressions" in text


def test_readme_advanced_section_links_support_tiers() -> None:
    advanced = (ROOT / "README.md").read_text(encoding="utf-8").split("## Advanced surfaces", maxsplit=1)[1]

    assert "advanced-supported" in advanced
    assert "maintenance-only" in advanced
    assert "support-surface-policy.md" in advanced
