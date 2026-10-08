"""Generated, installed and packaged guidance stays usable without host setup."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import re
import zipfile

import jsonschema
import pytest

from docmancer.cli import _commands_part01 as guidance
from docmancer.cli import _commands_part02 as packaging
from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts


ROOT = Path(__file__).resolve().parents[1]


def _links(text):
    return re.findall(r"\]\(([^)]+\.md)\)", text)


def _canonical():
    raw = files("docmancer.templates").joinpath("agent_contract.md").read_text(encoding="utf-8")
    return raw.replace("{{DOCATLAS_AGENT_CONTRACT_ID}}", public_agent_contract()["identity"]).strip()


@pytest.mark.parametrize("template,destination", [
    ("skill.md", ".config/opencode/skills/docatlas/SKILL.md"),
    ("claude_code_skill.md", ".claude/skills/docatlas/SKILL.md"),
    ("claude_desktop_skill.md", "export/docatlas/Skill.md"),
    ("cursor_agents_md.md", ".cursor/AGENTS.md"),
    ("copilot_instructions.md", ".copilot/copilot-instructions.md"),
    ("project_bootstrap.md", "project/AGENTS.md"),
])
def test_generated_guidance_installs_all_references_and_preserves_user_text(tmp_path, monkeypatch, template, destination):
    monkeypatch.setattr(guidance, "_resolve_skill_command", lambda config: "doc-atlas")
    content = guidance._build_skill_content(template, None)
    assert _canonical() in content
    assert "{{" not in content
    links = _links(content)
    assert set(links) == {
        f"docatlas-references/{name}.md" for name in ("prepare", "troubleshooting", "cli", "patch")
    }
    destination = tmp_path / destination
    def install(content, destination):
        if destination.name.lower() == "skill.md":
            guidance._install_skill_file(content, destination)
        else:
            guidance._install_or_append_agents_md(destination, content)
    install(content, destination)
    destination.write_text(destination.read_text() + "\nUser instructions stay here.\n")
    for link in links:
        reference = destination.parent / link
        reference.write_text(reference.read_text() + "\nUser guide annotation.\n")
    install(content, destination)
    install(content, destination)
    after = destination.read_text()
    assert after.count(_canonical()) == 1
    assert after.endswith("\nUser instructions stay here.\n")
    for link in links:
        reference = destination.parent / link
        text = reference.read_text()
        expected = files("docmancer.templates").joinpath("references", reference.name).read_text(encoding="utf-8").strip()
        assert text == f"{guidance._AGENTS_MD_START}\n{expected}\n{guidance._AGENTS_MD_END}\n\nUser guide annotation.\n"


def test_root_workflow_matches_generated_contract_and_links_to_real_assets():
    root = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    canonical = _canonical()
    assert root[root.index("1. Start"):].replace("docmancer/templates/references/", "docatlas-references/").strip() == canonical[canonical.index("1. Start"):]
    for link in _links(root):
        assert (ROOT / link).is_file()
    # Compact entry points link detail rather than embedding it.
    assert len(root.encode()) < len(b"".join((ROOT / link).read_bytes() for link in _links(root)))
    assert 'context_format="patch_context"' not in root
    assert 'context_format="patch_context"' not in canonical


def test_default_examples_and_installed_identity_match_exact_runtime_contract(monkeypatch):
    contract = public_agent_contract()
    payload = deepcopy(contract)
    identity = payload.pop("identity")
    digest = lambda value: hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert identity == "sha256:" + digest(payload)
    tools = runtime_public_tool_dicts()
    assert tuple(tool["name"] for tool in tools) == ("get_docs_context", "prepare_docs", "docs_status")
    assert contract["tools"] == [{
        "name": tool["name"],
        "description_sha256": digest(tool["description"]),
        "input_schema_sha256": digest(tool["inputSchema"]),
        "output_schema_sha256": digest(tool.get("outputSchema")),
        "tool_contract_sha256": digest(tool),
    } for tool in tools]
    by_name = {tool["name"]: tool for tool in tools}
    for example in contract["examples"]:
        jsonschema.validate(example["arguments"], by_name[example["tool"]]["inputSchema"])
        assert "context_format" not in example["arguments"]
    assert contract["workflow"]["first_call"]["coding_context_format"] is None
    assert contract["workflow"]["first_call"]["skill_read_required"] is False
    assert contract["workflow"]["advanced_patch"] == {
        "default_available": False,
        "startup_setting": "DOCATLAS_MCP_ADVANCED_TOOLS=1",
        "context_format": "patch_context",
        "patch_evidence_representation_cap": None,
        "authorizes_edit": False,
    }
    assert identity in guidance._get_template_content("skill.md")
    # Ambient advanced mode never silently changes the installed default contract.
    monkeypatch.setenv("DOCATLAS_MCP_ADVANCED_TOOLS", "1")
    assert public_agent_contract() == contract


def test_desktop_archive_contains_exact_generated_skill_and_linked_guides(tmp_path, monkeypatch):
    monkeypatch.setattr(packaging, "_ensure_user_home", lambda **kwargs: tmp_path)
    monkeypatch.setattr(guidance, "_resolve_skill_command", lambda config: "doc-atlas")
    archive = packaging._create_claude_desktop_zip(None)
    with zipfile.ZipFile(archive) as package:
        skill = package.read("docatlas/Skill.md").decode()
        assert skill == guidance._build_skill_content("claude_desktop_skill.md", None)
        assert set(package.namelist()) == {"docatlas/Skill.md", *("docatlas/" + link for link in _links(skill))}
        for link in _links(skill):
            expected = files("docmancer.templates").joinpath("references", Path(link).name).read_bytes()
            assert package.read("docatlas/" + link) == expected


def test_wheel_contains_templates_and_all_linked_guide_bytes(tmp_path):
    # Existing build backend only: no dependency installation or child process.
    from hatchling.builders.wheel import WheelBuilder

    builder = WheelBuilder(str(ROOT))
    wheel = next(builder.build(directory=str(tmp_path), versions=["standard"]))
    with zipfile.ZipFile(wheel) as package:
        template = package.read("docmancer/templates/agent_contract.md").decode()
        assert template == files("docmancer.templates").joinpath("agent_contract.md").read_text(encoding="utf-8")
        for link in _links(template):
            source = files("docmancer.templates").joinpath("references", Path(link).name)
            assert package.read("docmancer/templates/references/" + source.name) == source.read_bytes()
        for name in ("skill.md", "claude_code_skill.md", "claude_desktop_skill.md", "cursor_agents_md.md", "copilot_instructions.md", "project_bootstrap.md"):
            assert package.read("docmancer/templates/" + name) == files("docmancer.templates").joinpath(name).read_bytes()
