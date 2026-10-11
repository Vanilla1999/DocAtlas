"""Real qualified context through the public handler."""
from copy import deepcopy
import hashlib
import json
import yaml

from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
from docmancer.docs.application.project_docs_member_transaction import catalog_entry_hash
from docmancer.docs.domain.project_retrieval_intent import project_retrieval_disposition
from docmancer.docs.interfaces.mcp import context_tools
from docmancer.docs.project_docs_catalog import read_project_docs_catalog
from docmancer.mcp._docs_server_part01 import create_local_mcp_service
from docmancer.mcp.docs_server import call_docs_tool_payload


def test_legacy_fail_closed_adapter_does_not_block_real_qualified_context(tmp_path, monkeypatch):
    question = "Does guide.md prove the source ownership contract?"
    assert project_retrieval_disposition(question) == "fail_closed"
    root = tmp_path / "project"
    root.mkdir()
    text = "# Source ownership\n\nguide.md defines the source ownership contract: source bytes remain repository-local.\n"
    (root / "guide.md").write_text(text)
    catalog = root / "docatlas.project-docs.yaml"
    catalog.write_text(yaml.safe_dump({"schema_version": 1, "code_files": [], "documents": [
        {"path": "guide.md", "role": "overview", "scope": "project", "description": "Source ownership contract."},
    ]}))
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "app-home"))
    monkeypatch.delenv("DOCATLAS_INDEX_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    service = create_local_mcp_service()
    assert not service.member_storage_policy.app_home.exists()
    entry, = read_project_docs_catalog(root).entries
    prepared = call_docs_tool_payload("prepare_docs", {
        "action": "sync_project_docs", "project_path": str(root), "mutation": {
            "operation": "sync_project_docs", "confirm": True,
            "storage_path": str(service.member_storage_policy.db_path),
            "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
            "expected_generation_id": None,
            "documents": [{"path": "guide.md", "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
                           "catalog_entry_hash": catalog_entry_hash(entry)}],
        },
    }, service)
    assert prepared.get("status") == "success", prepared
    request = {"question": question, "project_path": str(root), "scope": "project"}
    before = deepcopy(request)
    snapshots = []
    original_projection = context_tools.project_docs_context

    def observe_projection(*args, **kwargs):
        projected, snapshot = original_projection(*args, **kwargs)
        assert validate_model_visible_projection(projected, snapshot=snapshot, max_tokens=800) == []
        snapshots.append(snapshot)
        return projected, snapshot

    monkeypatch.setattr(context_tools, "project_docs_context", observe_projection)
    payload = call_docs_tool_payload("get_docs_context", request, service)
    assert request == before
    assert payload["status"] == "ok", payload
    assert snapshots
    assert {row["path_or_url"] for row in payload["sources"]} == {"guide.md"}
    for source in payload["sources"]:
        assert "source ownership contract" in source["snippet"]
        assert source["snippet"] in text
        raw = snapshots[-1][source["evidence_id"]]["source"]
        # Docs-mode digest binds the source envelope, unlike the v4 window hash.
        material = {
            "path": raw.get("path") or raw.get("source") or raw.get("url") or raw.get("source_url"),
            "section": raw.get("heading_path") or raw.get("title"),
            "content": raw.get("content") or raw.get("display_text"),
            "snippet": raw.get("snippet") or raw.get("code"),
            "version": raw.get("version_binding") or raw.get("version") or raw.get("requested_version"),
        }
        digest = hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True,
                                            separators=(",", ":")).encode()).hexdigest()
        assert source["content_sha256"] == digest
        assert source["line_start"] == 1 and source["line_end"] == 3
    assert payload["answer_supported"] is False and payload["edit_ready"] is False
    assert service.member_storage_policy.generation() == prepared["metrics"]["generation_id"]
