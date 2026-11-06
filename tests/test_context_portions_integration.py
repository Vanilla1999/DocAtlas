"""Continuation contracts through real preparation, retrieval and public MCP dispatch."""
from __future__ import annotations

import json

import pytest

from eval.evidence_quality_v2.runtime import index_project, isolated_service, write_project
from docmancer.mcp.docs_server import call_docs_tool_payload, current_docs_surface, read_docs_resource


def test_minimal_candidate_public_full_scan_refs_and_scope(tmp_path, monkeypatch):
    """Real MiniLM/public MCP: 257 facts, source refs, scope and stale denial.

    Explicit host model provisioning is required. One preparation and one
    context request; no fake retrieval, scoring or source validation.
    """
    import hashlib
    import os
    from pathlib import Path
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    from docmancer.docs.application.standalone_text_view import render_standalone_text

    model = os.environ.get("DOCATLAS_TEST_MINI_MODEL_DIR")
    if not model:
        pytest.skip("explicit pinned local MiniLM assets required")
    project = tmp_path / "inventory"
    documents = {f"docs/serial-{i:03}.md": f"# Inventory\n\nSerial INV-{i:03} belongs to collection CEDAR.\n"
                 for i in range(257)}
    documents["modules/private/docs/secret.md"] = "# Inventory\n\nSerial PRIVATE must never enter project-only scope.\n"
    write_project(project, documents)
    import yaml
    catalog_path = project / "docatlas.project-docs.yaml"
    catalog = yaml.safe_load(catalog_path.read_text())
    for entry in catalog["documents"]:
        if entry["path"].startswith("modules/"):
            entry.update(scope="module", module_path="modules/private")
    catalog_path.write_text(yaml.safe_dump(catalog))
    with isolated_service(tmp_path / "state") as (service, config):
        monkeypatch.setenv("DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT", "1")
        monkeypatch.setenv("DOCATLAS_EXPERIMENT_MINI_PATH", model)
        monkeypatch.setenv("DOCATLAS_CONTEXT_COMPRESSION", "off")
        index_project(service, config, project)
        db = Path(config.index.db_path)
        before = hashlib.sha256(db.read_bytes()).hexdigest()
        args = {"project_path": str(project), "scope": "project",
                "question": "List every inventory serial and its collection."}
        result = call_docs_tool_payload("get_docs_context", args, service)
        (tmp_path / "inventory-receipt.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        assert result.get("status") == "ok", (result.get("reason_code"), result.get("source_selection"))
        rows = result["sources"]
        assert len(rows) == 257
        assert result["source_selection"]["candidate_units"] == 257
        assert result["source_selection"]["model_pairs"] == 257
        assert result["more_context"]["next_portion"] is None
        for i in range(257):
            row = next(row for row in rows if row["path_or_url"] == f"docs/serial-{i:03}.md")
            assert f"Serial INV-{i:03} belongs to collection CEDAR." in row["snippet"]
            assert row["snippet"] == documents[row["path_or_url"]]
        rendered = render_standalone_text(result)
        assert rendered.text is not None
        assert projection_token_count(rendered.text.encode()) <= 50000
        for row in (rows[0], rows[-1]):
            response = json.loads(read_docs_resource(row["source_uri"], service)["text"])
            assert response == {"status": "complete", "reason_code": "end_of_source"}
            replay = json.loads(read_docs_resource(row["source_uri"], service)["text"])
            assert replay["reason_code"] == "unknown_or_expired_reference"
        assert hashlib.sha256(db.read_bytes()).hexdigest() == before
        stale = rows[1]
        (project / stale["path_or_url"]).write_text("# Replaced\n\nUnprepared content.\n")
        denied = json.loads(read_docs_resource(stale["source_uri"], service)["text"])
        assert "snippet" not in denied and denied.get("status") in {"source_changed", "source_unavailable"}, denied


def test_minimal_candidate_public_emergency(tmp_path, monkeypatch):
    """One real model/public request: a permitted file with >50000 BPE tokens."""
    import hashlib
    import os
    from pathlib import Path
    from docmancer.docs.application.projection_tokenizer import projection_token_count

    model = os.environ.get("DOCATLAS_TEST_MINI_MODEL_DIR")
    if not model:
        pytest.skip("explicit pinned local MiniLM assets required")
    project = tmp_path / "large"
    # Fits the unchanged 256000-byte preparation authority limit while the
    # indivisible fenced block genuinely exceeds the 50000-token delivery stop.
    large = "# Ledger\n\n```text\n" + "".join(
        f"ledger {i:05} alpha beta gamma delta epsilon zeta eta theta lambda\n"
        for i in range(3800)) + "```\n"
    assert len(large.encode()) < 256000 and projection_token_count(large.encode()) > 50000
    write_project(project, {"docs/ledger.md": large})
    with isolated_service(tmp_path / "state") as (service, config):
        monkeypatch.setenv("DOCATLAS_EXPERIMENT_MINIMAL_CONTEXT", "1")
        monkeypatch.setenv("DOCATLAS_EXPERIMENT_MINI_PATH", model)
        monkeypatch.setenv("DOCATLAS_CONTEXT_COMPRESSION", "off")
        index_project(service, config, project)
        db = Path(config.index.db_path)
        before = hashlib.sha256(db.read_bytes()).hexdigest()
        stopped = call_docs_tool_payload("get_docs_context", {
            "project_path": str(project), "question": "Return the complete ledger."}, service)
        (tmp_path / "emergency-receipt.json").write_text(json.dumps(stopped, ensure_ascii=False, indent=2))
        assert stopped.get("reason_code") == "context_emergency_stop", stopped
        assert not stopped.get("sources")
        assert stopped["source_selection"]["measured_tokens"] > 50000
        assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_prepared_scope_stream_exhausts_without_lexical_ceiling(tmp_path):
    """Public prepare → real storage iterator; 257 facts, one scan, no model.

    This proves the acquisition boundary only, not final context delivery.
    """
    import hashlib
    from pathlib import Path
    from docmancer.core.sqlite_store import SQLiteStore

    project = tmp_path / "project"
    documents = {f"docs/item-{i:03}.md": f"# Item {i}\n\nInventory serial S{i:03} is retained.\n"
                 for i in range(257)}
    write_project(project, documents)
    with isolated_service(tmp_path / "state") as (service, config):
        inventory = index_project(service, config, project)
        assert not inventory["excluded_or_failed_paths"]
        store = SQLiteStore(config.index.db_path)
        db = Path(config.index.db_path)
        before = hashlib.sha256(db.read_bytes()).hexdigest()
        receipt = {}
        chunks = list(store.iter_scope_candidates(
            filters={"project_path": str(project.resolve()), "doc_scope": "project"},
            receipt=receipt,
        ))
        assert receipt["exhausted"] and receipt["status"] == "complete"
        assert receipt["generation_id"] == inventory["generation_id"]
        assert len(chunks) >= 257
        for path, original in documents.items():
            matching = [chunk for chunk in chunks if chunk.metadata.get("source_path") == path]
            assert matching, path
            assert all(chunk.text in original for chunk in matching)
            fact = original.split("\n\n", 1)[1].strip()
            assert any(fact in chunk.text for chunk in matching), path
        assert not list(store.iter_scope_candidates(filters={"doc_scope": "module"}))
        assert hashlib.sha256(db.read_bytes()).hexdigest() == before

        interrupted = {}
        stream = store.iter_scope_candidates(receipt=interrupted)
        next(stream)
        (project / "docs/item-000.md").write_text(documents["docs/item-000.md"] + "Revised.\n")
        index_project(service, config, project)
        with pytest.raises(ValueError, match="scope_scan_generation_changed"):
            list(stream)
        assert interrupted["status"] == "scan_incomplete" and not interrupted["exhausted"]


@pytest.fixture
def prepared_project(tmp_path, monkeypatch):
    project = tmp_path / "project"
    text = ("# Archive policy\n\nArchive records preserve their original timestamp.\n"
            "Archive records are stored in the west region.\n")
    write_project(project, {"docs/archive.md": text})
    with isolated_service(tmp_path / "state") as (service, config):
        monkeypatch.setenv("DOCATLAS_MCP_TEXT_FALLBACK", "1")
        monkeypatch.setenv("DOCATLAS_MCP_COMPACT_TEXT", "1")
        inventory = index_project(service, config, project)
        assert not inventory["excluded_or_failed_paths"]
        yield service, config, project, text


def test_context_portions_bind_snapshot_and_stop_after_exhaustion(prepared_project, monkeypatch):
    service, config, project, text = prepared_project
    args = {"project_path": str(project), "question": "What is the archive records policy?"}
    first = call_docs_tool_payload("get_docs_context", args, service)
    assert first.get("sources"), first
    assert any("original timestamp" in row["snippet"] for row in first["sources"])
    assert all(row["snippet"] in text for row in first["sources"])
    assert first == call_docs_tool_payload("get_docs_context", {**args, "portion": 1}, service)
    more = first["more_context"]
    assert more["next_portion"] is None and more["remaining_rows"] == 0
    token = more["continuation_token"]
    assert len(token) == 64
    source_uri = first["sources"][0]["source_uri"]
    consumed = json.loads(read_docs_resource(source_uri, service)["text"])
    assert consumed == {"status": "complete", "reason_code": "end_of_source"}
    exhausted = call_docs_tool_payload("get_docs_context", {
        **args, "portion": 2**31, "continuation_token": token}, service)
    assert not exhausted.get("error"), exhausted
    assert not exhausted.get("sources")
    assert exhausted["more_context"]["next_portion"] is None
    assert json.loads(read_docs_resource(source_uri, service)["text"]) == {
        "status": "source_unavailable", "reason_code": "unknown_or_expired_reference"}
    changed_query = call_docs_tool_payload("get_docs_context", {
        **args, "question": "Where are archive records stored?", "portion": 2,
        "continuation_token": token}, service)
    assert changed_query["error"]["reason_code"] == "stale_context_continuation"
    changed_scope = call_docs_tool_payload("get_docs_context", {
        **args, "scope": "all", "portion": 2, "continuation_token": token}, service)
    assert changed_scope["error"]["reason_code"] == "stale_context_continuation"
    focused_args = {**args, "source_path": "docs/archive.md"}
    focused = call_docs_tool_payload("get_docs_context", focused_args, service)
    assert focused.get("sources"), focused
    assert all(row["path_or_url"] == "docs/archive.md" and row["snippet"] in text
               for row in focused["sources"])
    assert any("original timestamp" in row["snippet"] and "west region" in row["snippet"]
               for row in focused["sources"])
    from docmancer.docs.application.standalone_text_view import render_standalone_text
    from docmancer.docs.application.projection_tokenizer import projection_token_count
    assert projection_token_count(render_standalone_text(focused).text.encode("utf-8")) <= 2400
    changed_focus = call_docs_tool_payload("get_docs_context", {
        **focused_args, "portion": 2, "continuation_token": token}, service)
    assert changed_focus["error"]["reason_code"] == "stale_context_continuation"
    missing = call_docs_tool_payload("get_docs_context", {**args, "source_path": "docs/absent.md"}, service)
    assert not missing.get("sources"), missing
    monkeypatch.setenv("DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS", "18000")
    changed_budget = call_docs_tool_payload("get_docs_context", {
        **args, "portion": 2, "continuation_token": token}, service)
    assert changed_budget["error"]["reason_code"] == "stale_context_continuation"
    monkeypatch.delenv("DOCATLAS_EXPERIMENT_DELIVERY_MAX_TOKENS")
    (project / "docs/archive.md").write_text(text + "Archive records also retain a checksum.\n")
    stale_focus = call_docs_tool_payload("get_docs_context", focused_args, service)
    assert not stale_focus.get("sources"), stale_focus
    index_project(service, config, project)
    changed_source = call_docs_tool_payload("get_docs_context", {
        **args, "portion": 2, "continuation_token": token}, service)
    assert changed_source["error"]["reason_code"] == "stale_context_continuation"


def test_context_portion_replay_keeps_spent_reads_spent_and_issues_new_sources(tmp_path, monkeypatch):
    """One prepare, three context calls and six public resource reads; no mocks."""
    from docmancer.docs.application.source_continuation import SourceContinuationReader

    project = tmp_path / "project"
    facts = (
        "Archive records preserve timestamp lineage.",
        "Archive records retain checksum validation.",
        "Archive records require owner approval.",
    )
    documents = {f"docs/archive-{name}.md": f"# Archive policy {name}\n\n{fact}\n"
                 for name, fact in zip(("alpha", "beta", "gamma"), facts, strict=True)}
    write_project(project, documents)
    # A smaller host reference capacity exercises real paging and eviction;
    # the production reader, source authorization and selection still execute.
    monkeypatch.setattr(SourceContinuationReader, "max_references", 2)
    with isolated_service(tmp_path / "state") as (service, config):
        monkeypatch.setenv("DOCATLAS_MCP_TEXT_FALLBACK", "1")
        monkeypatch.setenv("DOCATLAS_MCP_COMPACT_TEXT", "1")
        # Keep this source-reader scenario independent of the pruning recipe;
        # the existing default-mode case above covers exhausted-page replay.
        monkeypatch.setenv("DOCATLAS_EXPERIMENT_POOL_PRUNE", "off")
        inventory = index_project(service, config, project)
        assert not inventory["excluded_or_failed_paths"]
        args = {"project_path": str(project), "question": "Archive records policy"}
        first = call_docs_tool_payload("get_docs_context", args, service)
        assert len(first.get("sources", [])) == 2, first
        more = first["more_context"]
        assert more["next_portion"] == 2 and more["remaining_rows"] == 1
        old_uris = [row["source_uri"] for row in first["sources"]]
        for uri in old_uris:
            assert json.loads(read_docs_resource(uri, service)["text"]) == {
                "status": "complete", "reason_code": "end_of_source"}

        second = call_docs_tool_payload("get_docs_context", {
            **args, "portion": 2, "continuation_token": more["continuation_token"]}, service)
        assert len(second.get("sources", [])) == 1, second
        assert second["more_context"]["next_portion"] is None
        delivered = [row["snippet"] for row in [*first["sources"], *second["sources"]]]
        assert all(any(fact in text for text in delivered) for fact in facts)
        assert all(any(text in original for original in documents.values()) for text in delivered)
        for uri in old_uris:
            assert json.loads(read_docs_resource(uri, service)["text"]) == {
                "status": "source_unavailable", "reason_code": "unknown_or_expired_reference"}
        new_uri = second["sources"][0]["source_uri"]
        assert new_uri not in old_uris
        assert json.loads(read_docs_resource(new_uri, service)["text"]) == {
            "status": "complete", "reason_code": "end_of_source"}

        exhausted = call_docs_tool_payload("get_docs_context", {
            **args, "portion": 3, "continuation_token": more["continuation_token"]}, service)
        assert not exhausted.get("error") and not exhausted.get("sources"), exhausted
        assert json.loads(read_docs_resource(new_uri, service)["text"]) == {
            "status": "source_unavailable", "reason_code": "unknown_or_expired_reference"}


def test_context_portions_reject_invalid_and_unsupported_requests(prepared_project, monkeypatch):
    service, _config, project, _text = prepared_project
    args = {"project_path": str(project), "question": "What is the archive records policy?"}
    first = call_docs_tool_payload("get_docs_context", args, service)
    token = first["more_context"]["continuation_token"]
    for invalid in (0, True, "2"):
        result = call_docs_tool_payload("get_docs_context", {**args, "portion": invalid}, service)
        assert result.get("error") and not result.get("sources"), result
    missing_token = call_docs_tool_payload("get_docs_context", {**args, "portion": 2}, service)
    assert missing_token.get("error") and not missing_token.get("sources"), missing_token
    traversal = call_docs_tool_payload("get_docs_context", {**args, "source_path": "../outside.md"}, service)
    assert traversal["error"]["reason_code"] == "invalid_source_path" and not traversal.get("sources")
    advanced = current_docs_surface({"DOCATLAS_MCP_ADVANCED_TOOLS": "1"})
    patch = call_docs_tool_payload("get_docs_context", {
        **args, "context_format": "patch_context", "portion": 2, "continuation_token": token},
        service, surface=advanced)
    assert patch["error"]["reason_code"] == "portion_docs_only"
    monkeypatch.setenv("DOCATLAS_CONTEXT_COMPRESSION", "minilm-sections-v1")
    compressed = call_docs_tool_payload("get_docs_context", {
        **args, "portion": 2, "continuation_token": token}, service)
    assert compressed["error"]["reason_code"] == "portion_unavailable"
    monkeypatch.delenv("DOCATLAS_CONTEXT_COMPRESSION")
    library = call_docs_tool_payload("get_docs_context", {
        "library": "unprepared-library", "question": args["question"], "portion": 2,
        "continuation_token": token}, service)
    assert library["error"]["reason_code"] == "portion_unavailable"


def test_e5_focused_context_preserves_scope_snapshot_and_read_only_state(tmp_path, monkeypatch):
    """Optional real-model integration; no fake vectors, retrieval or admission.

    Provision the pinned local assets and set DOCATLAS_TEST_E5_MODEL_DIR. This
    covers the hybrid execution boundary, not superiority over lexical search.
    """
    import hashlib
    import os
    from pathlib import Path
    import subprocess
    import sys
    import yaml

    model = os.environ.get("DOCATLAS_TEST_E5_MODEL_DIR")
    if not model:
        pytest.skip("explicit local E5 assets required")
    root = tmp_path / "project"
    docs = {
        "docs/archive.md": "# Archive policy\n\nArchive records preserve the original timestamp.\n",
        "docs/approval.md": "# Archive approval\n\nArchive deletion needs written owner approval.\n",
        "modules/private/docs/archive.md": "# Archive policy\n\nArchive private vault code is COBALT.\n",
    }
    write_project(root, docs)
    catalog_path = root / "docatlas.project-docs.yaml"
    catalog = yaml.safe_load(catalog_path.read_text())
    for entry in catalog["documents"]:
        if entry["path"].startswith("modules/"):
            entry.update(scope="module", module_path="modules/private")
    catalog_path.write_text(yaml.safe_dump(catalog))
    with isolated_service(tmp_path / "state") as (service, config):
        cold = call_docs_tool_payload("get_docs_context", {
            "project_path": str(root), "question": "What is the archive policy?",
            "source_path": "docs/archive.md"}, service._cold)
        assert cold["recommended_next_action"]["requires_confirmation"] and not cold.get("sources"), cold
        assert not Path(config.index.db_path).exists()
        inventory = index_project(service, config, root)
        cache = tmp_path / "e5-cache"
        script = Path(__file__).resolve().parents[1] / "eval/blind_project_context/prepare_e5_cache.py"
        subprocess.run([sys.executable, str(script), "--db", inventory["storage_path"],
                        "--model-dir", model, "--out", str(cache)], check=True)
        monkeypatch.setenv("DOCATLAS_EXPERIMENT_ACQUISITION_E5", "1")
        monkeypatch.setenv("DOCATLAS_EXPERIMENT_E5_MODEL_DIR", model)
        monkeypatch.setenv("DOCATLAS_EXPERIMENT_E5_CACHE", str(cache))
        monkeypatch.setenv("DOCATLAS_CONTEXT_COMPRESSION", "off")
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in [Path(inventory["storage_path"]), *root.rglob("*.md"), *cache.iterdir()]}
        args = {"project_path": str(root), "scope": "project", "question": "What is the archive policy?"}
        first = call_docs_tool_payload("get_docs_context", args, service)
        text = "\n".join(row["snippet"] for row in first.get("sources", []))
        assert "original timestamp" in text and "written owner approval" in text, first
        assert "COBALT" not in json.dumps(first)
        focused = call_docs_tool_payload("get_docs_context", {**args, "source_path": "docs/approval.md"}, service)
        assert focused.get("sources"), focused
        assert all(row["path_or_url"] == "docs/approval.md" and row["snippet"] in docs["docs/approval.md"]
                   for row in focused["sources"])
        hidden = call_docs_tool_payload("get_docs_context", {
            **args, "source_path": "modules/private/docs/archive.md"}, service)
        assert not hidden.get("sources") and "COBALT" not in json.dumps(hidden), hidden
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in before.items())
        (root / "docs/approval.md").write_text("# Archive approval\nChanged without reindexing.\n")
        stale = call_docs_tool_payload("get_docs_context", {**args, "source_path": "docs/approval.md"}, service)
        assert not stale.get("sources"), stale
