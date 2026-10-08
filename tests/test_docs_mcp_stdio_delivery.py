"""Delivery validation and isolation; real retrieval runs in installed smoke."""
import hashlib
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.docs_mcp_stdio_smoke import (
    bootstrap_library_fixture, bootstrap_ready_fixture, evidence_sizes,
    fixture_database_state, initialize_fixture_members, isolated_environment, payload, text_payload,
    natural_protocol_documents, LARGE_PHASES, trace_project_delivery,
    cold_fixture_members, indexed_delivery, repeat_preparation, read_only_delivery,
    validate_blocked_preparation, validate_patch_payload,
)
from docmancer.docs.application.action_packet import build_action_packet, refresh_action_packet_estimate
from docmancer.mcp.docs_server import current_docs_surface


ADVANCED_SURFACE = current_docs_surface({"DOCATLAS_MCP_ADVANCED_TOOLS": "1"})


@pytest.fixture
def library_service(tmp_path, monkeypatch):
    from docmancer.core.config import DocmancerConfig
    from docmancer.docs.service import LibraryDocsService

    root = tmp_path / "library-test"
    root.mkdir()
    for key, value in isolated_environment(root).items():
        monkeypatch.setenv(key, value)
    project = root / "project"
    project.mkdir()
    index_root = root / "owned-home" / "docs-indexes"
    fixtures = bootstrap_library_fixture(project, index_root)
    config = DocmancerConfig(index={"db_path": str(project / ".docatlas" / "docatlas.db")})
    service = LibraryDocsService(config=config, library_index_root=index_root)
    return service, project, fixtures


def _library_arguments(version="1.0.0", **extra):
    command = "fixture-open" if version == "1.0.0" else "fixture-connect"
    return {"question": f"What is the `{command}` transport command?",
            "library": "local-transport-fixture", "version": version,
            "context_format": "patch_context", **extra}


def _library_result(service, version="1.0.0"):
    args = _library_arguments(version)
    return service.get_docs(args["library"], topic=args["question"], version=version)


@pytest.mark.parametrize("version", ["1.0.0", "2.0.0"])
def test_real_library_adapter_preserves_indexed_snapshot_lineage(library_service, version):
    service, project, fixtures = library_service
    result = _library_result(service, version)
    rows = service.unified_context._library_context_pack(result)
    assert rows and all(row["resolved_version"] == version for row in rows)
    original = (project / "library-fixtures" / version / "reference.md").read_bytes()
    text = original.decode("utf-8")
    for row in rows:
        assert row["source"] == fixtures[version]["source"]
        assert row["generation_id"] == fixtures[version]["generation_id"]
        assert row["source_content_hash"] == hashlib.sha256(original).hexdigest()
        assert row["display_text"] == text[row["char_start"]:row["char_end"]]
        assert row["display_text"].encode() == original[row["byte_start"]:row["byte_end"]]
        assert row["display_content_hash"] == hashlib.sha256(row["display_text"].encode()).hexdigest()
        assert row["docs_snapshot_exact"] is True
        assert row["parent_logical_id"] != row["source"]
        assert row["stable_chunk_id"] == result.results[0].metadata["stable_chunk_id"]


def test_real_library_public_graph_preserves_versions_and_source_spans(library_service):
    from docmancer.mcp.docs_server import call_docs_tool_payload
    from docmancer.docs.application import _library_docs_service_part03 as producer

    assert Path(producer.__file__).resolve().is_relative_to(Path(__file__).resolve().parents[1])
    service, project, fixtures = library_service
    before = {version: fixture_database_state(Path(row["database"])) for version, row in fixtures.items()}
    for version, command in (("1.0.0", "fixture-open"), ("2.0.0", "fixture-connect")):
        response = call_docs_tool_payload("get_docs_context", _library_arguments(version), service, surface=ADVANCED_SURFACE)
        validate_patch_payload(response, completeness="complete")
        assert response["result"] == "data" and response["edit_ready"] is False
        assert {row["path"] for row in response["sources"]} == {fixtures[version]["source"]}
        assert {row["version_binding"] for row in response["sources"]} == {"exact_snapshot"}
        assert any(row["requirement_id"] == f"exact_version:{version}" for row in response["assignments"])
        assert command in "".join(row["text"] for row in response["sources"])
        other = "fixture-connect" if version == "1.0.0" else "fixture-open"
        assert other not in "".join(row["text"] for row in response["sources"])
        assert evidence_sizes(response, project)["unique_nonoverlap_utf8_bytes"] > 0
    assert {version: fixture_database_state(Path(row["database"])) for version, row in fixtures.items()} == before
    missing = call_docs_tool_payload("get_docs_context", _library_arguments("99.0.0"), service, surface=ADVANCED_SURFACE)
    validate_patch_payload(missing, completeness="unavailable")
    assert not missing.get("sources")


def test_real_library_omitted_and_null_format_keep_docs_delivery(library_service):
    from docmancer.mcp.docs_server import call_docs_tool_payload

    service, project, _fixtures = library_service
    arguments = _library_arguments()
    arguments.pop("context_format")
    omitted = call_docs_tool_payload("get_docs_context", arguments, service)
    rejected = call_docs_tool_payload("get_docs_context", {**arguments, "context_format": None}, service)
    assert rejected["error"]["reason_code"] == "validation_error"
    null = call_docs_tool_payload("get_docs_context", {**arguments, "context_format": None}, service, surface=ADVANCED_SURFACE)
    assert omitted == null
    assert omitted.get("kind") == "docs_answer" and omitted.get("status") == "ok", omitted
    assert not omitted.get("edit_ready")
    assert evidence_sizes(omitted, project)["unique_nonoverlap_utf8_bytes"] > 0


def test_real_library_cleaning_keeps_original_unicode_bytes_and_carrier_is_overwritten(library_service):
    from docmancer.core.models import Document
    from docmancer.core.sqlite_store import SQLiteStore
    from docmancer.mcp.docs_server import call_docs_tool_payload

    service, project, fixtures = library_service
    result = _library_result(service)
    chunk = result.results[0]
    metadata = {key: value for key, value in chunk.metadata.items() if key != "_indexed_source"}
    # Real authored file/index, including characters the presentation cleaner removes.
    text = '# Transport\n\n<a id="open"></a> 🧭 The `fixture-open` transport command preserves café records.  \n'
    path = project / "library-fixtures" / "1.0.0" / "reference.md"
    path.write_text(text, encoding="utf-8")
    metadata["_indexed_source"] = {"display_text": "forged", "verified": True}
    SQLiteStore(fixtures["1.0.0"]["database"]).add_documents([
        Document(source=path.as_uri(), content=text, metadata=metadata)])
    result = _library_result(service)
    rows = service.unified_context._library_context_pack(result)
    assert rows and any(row["display_text"] != row["content"] for row in rows)
    for row in rows:
        assert text[row["char_start"]:row["char_end"]] == row["display_text"]
        assert row["display_content_hash"] == hashlib.sha256(row["display_text"].encode()).hexdigest()
        assert row["source_content_hash"] == hashlib.sha256(text.encode()).hexdigest()
        assert "verified" not in result.results[0].metadata["_indexed_source"]
    response = call_docs_tool_payload("get_docs_context", _library_arguments(), service, surface=ADVANCED_SURFACE)
    validate_patch_payload(response, completeness="complete")
    assert evidence_sizes(response, project)["unique_nonoverlap_utf8_bytes"] == len(text.encode())


@pytest.mark.parametrize("mutation", ["parent", "hash", "span", "bool_span", "line_span", "source_hash",
    "source", "child", "version", "snapshot_bool", "missing", "derived", "text", "carrier"])
def test_library_consumer_rejects_inconsistent_or_missing_lineage(library_service, mutation):
    service, _project, _fixtures = library_service
    result = deepcopy(_library_result(service))
    assert service.unified_context._library_context_pack(result)
    chunk = result.results[0]
    metadata = chunk.metadata
    if mutation == "parent":
        metadata.pop("parent_logical_id")
    elif mutation == "hash":
        metadata["content_hash"] = "0" * 64
    elif mutation == "span":
        metadata["char_span"][1] += 1
    elif mutation == "bool_span":
        metadata["char_span"][0] = False
    elif mutation == "line_span":
        metadata["line_span"][1] += 1
    elif mutation == "source_hash":
        metadata["source_content_hash"] = "0" * 64
    elif mutation == "source":
        result.results[0] = replace(chunk, source=chunk.source.replace("1.0.0", "2.0.0"))
    elif mutation == "child":
        metadata["stable_chunk_id"] += "-other"
    elif mutation == "version":
        metadata["resolved_version"] = "2.0.0"
    elif mutation == "snapshot_bool":
        metadata["docs_snapshot_exact"] = "true"
    elif mutation == "missing":
        metadata.pop("_indexed_source")
    elif mutation == "derived":
        metadata["source_excerpt"] = True
    elif mutation == "text":
        result.results[0] = replace(chunk, content=chunk.content + " changed")
    else:
        metadata["_indexed_source"] = {"verified": True, "authority": "official"}
    assert service.unified_context._library_context_pack(result) == []


def test_library_adapter_uses_child_identity_not_selected_id_position(library_service):
    from docmancer.core.models import Document
    from docmancer.core.sqlite_store import SQLiteStore

    service, project, fixtures = library_service
    first = _library_result(service).results[0]
    second = project / "library-fixtures" / "1.0.0" / "retries.md"
    second.write_text("# Retry handling\n\nThe `fixture-open` transport command retains its request identifier when a connection drops.\n")
    metadata = {**first.metadata, "canonical_url": second.as_uri(), "source_origin_url": second.as_uri()}
    SQLiteStore(fixtures["1.0.0"]["database"]).add_documents([
        Document(source=second.as_uri(), content=second.read_text(), metadata=metadata)])
    result = _library_result(service)
    assert len(result.results) == 2
    result = replace(result, results=list(reversed(result.results)),
                     selected_evidence_ids=["unrelated-selection-id"] * len(result.results))
    rows = service.unified_context._library_context_pack(result)
    assert [row["stable_chunk_id"] for row in rows] == [chunk.metadata["stable_chunk_id"] for chunk in result.results]
    assert all(row["stable_chunk_id"] != "unrelated-selection-id" for row in rows)


@pytest.mark.parametrize("attack", ["missing_parent", "wrong_hash", "wrong_span", "ambiguous", "duplicate",
                                   "duplicate_parent", "wrong_version", "wrong_root"])
def test_real_library_producer_rejects_corrupt_lineage_and_existing_source_guards(library_service, monkeypatch, attack):
    service, project, _fixtures = library_service
    original = service.agent_gateway.query_library

    def corrupt(*args, **kwargs):
        result = original(*args, **kwargs)  # Actual SQLite retrieval, never invented source text.
        assert result.chunks
        chunk = result.chunks[0]
        if attack == "missing_parent":
            chunk.metadata.pop("parent_logical_id")
        elif attack == "wrong_hash":
            chunk.metadata["content_hash"] = "f" * 64
        elif attack == "wrong_span":
            chunk.metadata["char_span"][1] += 7
        elif attack in {"ambiguous", "duplicate", "duplicate_parent"}:
            altered = chunk.model_copy(deep=True)
            if attack == "ambiguous":
                altered.text += " conflicting bytes"
            elif attack == "duplicate_parent":
                altered.metadata["parent_logical_id"] += "-conflicting"
            result.chunks.append(altered)
        elif attack == "wrong_version":
            chunk.metadata["version"] = "2.0.0"
        else:
            chunk.metadata["docset_root"] = (project / "library-fixtures" / "2.0.0").as_uri()
        chunk.metadata["_indexed_source"] = {"verified": True, "display_text": chunk.text}
        return result

    monkeypatch.setattr(service.agent_gateway, "query_library", corrupt)
    result = _library_result(service)
    assert not any(chunk.metadata.get("_indexed_source") for chunk in result.results)
    assert service.unified_context._library_context_pack(result) == []
    if attack in {"wrong_version", "wrong_root"}:
        assert result.results == []


@pytest.mark.parametrize("duplicate", ["identical", "conflicting_parent", "invalid_parent"])
def test_library_consumer_rejects_all_repeated_child_identities(library_service, duplicate):
    service, _project, _fixtures = library_service
    result = _library_result(service)
    assert len(result.results) == 1
    assert len(service.unified_context._library_context_pack(result)) == 1
    competing = deepcopy(result.results[0])
    if duplicate == "conflicting_parent":
        competing.metadata["parent_logical_id"] += "-conflicting"
        competing.metadata["_indexed_source"]["parent_logical_id"] = competing.metadata["parent_logical_id"]
        # Each row passes its own consistency check. Only the cross-row
        # repeated identity makes the pair inadmissible.
        assert len(service.unified_context._library_context_pack(replace(result, results=[competing]))) == 1
    elif duplicate == "invalid_parent":
        competing.metadata.pop("parent_logical_id")
    for chunks in ([result.results[0], competing], [competing, result.results[0]]):
        assert service.unified_context._library_context_pack(replace(result, results=chunks)) == []


@pytest.mark.parametrize("derived", [False, True])
def test_real_library_postprocessing_cannot_rebind_a_transformed_or_derived_child(library_service, monkeypatch, derived):
    from docmancer.docs.application import library_docs_service as producer

    service, _project, _fixtures = library_service
    postprocess = producer._postprocess_library_chunks

    def transform(chunks, query):
        rows, diagnostics = postprocess(chunks, query)
        rows[0] = rows[0].model_copy(update={"text": rows[0].text + " transformed"})
        if derived:
            rows[0].metadata.update(source_excerpt=True,
                                    stable_chunk_id=rows[0].metadata["stable_chunk_id"] + ":excerpt:changed")
        return rows, diagnostics

    monkeypatch.setattr(producer, "_postprocess_library_chunks", transform)
    result = _library_result(service)
    assert result.results and all("_indexed_source" not in chunk.metadata for chunk in result.results)
    assert service.unified_context._library_context_pack(result) == []


def test_acquisition_observer_uses_real_small_public_route_without_changing_results(library_service, monkeypatch):
    from docmancer.mcp.docs_server import call_docs_tool_payload

    service, project, _fixtures = library_service
    # The trace and both direct dispatches must use the same explicit startup mode.
    monkeypatch.setenv("DOCATLAS_MCP_ADVANCED_TOOLS", "1")
    (project / "README.md").write_text("# Server\n\nStart the server with `doc-atlas mcp docs-serve`.\n")
    initialize_fixture_members(project)
    bootstrap_ready_fixture(project)
    arguments = {"question": "What is `doc-atlas mcp docs-serve`?", "project_path": str(project),
                 "context_format": "patch_context"}
    before = call_docs_tool_payload("get_docs_context", arguments, service)
    validate_patch_payload(before)
    report = trace_project_delivery(service, arguments, project)
    after = call_docs_tool_payload("get_docs_context", arguments, service)
    assert before == after
    assert report["returned"] == evidence_sizes(before, project)
    assert report["acquired"]["unique_nonoverlap_utf8_bytes"] >= report["returned"]["unique_nonoverlap_utf8_bytes"] > 0
    assert report["qualified"]["unique_nonoverlap_utf8_bytes"] > 0
    assert report["routes"] and all(row["budget"] == 4000 for row in report["routes"])
    assert all(row["query"] == arguments["question"] for row in report["routes"])
    assert report["tool_wire_utf8_bytes"] is None


def test_patch_validator_preserves_large_utf8_evidence_and_checks_hash():
    text = "必要な unique evidence\n" * 3000
    value = build_action_packet(question="Inspect evidence", context_pack=[{
        "path": "docs/evidence.md", "content": text, "display_text": text,
        "source_class": "project_doc", "doc_scope": "project", "authority": "canonical",
        "stable_chunk_id": "unique-window", "parent_logical_id": "unique-parent",
        "char_start": 13, "char_end": 13 + len(text),
        "display_content_hash": hashlib.sha256(text.encode()).hexdigest(),
    }], required_target_paths=["missing.py"])
    value["kind"] = "patch_context"
    refresh_action_packet_estimate(value)
    validate_patch_payload(value, completeness="partial")
    assert len(text.encode()) > 32768
    value["sources"][0]["content_sha256"] = "0" * 64
    refresh_action_packet_estimate(value)
    with pytest.raises(AssertionError):
        validate_patch_payload(value)


def test_fixture_environment_does_not_inherit_configuration_or_credentials(tmp_path, monkeypatch):
    for key in ("PYTHONPATH", "OPENCODE_CONFIG", "OPENAI_API_KEY", "DOCATLAS_CONFIG"):
        monkeypatch.setenv(key, "foreign")
    env = isolated_environment(tmp_path)
    assert all(key not in env for key in ("PYTHONPATH", "OPENCODE_CONFIG", "OPENAI_API_KEY", "DOCATLAS_CONFIG"))
    assert env["DOCATLAS_HOME"] == str(tmp_path / "docatlas-home")
    assert env["HOME"] == env["USERPROFILE"]
    assert os.environ["OPENAI_API_KEY"] == "foreign"


def test_strict_validator_accepts_failure_and_rejects_unknown_authority():
    value = {"schema_version": 4, "kind": "patch_context", "result": "failure",
             "completeness": "unavailable", "edit_ready": False,
             "missing": ["no_evidence"], "estimated_tokens": 1}
    refresh_action_packet_estimate(value)
    validate_patch_payload(value, completeness="unavailable")
    value["consent"] = True
    refresh_action_packet_estimate(value)
    with pytest.raises(AssertionError, match="Additional properties"):
        validate_patch_payload(value)
    terminal = {"status": "failed", "retryable": False}
    result = SimpleNamespace(isError=True, structuredContent=terminal, content=[])
    with pytest.raises(AssertionError):
        payload(result)
    assert payload(result, allow_error=True) == terminal
    result.structuredContent = None
    result.content = [SimpleNamespace(text='{"status":"failed","retryable":false}')]
    assert text_payload(result, allow_error=True) == terminal
    blocked = {"status": "blocked", "reason_code": "unsafe_sqlite_path_mutation",
               "retryable": False, "mutation_performed": False}
    validate_blocked_preparation(blocked)
    with pytest.raises(AssertionError):
        validate_blocked_preparation({**blocked, "mutation_performed": True})


def test_explicit_fixture_grant_binds_actual_catalog_members_and_empty_storage(tmp_path):
    from docmancer.docs.application.project_docs_member_transaction import MemberTransaction

    project = tmp_path / "fixture"
    project.mkdir()
    (project / "README.md").write_text("# Fixture\n\nDocumentation evidence.\n")
    store, mutation = initialize_fixture_members(project)
    parsed = MemberTransaction.parse(mutation, operation="sync_project_docs")
    assert parsed.storage_path == str(project / ".docatlas" / "docatlas.db")
    assert parsed.expected_generation_id is None
    assert {document.path for document in parsed.documents} == {"README.md", *natural_protocol_documents()}
    assert all(document.catalog_entry_hash.startswith("sha256:") for document in parsed.documents)
    assert all((project / path).read_text() == text for path, text in natural_protocol_documents().items())
    for document in parsed.documents:
        assert document.content_sha256 == hashlib.sha256((project / document.path).read_bytes()).hexdigest()
    state = fixture_database_state(store.db_path)
    assert all(not rows for rows in state.values())


@pytest.mark.parametrize("text_only", [False, True])
def test_cold_smoke_helpers_prepare_retrieve_and_restart_real_source_stdio(tmp_path, text_only):
    import asyncio
    import sys
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text(
        "# Docs MCP server\n\nThe command that starts the Docs MCP server is `doc-atlas mcp docs-serve`.\n")
    env = isolated_environment(tmp_path)
    # Source test only. Installed smoke forbids PYTHONPATH and verifies imports.
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    if text_only:
        env["DOCATLAS_MCP_TEXT_FALLBACK"] = "1"
    database = Path(env["DOCATLAS_HOME"]) / "mcp-members" / "members.db"
    params = StdioServerParameters(command=sys.executable,
                                  args=["-m", "docmancer.cli", "mcp", "docs-serve"], env=env, cwd=str(tmp_path))

    async def run():
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                await read_only_delivery(session, project, text_only=text_only)
                assert not database.parent.exists()
                prepared = await indexed_delivery(session, project, database, text_only=text_only)
        # Library preload shares the actual registry but does not create or
        # adopt the member database, and is not counted as cold acceptance.
        state = fixture_database_state(database)
        bootstrap_library_fixture(project, database.parent / "docs-indexes", database=database)
        assert fixture_database_state(database) == state
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                await repeat_preparation(session, project, database, *prepared, text_only=text_only)
        assert not (project / ".docatlas" / "docatlas.db").exists()

    asyncio.run(run())


def test_cold_fixture_grant_never_constructs_selected_storage(tmp_path):
    from docmancer.docs.application.project_docs_member_transaction import MemberTransaction

    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Fixture\n\nSource-bound documentation.\n")
    database = tmp_path / "private-app-home" / "mcp-members" / "members.db"
    mutation = cold_fixture_members(project, database)
    parsed = MemberTransaction.parse(mutation, operation="sync_project_docs")
    assert parsed.storage_path == str(database) and parsed.expected_generation_id is None
    assert len(parsed.documents) == 8
    assert not database.parent.parent.exists()
    assert not (project / "docatlas.yaml").exists()
    assert all(row.content_sha256 == hashlib.sha256((project / row.path).read_bytes()).hexdigest()
               for row in parsed.documents)


def test_ready_fixture_bootstrap_uses_real_store_and_local_catalog_binding(tmp_path):
    project = tmp_path / "ready"
    project.mkdir()
    (project / "README.md").write_text("# Docs\n\nStart with `doc-atlas mcp docs-serve`.\n")
    store, _mutation = initialize_fixture_members(project)
    bootstrap = bootstrap_ready_fixture(project)
    assert bootstrap["generation_id"].startswith("gen-")
    assert set(bootstrap["files"]) == {"README.md", *natural_protocol_documents(), "packages/alpha/README.md", "packages/beta/README.md"}
    assert bootstrap["files"]["packages/alpha/README.md"]["scope"] == "module"
    with store._connect() as conn:
        assert store._active_generation_id(conn) == bootstrap["generation_id"]
        assert conn.execute("SELECT count(*) FROM generation_sources WHERE generation_id=?",
                            (bootstrap["generation_id"],)).fetchone()[0] == 8
        assert conn.execute("SELECT count(*) FROM retrieval_children_fts WHERE retrieval_children_fts MATCH 'alpha'").fetchone()[0] > 0


def test_evidence_byte_measurement_unions_overlapping_unicode_source_spans(tmp_path):
    raw = "αβγδε source"
    (tmp_path / "source.md").write_text(raw, encoding="utf-8")
    rows = [{"path": "source.md", "text": raw[start:end], "char_start": start, "char_end": end,
             "content_sha256": hashlib.sha256(raw[start:end].encode()).hexdigest(), "evidence_id": str(index)}
            for index, (start, end) in enumerate(((0, 4), (2, 7)))]
    report = evidence_sizes({"sources": rows}, tmp_path)
    assert report["source_text_utf8_bytes"] == sum(len(row["text"].encode()) for row in rows)
    assert report["unique_nonoverlap_utf8_bytes"] == len(raw[:7].encode())
    assert report["unique_nonoverlap_utf8_bytes"] < report["source_text_utf8_bytes"]
    docs = evidence_sizes({"sources": [{"path_or_url": "source.md", "snippet": raw[:4]}]}, tmp_path)
    assert docs["unique_nonoverlap_utf8_bytes"] == len(raw[:4].encode())
    rows[0]["text"] = "forged"
    with pytest.raises(AssertionError):
        evidence_sizes({"sources": rows}, tmp_path)


def test_library_fixture_versions_have_real_local_provenance_and_distinct_bytes(tmp_path):
    from pathlib import Path
    from urllib.parse import urlparse
    from urllib.request import url2pathname

    project = tmp_path / "project"
    project.mkdir()
    libraries = bootstrap_library_fixture(project, tmp_path / "owned-home" / "docs-indexes")
    assert set(libraries) == {"1.0.0", "2.0.0"}
    assert libraries["1.0.0"]["content_sha256"] != libraries["2.0.0"]["content_sha256"]
    for version, fixture in libraries.items():
        source = Path(url2pathname(urlparse(fixture["source"]).path))
        assert source.is_relative_to(project) and source.is_file()
        assert version in source.read_text()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == fixture["content_sha256"]
        assert fixture["generation_id"].startswith("gen-")


def test_natural_fixture_uses_default_source_bound_children_without_padding():
    from docmancer.core.structured_chunking import ChunkingConfig, chunk_markdown_parent_child

    documents = natural_protocol_documents()
    assert len(documents) == 5
    all_paragraphs = []
    for path, text in documents.items():
        paragraphs = [part for part in text.split("\n\n") if part and not part.startswith("#")]
        assert len(paragraphs) == 10
        assert all(sum(f"`{phase}`" in paragraph for paragraph in paragraphs) == 2 for phase in LARGE_PHASES)
        all_paragraphs.extend(paragraphs)
        _parents, children = chunk_markdown_parent_child(text, path)
        assert children and all(child.retrieval_token_estimate <= ChunkingConfig().hard_max_tokens for child in children)
        assert all(text[child.char_start:child.char_end] == child.display_text for child in children)
        assert sum(len(child.display_text.encode()) for child in children) == len(text.encode())
    assert len(set(all_paragraphs)) == 50
    # Authored corpus size is a fixture property, never a retrieval acceptance.
    print("Authored natural fixture bytes (NOT delivered):", sum(len(text.encode()) for text in documents.values()))
