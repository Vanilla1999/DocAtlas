"""Public prepare/context/resource guards with real components, no mocks.

Two scenarios: 4 confirmed prepare/sync calls, 13 context calls, <=2 resources,
0 models. Existing optics/scope documents and facts reused unchanged.
Only host environment is selected; no product helper is asserted or replaced.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml
import tiktoken

from docmancer.mcp.docs_server import call_docs_tool_payload, read_docs_resource
from docmancer.docs.application.query_trace import query_trace
from eval.evidence_quality_v2 import runtime
from eval.heuristic_removal.receipts import database, files, integrity, pack, relative_path, sha, snapshots, stable_packet
from tests.test_prepared_retrieval_integration import (
    OPTICS_DOCUMENTS, OPTICS_FACTS, OPTICS_QUESTION, UPDATED_ISSUE,
    UPDATED_OPTICS_FACTS, SCOPE_DOCUMENTS, SHUTTER_QUESTION, MODULE_QUESTION,
    state_root,
)


def context(service, root, question, **extra):
    return call_docs_tool_payload("get_docs_context", {
        "question": question, "project_path": str(root), "scope": "project", **extra}, service)


def facts(payload, root, required):
    for relative, statements in required.items():
        delivered = [row["snippet"] for row in payload.get("sources") or []
                     if relative_path(row["path_or_url"], root) == relative]
        for statement in statements:
            assert any(statement in text for text in delivered), (relative, statement, delivered)


def read_source(service, row, root, documents):
    """At most one resource per supplied row, no continuation loop."""
    assert row.get("source_uri"), "public source capability missing"
    response = read_docs_resource(row["source_uri"], service)
    assert response is not None
    payload = json.loads(response["text"])
    if payload.get("status") == "complete" and "snippet" not in payload:
        assert payload.get("reason_code") == "end_of_source"
        return
    relative = relative_path(payload["path"], root)
    text = documents[relative]
    assert payload["content_sha256"] == "sha256:" + sha(text.encode())
    assert payload["project_identity"] == row["project_identity"]
    start, end = payload["line_start"], payload["line_end"]
    assert type(start) is int and type(end) is int and 1 <= start <= end <= len(text.splitlines())
    assert payload["snippet"] == "\n".join(text.splitlines()[start - 1:end])


def test_public_removal_lifecycle_partial_source_integrity_trace_and_read_only(
    tmp_path, monkeypatch, state_root, record_property,
):
    """2 prepare/sync, 7 contexts (off/on/off, partial, stale, fresh, invalid grant), <=2 resources."""
    root = (tmp_path / "project").resolve()
    runtime.write_project(root, OPTICS_DOCUMENTS)
    with runtime.isolated_service(state_root) as (service, config), monkeypatch.context() as env:
        env.delenv("DOCATLAS_EXPERIMENT_HEURISTIC_REMOVAL", raising=False)
        env.delenv("DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS", raising=False)
        inventory = runtime.index_project(service, config, root)
        snapshots(inventory, root, OPTICS_DOCUMENTS)
        before, initial_files = database(inventory["storage_path"]), files(root)
        packets = []
        for trace in (False, True, False):
            with query_trace(trace):
                payload = context(service, root, OPTICS_QUESTION)
            assert not integrity(payload, root, OPTICS_DOCUMENTS)["errors"]
            facts(payload, root, OPTICS_FACTS)
            packed = pack(payload, tiktoken.get_encoding("o200k_base"), 12000)
            facts(packed, root, OPTICS_FACTS)
            assert packed["tokens"] <= 12000
            packets.append(payload)
        assert stable_packet(packets[0]) == stable_packet(packets[1]) == stable_packet(packets[2])
        record_property("trace_off_on_off_public_context_calls", [1, 1, 1])
        old_row = next(row for row in packets[0]["sources"]
                       if relative_path(row["path_or_url"], root) == "docs/issue.md")
        read_source(service, old_row, root, OPTICS_DOCUMENTS)
        partial = context(service, root,
                          "How must lenses be packed for an observation trip, and what is the helicopter refuelling schedule?")
        assert not integrity(partial, root, OPTICS_DOCUMENTS)["errors"]
        facts(partial, root, {"docs/packing.md": OPTICS_FACTS["docs/packing.md"]})
        assert partial.get("answer_supported") is False and partial.get("answer_available") is False
        assert partial.get("edit_ready") is False
        lookup = context(service, root, "Explain the observatory's night-travel checklist.",
                         lookup_queries=[OPTICS_QUESTION])
        assert not integrity(lookup, root, OPTICS_DOCUMENTS)["errors"]
        facts(lookup, root, OPTICS_FACTS)
        assert lookup.get("answer_supported") is False and lookup.get("edit_ready") is False
        assert not lookup.get("covered_query_ids")
        assert database(inventory["storage_path"]) == before and files(root) == initial_files
        (root / "docs/issue.md").write_bytes(UPDATED_ISSUE.encode())
        edited_files = files(root)
        stale = context(service, root, OPTICS_QUESTION)
        assert not stale.get("sources") and stale.get("context_available") is False
        assert stale.get("requires_confirmation") is True
        stale_resource = json.loads(read_docs_resource(old_row["source_uri"], service)["text"])
        assert stale_resource.get("status") in {"source_changed", "source_unavailable"}
        assert "snippet" not in stale_resource
        assert database(inventory["storage_path"]) == before and files(root) == edited_files
        synced = runtime.index_project(service, config, root)
        assert synced["generation_id"] != inventory["generation_id"]
        updated = {**OPTICS_DOCUMENTS, "docs/issue.md": UPDATED_ISSUE}
        snapshots(synced, root, updated)
        synced_state = database(synced["storage_path"])
        fresh = context(service, root, OPTICS_QUESTION)
        assert not integrity(fresh, root, updated)["errors"]
        facts(fresh, root, UPDATED_OPTICS_FACTS)
        assert "collection custodian" not in "\n".join(row["snippet"] for row in fresh["sources"])
        # An unauthorized mutation field must be rejected, never treated as a grant.
        rejected = context(service, root, OPTICS_QUESTION, mutation_intent={"operation": "delete", "confirm": True})
        assert rejected.get("status") == "failed" and not rejected.get("sources")
        assert rejected.get("edit_ready") is not True
        assert database(synced["storage_path"]) == synced_state and files(root) == edited_files


def test_public_removal_explicit_scope_version_and_foreign_locator(
    tmp_path, monkeypatch, state_root,
):
    """2 prepare, 6 contexts; foreign project also indexed, so locator isolation is real."""
    root, foreign = (tmp_path / "project").resolve(), (tmp_path / "foreign").resolve()
    runtime.write_project(root, SCOPE_DOCUMENTS)
    catalog = root / "docatlas.project-docs.yaml"
    data = yaml.safe_load(catalog.read_bytes())
    for entry in data["documents"]:
        if entry["path"] == "modules/imaging/guide.md":
            entry.update(scope="module", module_path="modules/imaging")
    catalog.write_text(yaml.safe_dump(data, sort_keys=False))
    foreign_documents = {"docs/foreign.md": "# Foreign vault\n\n`FOREIGN_VAULT_PIN` unlocks the foreign vault.\n"}
    runtime.write_project(foreign, foreign_documents)
    with runtime.isolated_service(state_root) as (service, config), monkeypatch.context() as env:
        env.delenv("DOCATLAS_EXPERIMENT_HEURISTIC_REMOVAL", raising=False)
        env.delenv("DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS", raising=False)
        runtime.index_project(service, config, foreign)
        inventory = runtime.index_project(service, config, root)
        # A generation contains both explicitly prepared project roots. Check
        # all pinned bytes here; public contexts below still enforce root scope.
        snapshots(inventory, root.parent, {
            **{"project/" + name: text for name, text in SCOPE_DOCUMENTS.items()},
            **{"foreign/" + name: text for name, text in foreign_documents.items()},
        })
        before, root_files, foreign_files = database(inventory["storage_path"]), files(root), files(foreign)
        project = context(service, root, SHUTTER_QUESTION)
        assert not integrity(project, root, {"docs/camera.md": SCOPE_DOCUMENTS["docs/camera.md"]})["errors"]
        facts(project, root, {"docs/camera.md": ("`SHUTTER_DELAY` sets shutter delay to 230 milliseconds.",)})
        module = context(service, root, MODULE_QUESTION, scope="module", module_path="modules/imaging")
        assert not integrity(module, root, SCOPE_DOCUMENTS, ("modules/imaging/guide.md",))["errors"]
        assert {row["scope"] for row in module.get("sources") or []} == {"module"}
        facts(module, root, {"modules/imaging/guide.md": ("`SENSOR_GAIN` controls sensor gain for flat-field calibration.",)})
        project_only = context(service, root, MODULE_QUESTION)
        assert not integrity(project_only, root, {"docs/camera.md": SCOPE_DOCUMENTS["docs/camera.md"]})["errors"]
        missing_module = context(service, root, MODULE_QUESTION, scope="module", module_path="modules/absent")
        exact = context(service, root, SHUTTER_QUESTION, version="99.0.0")
        locator = context(service, root, f"In {foreign / 'docs/foreign.md'}, explain `FOREIGN_VAULT_PIN`.")
        for payload in (missing_module, exact, locator):
            assert not payload.get("sources"), payload
            assert payload.get("answer_available") is not True and payload.get("edit_ready") is not True
        assert database(inventory["storage_path"]) == before
        assert files(root) == root_files and files(foreign) == foreign_files


def test_public_library_native_context_isolates_versions(tmp_path, monkeypatch):
    """Real per-library SQLite indexes and public MCP read; no transport or retrieval mocks."""
    from tests._shared_test_docs_service import _service_with_real_agent
    from tests.docs.test_dependency_version_transition import _seed, PACKAGE, QUESTION

    service = _service_with_real_agent(tmp_path, monkeypatch)
    service.config.retrieval.default_mode = "lexical"
    first = _seed(service, "1.0.0", "FIRST_ONLY")
    second = _seed(service, "2.0.0", "SECOND_ONLY")
    paths = [service._index_config_for(row).index.db_path for row in (first, second)]
    before = [database(path) for path in paths]
    for version, marker, other in [("1.0.0", "FIRST_ONLY", "SECOND_ONLY"),
                                    ("2.0.0", "SECOND_ONLY", "FIRST_ONLY")]:
        with query_trace(True):
            payload = call_docs_tool_payload("get_docs_context", {
                "question": QUESTION, "library": PACKAGE, "version": version,
            }, service)
        assert payload.get("context_available") is True, payload
        assert payload.get("answer_supported") is False and payload.get("edit_ready") is False
        rows = payload.get("sources") or []
        expected = f"NavigationRegistry is a route registry using {marker} dispatch in version {version}."
        assert any(expected in row["snippet"] for row in rows), payload
        original = f"# NavigationRegistry\n\n{expected}\n"
        for row in rows:
            assert row["snippet"] in original
            assert other not in row["snippet"]
            assert row["path_or_url"] == (
                f"https://pub.dev/documentation/{PACKAGE}/{version}/nav_kit/NavigationRegistry-class.html")
            assert row["version_binding"] == "exact_snapshot"
    assert [database(path) for path in paths] == before
