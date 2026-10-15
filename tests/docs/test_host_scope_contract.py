"""Host-visible scope intent and real project/module isolation are distinct."""
from copy import deepcopy
import hashlib

import jsonschema
import pytest
import yaml

from docmancer.cli.commands import _get_template_content
from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.mcp._docs_server_part01 import create_local_mcp_service
from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts
from docmancer.mcp.docs_server import call_docs_tool_payload
from tests._shared_test_docs_service import _flutter_project
from tests.docs._scope_guidance_contract import assert_public_scope_guidance




@pytest.mark.parametrize("scope,module_path,question,expected", [
    ("all", None, "What constraints apply to `BackendOnlyAnswer`?", "packages/backend/README.md"),
    ("project", None, "What constraints apply to `BackendOnlyAnswer`?", None),
    ("module", "packages/backend", "What constraints apply to `SharedNeedle`?", "packages/backend/README.md"),
    ("all", "packages/backend", "What constraints apply to `SharedNeedle`?", "packages/backend/README.md"),
    ("all", None, "What constraints apply to `ForeignOnlyAnswer`?", None),
])
def test_public_scope_never_implicitly_widens(tmp_path, monkeypatch, scope, module_path, question, expected):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text(
        "# Root\n\nConstraints apply to `SharedNeedle`: repository-level validation is required. "
        "Constraints apply to `RootOnlyAnswer`: it is root-only.\n"
    )
    for name in ("backend", "frontend"):
        module = project / "packages" / name
        module.mkdir(parents=True)
        (module / "README.md").write_text(
            f"# {name}\n\nConstraints apply to `SharedNeedle`: {name}-local validation is required. "
            f"Constraints apply to `{name.title()}OnlyAnswer`: {name}-local validation is required.\n"
        )
    foreign_root = tmp_path / "foreign"
    foreign_root.mkdir()
    foreign = _flutter_project(foreign_root)
    (foreign / "README.md").write_text(
        "# Foreign\n\nConstraints apply to `ForeignOnlyAnswer`: foreign-local validation is required.\n"
    )
    # Use private pytest host state, not the group-writable checkout ancestor.
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "app-home"))
    monkeypatch.delenv("DOCATLAS_INDEX_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    service = create_local_mcp_service()
    assert not service.member_storage_policy.app_home.exists()
    generation = None
    for target in (project, foreign):
        documents = [{"path": "README.md", "role": "overview", "scope": "project",
                      "description": "Repository-level constraints."}]
        if target == project:
            documents.extend({"path": f"packages/{name}/README.md", "role": "module_architecture",
                              "scope": "module", "module_path": f"packages/{name}",
                              "description": f"{name} module constraints."}
                             for name in ("backend", "frontend"))
        catalog_path = target / "docatlas.project-docs.yaml"
        catalog_path.write_text(yaml.safe_dump({"schema_version": 1, "code_files": [],
                                                "documents": documents}))
        entries = read_project_docs_catalog(target).entries
        assert {entry.path for entry in entries} == {row["path"] for row in documents}
        prepared = call_docs_tool_payload("prepare_docs", {
            "action": "sync_project_docs", "project_path": str(target), "mutation": {
                "operation": "sync_project_docs", "confirm": True,
                "storage_path": str(service.member_storage_policy.db_path),
                "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
                "expected_generation_id": generation,
                "documents": [{"path": entry.path,
                               "content_sha256": hashlib.sha256((target / entry.path).read_bytes()).hexdigest(),
                               "catalog_entry_hash": catalog_entry_hash(entry)} for entry in entries],
            },
        }, service)
        assert prepared.get("status") == "success", prepared
        updated = prepared["metrics"]["generation_id"]
        assert updated != generation
        generation = updated
        assert service.member_storage_policy.generation() == generation
    # Negative isolation must not pass merely because the foreign evidence is
    # unqualified or the root/module catalog failed to reach the real index.
    for target, anchor in ((project, "SharedNeedle"), (foreign, "ForeignOnlyAnswer")):
        control = call_docs_tool_payload("get_docs_context", {
            "question": f"What constraints apply to `{anchor}`?",
            "project_path": str(target), "scope": "project",
        }, service)
        assert {source["path_or_url"] for source in control.get("sources", [])} == {"README.md"}, control
    request = {"question": question, "project_path": str(project), "scope": scope}
    if module_path:
        request["module_path"] = module_path
    before = deepcopy(request)
    payload = call_docs_tool_payload("get_docs_context", request, service)
    assert request == before
    paths = {s["path_or_url"] for s in payload.get("sources", [])}
    if expected:
        assert expected in paths, payload
        for source in payload["sources"]:
            assert source["snippet"] in (project / source["path_or_url"]).read_text()
    elif "BackendOnlyAnswer" in question:
        assert not any(path.startswith("packages/") for path in paths)
    else:
        assert not paths, payload
    if module_path:
        assert paths == {"packages/backend/README.md"}
    assert payload.get("answer_supported") is not True
    assert payload.get("edit_ready") is not True
