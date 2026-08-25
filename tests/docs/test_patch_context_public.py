from __future__ import annotations

import shutil
from pathlib import Path

from docmancer.docs.interfaces.mcp.context_tools import handle_context_tool
from tests._shared_test_docs_service import _service_with_real_agent


class _Facade:
    def __init__(self, context_pack: list[dict]) -> None:
        self.context_pack = context_pack

    def get_docs_context(self, question: str, **kwargs):
        return {
            "tool": "get_docs_context",
            "status": "success",
            "answer_available": True,
            "context_pack": self.context_pack,
            "lanes": {"project": {"status": "success", "source_count": len(self.context_pack)}},
            "trust_contract": {"selected": [], "rejected": [], "risky": []},
        }


def _source(path: str, declaration: str) -> dict:
    return {
        "path": path,
        "source": path,
        "source_class": "source_evidence",
        "authority": "supporting",
        "content": declaration,
        "symbols": [{"kind": "class", "name": declaration.split()[1]}],
    }


def test_exact_permission_patch_is_publicly_edit_ready() -> None:
    question = (
        "Fix partial permission handling in BrowserPermissionGate, ScanPermissionGate, "
        "OfflineSyncGate, and PermissionService without changing "
        "permission_result.freezed.dart."
    )
    context_pack = [
        _source("lib/browser_permission_gate.dart", "class BrowserPermissionGate"),
        _source("lib/scan_permission_gate.dart", "class ScanPermissionGate"),
        _source("lib/offline_sync_gate.dart", "class OfflineSyncGate"),
        _source("lib/permission_service.dart", "class PermissionService"),
        {
            "path": "lib/permission_result.freezed.dart",
            "source": "lib/permission_result.freezed.dart",
            "source_class": "source_evidence",
            "authority": "supporting",
            "content": "// generated PermissionResult",
        },
        {
            "path": "docs/permission-architecture.md",
            "source": "docs/permission-architecture.md",
            "source_class": "project_doc",
            "authority": "canonical",
            "content": (
                "BrowserPermissionGate, ScanPermissionGate, OfflineSyncGate, and "
                "PermissionService share the partial permission handling contract."
            ),
        },
    ]

    payload = handle_context_tool(
        "get_docs_context",
        {
            "question": question,
            "project_path": "/repo",
            "delivery_strategy": "bounded_direct",
            "packet_tokens": 2_000,
        },
        _Facade(context_pack),
    )

    assert payload["kind"] == "patch_context"
    assert payload["status"] in {"ok", "truncated"}
    assert payload["mutation_ready"] is True
    assert payload["edit_ready"] is True
    assert payload["mutation_intent"]["ready"] is True
    assert {
        target["requested_value"]
        for target in payload["mutation_intent"]["resolved_targets"]
    } == {
        "BrowserPermissionGate",
        "ScanPermissionGate",
        "OfflineSyncGate",
        "PermissionService",
    }
    assert payload["mutation_intent"]["preserved_targets"][0][
        "requested_value"
    ] == "permission_result.freezed.dart"
    assert any(
        item.get("provenance") == "user_request"
        and "permission_result.freezed.dart" in item.get("text", "")
        for item in payload["forbidden_changes"]
    )


def test_source_search_recovery_never_authorizes_editing() -> None:
    payload = handle_context_tool(
        "get_docs_context",
        {
            "question": "Fix MissingPermissionGate.",
            "project_path": "/repo",
            "delivery_strategy": "bounded_direct",
        },
        _Facade([]),
    )

    assert payload["kind"] == "patch_context"
    assert payload["status"] == "insufficient_evidence"
    assert payload["investigation_allowed"] is True
    assert payload["edit_ready"] is False
    assert payload["source_search_status"] == "required"


def test_project_docs_cannot_authorize_source_mutation_target() -> None:
    payload = handle_context_tool(
        "get_docs_context",
        {
            "question": "Fix BrowserPermissionGate.",
            "project_path": "/repo",
            "delivery_strategy": "bounded_direct",
        },
        _Facade([{
            "path": "docs/architecture.md",
            "source": "docs/architecture.md",
            "source_class": "project_doc",
            "authority": "canonical",
            "content": "BrowserPermissionGate is documented here.",
            "symbols": ["BrowserPermissionGate"],
        }]),
    )

    assert payload["kind"] == "patch_context"
    assert payload["status"] == "insufficient_evidence"
    assert payload["edit_ready"] is False
    assert payload["source_search_status"] == "required"


def test_source_recovery_prioritizes_unresolved_target_after_first_eight() -> None:
    paths = [f"src/target_{index}.py" for index in range(1, 10)]
    payload = handle_context_tool(
        "get_docs_context",
        {
            "question": "Fix " + ", ".join(paths) + ".",
            "project_path": "/repo",
            "delivery_strategy": "bounded_direct",
        },
        _Facade([
            {"path": path, "source": path, "source_class": "source_evidence", "content": path}
            for path in paths[:8]
        ]),
    )

    action = payload["recommended_next_action"]
    assert paths[8] in action["query_terms"]


def test_exact_permission_patch_passes_real_project_service(
    tmp_path, monkeypatch,
) -> None:
    template = (
        Path(__file__).parents[2]
        / "eval/task_level/fixtures/templates/decisive_nbo_cross_module_gate_large_001"
    )
    project = tmp_path / "permission-project"
    shutil.copytree(template, project)
    documents = [
        "README.md",
        "docs/browser-flow.md",
        "docs/scan-flow.md",
        "docs/offline-sync.md",
        "docs/permission-architecture.md",
        "docs/generated-files.md",
    ]
    for path in documents:
        (project / path).write_text("# Supporting fixture\n", encoding="utf-8")
    (project / "docs/permission-architecture.md").write_text(
        """# Permission architecture

Partial permission handling in BrowserPermissionGate, ScanPermissionGate,
OfflineSyncGate, and PermissionService must be consistent.
Each gate must preserve partial grant and denial details instead of reducing
the decision to a boolean. `permission_result.freezed.dart` is generated and
must not be edited directly.
""",
        encoding="utf-8",
    )
    manifest = ["schema_version: 1", "documents:"]
    for path in documents:
        manifest.extend((
            f"  - path: {path}",
            "    role: development",
            "    scope: project",
            f"    description: Authoritative permission evidence in {path}.",
            "    authority: source_of_truth",
            "    status: active",
            "    impact: track",
        ))
    (project / "docatlas.project-docs.yaml").write_text(
        "\n".join(manifest) + "\n", encoding="utf-8",
    )
    service = _service_with_real_agent(tmp_path, monkeypatch)
    assert service.ingest_project_docs(str(project), with_vectors=False).status == "success"

    payload = handle_context_tool(
        "get_docs_context",
        {
            "question": (
                "Fix partial permission handling in BrowserPermissionGate, "
                "ScanPermissionGate, OfflineSyncGate, and PermissionService "
                "without changing permission_result.freezed.dart."
            ),
            "project_path": str(project),
            "mode": "project",
            "delivery_strategy": "bounded_direct",
            "packet_tokens": 2_000,
        },
        service,
    )

    assert payload["kind"] == "patch_context"
    assert payload["status"] in {"ok", "truncated"}, payload.get("missing")
    assert payload["mutation_ready"] is True
    assert payload["edit_ready"] is True
