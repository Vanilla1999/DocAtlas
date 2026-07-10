from __future__ import annotations

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import ALL_TOOLS


def _constraint_packet() -> dict:
    return {
        "task": "Update permissions",
        "constraints": [
            {
                "id": "generated",
                "type": "generated_file",
                "instruction": "Generated files *.g.dart must not be edited by hand.",
                "source": "docs/architecture.md",
                "severity": "must",
                "confidence": "high",
                "evidence": "Generated files *.g.dart must not be edited by hand.",
                "files": ["*.g.dart"],
                "symbols": [],
            }
        ],
    }


def test_validate_patch_against_constraints_mcp_schema():
    tool = next(tool for tool in ALL_TOOLS if tool["name"] == "validate_patch_against_constraints")

    properties = tool["inputSchema"]["properties"]
    assert properties["constraints"]["type"] == ["object", "array"]
    assert properties["project_path"]["type"] == ["string", "null"]
    assert properties["changed_files"]["items"]["type"] == "string"
    assert properties["patch_diff"]["type"] == ["string", "null"]
    assert properties["strict"]["type"] == "boolean"
    assert tool["inputSchema"]["required"] == ["constraints"]


def test_validate_patch_against_constraints_mcp_returns_packet():
    payload = handle_project_tool(
        "validate_patch_against_constraints",
        {"constraints": _constraint_packet(), "changed_files": ["lib/user/user.g.dart"]},
        LibraryDocsService(),
    )

    assert payload is not None
    assert payload["total_constraints"] == 1
    assert payload["violated"] == 1
    assert isinstance(payload["results"], list)
    assert isinstance(payload["warnings"], list)
    assert payload["confidence"] in {"high", "medium", "low"}


def test_validate_patch_against_constraints_handles_empty_constraints():
    payload = handle_project_tool("validate_patch_against_constraints", {"constraints": []}, LibraryDocsService())

    assert payload is not None
    assert payload["total_constraints"] == 0
    assert payload["violated"] == 0


def test_validate_patch_against_constraints_reports_warning_for_missing_patch_and_changed_files():
    payload = handle_project_tool("validate_patch_against_constraints", {"constraints": _constraint_packet()}, LibraryDocsService())

    assert payload is not None
    assert any("changed_files or patch_diff" in warning for warning in payload["warnings"])


def test_validate_patch_against_constraints_detects_generated_file_violation():
    payload = handle_project_tool(
        "validate_patch_against_constraints",
        {"constraints": _constraint_packet(), "changed_files": ["lib/user/user.g.dart"]},
        LibraryDocsService(),
    )

    assert payload is not None
    assert payload["violated"] == 1


def test_validate_patch_against_constraints_detects_lockfile_violation():
    packet = {
        "constraints": [
            {
                "id": "lock",
                "type": "forbidden_edit",
                "instruction": "Do not change lockfile.",
                "source": "pubspec.lock",
                "severity": "must",
                "confidence": "high",
                "evidence": "Do not change lockfile.",
                "files": ["pubspec.lock"],
                "symbols": [],
            }
        ]
    }

    payload = handle_project_tool(
        "validate_patch_against_constraints",
        {"constraints": packet, "changed_files": ["pubspec.lock"]},
        LibraryDocsService(),
    )

    assert payload is not None
    assert payload["violated"] == 1
