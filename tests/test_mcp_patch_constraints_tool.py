from __future__ import annotations

import json
from pathlib import Path

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import TOOLS


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs/architecture.md").write_text(
        "PermissionService is the source-of-truth. Providers delegate to PermissionService and do not duplicate policy.\n"
        "Generated files *.g.dart and *.freezed.dart must not be edited by hand; regenerate from source models.\n",
        encoding="utf-8",
    )
    (root / "pubspec.lock").write_text('packages:\n  permission_handler:\n    version: "11.4.0"\n', encoding="utf-8")
    return root


def _payload(tmp_path: Path, **overrides):
    args = {
        "question": "Update permission handling",
        "project_path": str(_workspace(tmp_path)),
        "changed_files": ["lib/modules/permission/domain/services/permission_service.dart"],
        "max_constraints": 12,
        "max_tokens": 1200,
        "include_sources": True,
    }
    args.update(overrides)
    return handle_project_tool("get_patch_constraints", args, LibraryDocsService())


def test_mcp_schema_exposes_get_patch_constraints():
    tool = next(tool for tool in TOOLS if tool["name"] == "get_patch_constraints")

    assert tool["inputSchema"]["required"] == ["question"]
    properties = tool["inputSchema"]["properties"]
    assert properties["question"]["type"] == "string"
    assert properties["project_path"]["type"] == ["string", "null"]
    assert properties["changed_files"]["items"]["type"] == "string"
    assert properties["max_constraints"]["type"] == "integer"
    assert properties["max_tokens"]["type"] == "integer"
    assert properties["include_sources"]["type"] == "boolean"
    assert properties["output_mode"]["enum"] == ["compact", "debug", "full", None]


def test_mcp_return_shape(tmp_path: Path):
    payload = _payload(tmp_path)

    assert payload is not None
    assert payload["task"] == "Update permission handling"
    assert isinstance(payload["constraints"], list)
    assert isinstance(payload["forbidden_edits"], list)
    assert isinstance(payload["dependency_contracts"], list)
    assert isinstance(payload["source_of_truth_rules"], list)
    assert isinstance(payload["suggested_checks"], list)
    assert isinstance(payload.get("warnings", []), list)
    assert isinstance(payload["sources"], list)
    assert isinstance(payload["token_estimate"], int)
    assert payload["confidence"] in {"high", "medium", "low"}
    assert any(item["source"] for item in payload["constraints"])


def test_mcp_return_shape_is_json_serializable(tmp_path: Path):
    payload = _payload(tmp_path, question="Avoid generated files")
    json.dumps(payload)


def test_mcp_tool_returns_grouped_constraints(tmp_path: Path):
    payload = _payload(tmp_path)
    assert payload["forbidden_edits"]
    assert payload["dependency_contracts"]
    assert payload["source_of_truth_rules"]
    assert any("test" in check.lower() or "verify" in check.lower() for check in payload["suggested_checks"])


def test_mcp_tool_respects_max_constraints_and_max_tokens(tmp_path: Path):
    payload = _payload(tmp_path, max_constraints=2, max_tokens=180)
    assert len(payload["constraints"]) <= 2
    assert payload["token_estimate"] <= 180
    assert any("constraints truncated by budget" in warning for warning in payload["warnings"])


def test_mcp_tool_applies_compact_cap_without_debug_noise(tmp_path: Path):
    compact = handle_project_tool("get_patch_constraints", {
        "question": "Update permission handling",
        "project_path": str(_workspace(tmp_path)),
        "max_constraints": 50,
        "max_tokens": 120_000,
        "include_sources": True,
    }, LibraryDocsService())
    assert len(json.dumps(compact, ensure_ascii=False).encode("utf-8")) <= 32_000
    assert "mcp_compaction" not in compact
