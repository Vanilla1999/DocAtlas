"""Exercise generated host config and template boundaries in disposable paths."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from docmancer.mcp.agent_config import AgentTarget, register_server, target_has_current_server_entry
from docmancer.mcp.agent_workflow_contract import public_agent_contract
from docmancer.cli._commands_part01 import _build_skill_content
from docmancer.mcp.docs_server import DocsServerConfig, build_docs_surface, read_docs_resource
from docmancer.mcp._docs_server_resources import MCP_RESOURCES, MCP_RESOURCE_TEMPLATES


def main() -> None:
    rows = []
    with TemporaryDirectory(prefix="pr211-config-", dir="/tmp/opencode") as temp:
        for style in ("json_mcpServers", "json_mcp_servers", "json_opencode_mcp", "json_vscode_servers", "toml_mcp_servers"):
            path = Path(temp) / (style + (".toml" if style.startswith("toml") else ".json"))
            target = AgentTarget("audit-only", path, style)
            first = register_server(target)
            before = path.read_bytes()
            second = register_server(target)
            assert first[0] and not second[0]
            assert before == path.read_bytes() and target_has_current_server_entry(target)
            rows.append({"style": style, "generated": before.decode(), "sha256": hashlib.sha256(before).hexdigest(),
                         "idempotent": True, "recognized_current": True,
                         "classification": "TECHNICAL: explicit host format/command/environment; no question-dependent branch"})
    templates = []
    for path in sorted(Path("docmancer/templates").glob("*.md")):
        rendered = _build_skill_content(path.name, "/tmp/opencode/p0-audit-config.yaml")
        templates.append({"path": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(), "rendered": rendered,
                          "remaining_placeholders": "{{" in rendered})
    surfaces = []
    for admin in (False, True):
        for advanced in (False, True):
            for fallback in (False, True):
                surface = build_docs_surface(DocsServerConfig(expose_admin=admin, expose_advanced=advanced, text_fallback=fallback))
                surfaces.append({"admin": admin, "advanced": advanced, "text_fallback": fallback,
                                 "tools": [spec.to_tool_dict() for spec in surface.tools],
                                 "handlers": {name: handler.__module__ + "." + handler.__name__ for name, handler in surface.handlers.items()}})
    resources = [read_docs_resource(row["uri"]) for row in MCP_RESOURCES]
    resources.extend(read_docs_resource(uri) for uri in
                     ("docmancer://workflow/project-docs/audit-only-project", "docmancer://library/python/audit-only-library/1.0"))
    print(json.dumps({"schema": "p0-config-boundaries-v1", "host_configs": rows,
                      "surfaces": surfaces, "resources": resources, "resource_templates": MCP_RESOURCE_TEMPLATES,
                      "templates": templates, "agent_contract": public_agent_contract(),
                      "external_boundary": "User host files are not read or modified. Existing unrelated keys are outside product-owned content; these probes use only disposable files.",
                      "classification": "Workflow examples/guidance require semantic review separately from technical config serialization."}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
