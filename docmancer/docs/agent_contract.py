"""Portable, machine-readable instructions for coding agents in a local project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.project_docs_catalog import CATALOG_FILENAME


SCHEMA_VERSION = "agent-contract-1"


def build_agent_contract(project_path: str | Path) -> dict[str, Any]:
    """Describe the local sources and DocAtlas workflow an agent must follow.

    The contract is intentionally a read-only snapshot. It is safe to generate in
    an agent loop before asking repository questions or changing code.
    """

    metadata = ProjectMetadataReader().read(project_path)
    docs = [
        {
            "path": candidate.path,
            "scope": candidate.doc_scope,
            "module_path": candidate.module_path,
            "role": candidate.reason,
            "description": candidate.description,
            "authority": candidate.authority,
            "status": candidate.lifecycle_status,
            "impact": candidate.impact_policy,
        }
        for candidate in metadata.docs_candidates
    ]
    dependencies = [
        {
            "name": item.package_name,
            "ecosystem": item.ecosystem,
            "group": item.dependency_group,
            "resolved_version": item.resolved_version,
            "version_source": item.version_source,
            "source_kind": item.source_kind,
        }
        for item in metadata.dependencies
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "path": metadata.project_path,
            "ecosystems": metadata.detected_ecosystems,
            "documentation": docs,
            "documentation_catalog": {
                "path": CATALOG_FILENAME,
                "mode": "explicit" if metadata.docs_catalog_present else "cold_start_discovery",
                "valid": metadata.docs_catalog_valid,
            },
            "dependencies": dependencies,
        },
        "tool_selection": {
            "decision_rule": "Use docs_status for an explicit health, freshness, index, or job-status request. Otherwise start with get_docs_context; call prepare_docs only from next_action or an explicit lifecycle request.",
            "default_tool": "get_docs_context",
            "tools": [
                {
                    "name": "get_docs_context",
                    "use_when": "Start of every repository, dependency, or mixed documentation question.",
                    "do_not_use_when": "The request only asks for index health, freshness, or background-job status.",
                },
                {
                    "name": "prepare_docs",
                    "use_when": "Only when get_docs_context returns it as next_action, or the user explicitly requests sync, refresh, indexing, or prefetching.",
                    "requires_user_approval": "Network actions require approval.",
                },
                {
                    "name": "docs_status",
                    "use_when": "An explicit health, freshness, index, or background-job status request.",
                },
            ],
        },
        "evidence_rules": [
            "For explicit health, freshness, index, or job-status requests, use docs_status; otherwise start with get_docs_context and follow its next_action.",
            "Use project documentation for repository conventions and decisions; use source code for current implementation.",
            "Use dependency documentation only for external APIs, with the resolved version when available.",
            "Cite the selected sources returned by DocAtlas; do not replace local evidence with model memory.",
        ],
        "maintenance": {
            "check_docs_after_code_change": "doc-atlas docs-impact --base <base-ref>",
            "refresh_project_docs": "Use prepare_docs(action=sync_project_docs) after file changes, or only when explicitly requested.",
            "fallback_without_mcp": [
                "doc-atlas context <question>",
                "doc-atlas query <question>",
                "doc-atlas docs-impact --base <base-ref>",
            ],
        },
        "warnings": metadata.warnings,
    }


def format_agent_contract_markdown(contract: dict[str, Any]) -> str:
    """Render a human-reviewable counterpart of the JSON agent contract."""

    project = contract["project"]
    lines = [
        "# DocAtlas agent contract",
        "",
        f"Project: `{project['path']}`",
        (
            "Documentation catalog: "
            f"`{project['documentation_catalog']['mode']}` "
            f"(valid: {'yes' if project['documentation_catalog']['valid'] else 'no'})"
        ),
        "",
        "## Required tool selection",
        "",
        "For an explicit health, freshness, index, or job-status request, use `docs_status`. Otherwise start with `get_docs_context`. Call `prepare_docs` only when it is returned as `next_action` or when the user explicitly requests a sync/refresh/index.",
        "",
        "## Local documentation sources",
        "",
    ]
    docs = project["documentation"]
    if docs:
        lines.extend(["| Path | Scope | Role | Description |", "|---|---|---|---|"])
        for item in docs:
            scope = item["scope"]
            if item["module_path"]:
                scope = f"{scope}: {item['module_path']}"
            lines.append(
                f"| `{_markdown_cell(item['path'])}` | {_markdown_cell(scope)} | "
                f"{_markdown_cell(item['role'])} | {_markdown_cell(item.get('description') or '')} |"
            )
    else:
        lines.append("No maintained documentation files were discovered.")
    lines.extend(["", "## Evidence rules", ""])
    lines.extend(f"- {rule}" for rule in contract["evidence_rules"])
    lines.extend(["", "## Maintenance", ""])
    lines.append(f"- Check doc impact: `{contract['maintenance']['check_docs_after_code_change']}`")
    lines.append(f"- Refresh indexed project docs: {contract['maintenance']['refresh_project_docs']}")
    return "\n".join(lines)


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("`", "&#96;").replace("\r", "").replace("\n", "<br>")
