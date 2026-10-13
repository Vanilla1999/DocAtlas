"""Public context and retrieval-runtime guards with real storage/selection.

Existing optics/scope documents and facts are reused unchanged. The vector
scenario substitutes only external embedding HTTP, not retrieval or validation.
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


def test_public_sdk_delivery_caps_and_explicit_lexical_expansion(tmp_path, record_property):
    """1 prepare, 12 public retrieval calls; real SQLite, no model/transport mocks."""
    from eval.heuristic_removal.sdk_delivery import observe
    audit = Path(__file__).resolve().parents[1] / "reports/docatlas-grounded-20261013/pre-model-research-audit"
    result = observe(tmp_path, audit)
    record_property("sdk_delivery", json.dumps(result, ensure_ascii=False))
    assert result["state_unchanged"]
    assert len(result["small"]) == 1
    assert sum(row["metadata"]["token_estimate"] for row in result["small"]) <= 100
    assert all(row["metadata"]["docmancer_tokens"] <= 100 for row in result["small"])
    assert (len(result["tight_text"]) + 3) // 4 <= 100
    assert len(result["wide"]) == 3
    assert len(result["dispatcher_acquired"]) == 3  # MCP pool not shrunk by SDK caps
    assert (len(result["wide_text"]) + 3) // 4 <= 12000
    for path in ("docs/packing.md", "docs/transport.md", "docs/storage.md"):
        source = result["documents"][path]
        assert source in result["wide_text"]
    fact = result["expected_neighbor"]
    assert not any(fact in row["text"] for row in result["bare"])
    for key in ("adjacent", "page", "dispatcher_expanded"):
        assert any(fact in row["text"] for row in result[key])
    assert fact in result["expanded_text"]
    assert (len(result["expanded_text"]) + 3) // 4 <= 600
    assert not result["zero_chunks"] and result["zero_text"] == ""
    for key in ("small", "wide", "bare", "adjacent", "page", "dispatcher_expanded"):
        for row in result[key]:
            relative = relative_path(row["source"], tmp_path / "project")
            source = result["documents"][relative]
            metadata = row["metadata"]
            start, end = metadata["char_span"]
            assert source[start:end] == row["text"]
            assert metadata["content_hash"] == sha(row["text"].encode())
            assert metadata["source_content_hash"] == sha(source.encode())
            assert metadata["doc_scope"] == "project"
            assert metadata["resolved_version"] == ""
            assert metadata["generation_id"] == result["wide"][0]["metadata"]["generation_id"]


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
        with env.context() as advanced, query_trace(True):
            advanced.setenv("DOCATLAS_MCP_ADVANCED_TOOLS", "1")
            patch_context = context(service, root, OPTICS_QUESTION, context_format="patch_context")
        assert patch_context.get("edit_ready") is False
        assert patch_context.get("sources"), json.dumps(patch_context, ensure_ascii=False)
        assert patch_context.get("answer_supported", False) is False
        for row in patch_context["sources"]:
            source = OPTICS_DOCUMENTS[relative_path(row["path"], root)]
            assert row["text"] in source
            assert row["content_sha256"] == sha(row["text"].encode())
            assert row["instruction_trust"] == "untrusted_data"
            if "char_start" in row and "char_end" in row:
                assert source[row["char_start"]:row["char_end"]] == row["text"]
        for path, statements in OPTICS_FACTS.items():
            windows = [row["text"] for row in patch_context["sources"]
                       if relative_path(row["path"], root) == path]
            for statement in statements:
                assert any(statement in text for text in windows)
        record_property("patch_context_evidence", json.dumps(patch_context))
        assert [(row["path"], row["text"]) for row in patch_context["sources"]] == [
            (row["path_or_url"], row["snippet"]) for row in packets[0]["sources"]
        ]
        # Direct SDK service calls own a source-read lifetime too; they must not
        # depend on being nested under the MCP handler to retain original bytes.
        direct = service.get_docs_context(
            OPTICS_QUESTION, project_path=str(root), scope="project",
            prepare_project_docs=False, allow_network=False,
        )
        assert direct.answer_available is False
        for statements in OPTICS_FACTS.values():
            for statement in statements:
                assert any(statement in str(row.get("content") or row.get("snippet") or "")
                           for row in direct.context_pack)
        direct_docs = service.get_project_docs(str(root), OPTICS_QUESTION, scope="project")
        for statements in OPTICS_FACTS.values():
            for statement in statements:
                assert any(statement in row.content for row in direct_docs.results)
        from docmancer import DocmancerClient
        sdk = DocmancerClient(db_path=inventory["storage_path"])
        sdk_text = sdk.get_context(OPTICS_QUESTION, budget=12000)
        for statements in OPTICS_FACTS.values():
            for statement in statements:
                assert statement in sdk_text
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
    with monkeypatch.context() as advanced, query_trace(True):
        advanced.setenv("DOCATLAS_MCP_ADVANCED_TOOLS", "1")
        patch = call_docs_tool_payload("get_docs_context", {
            "question": "Explain `Navigation` route registry.", "library": PACKAGE,
            "version": "1.0.0", "context_format": "patch_context",
        }, service)
    assert patch.get("result") == "data", patch
    assert patch["edit_ready"] is False
    expected = "NavigationRegistry is a route registry using FIRST_ONLY dispatch in version 1.0.0."
    assert any(expected in row["text"] for row in patch["sources"]), patch
    for row in patch["sources"]:
        assert row["text"] in f"# NavigationRegistry\n\n{expected}\n"
        assert row["content_sha256"] == sha(row["text"].encode())
        assert row["resolved_version"] == "1.0.0"
    assert [database(path) for path in paths] == before


def test_vector_runtime_preserves_source_windows_and_access(tmp_path, monkeypatch, record_property):
    """Production ingest/runtime with SQLite+sqlite-vec; only embedding HTTP is substituted.

    The fixed embedding response proves rank delivery/access, not model relevance.
    """
    import httpx
    import pytest
    from docmancer.agent import DocmancerAgent
    from docmancer.core.config import DocmancerConfig, VectorStoreConfig
    from docmancer.core.models import Document
    from docmancer.retrieval.runtime import dispatcher_for_agent
    from docmancer.retrieval.dispatch import HybridRetrievalError
    from docmancer.core.product_identity import ensure_owned_home

    home = tmp_path / "home"
    monkeypatch.setenv("DOCATLAS_HOME", str(home))
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-only-not-a-credential")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://embeddings.invalid/v1")
    monkeypatch.delenv("DOCATLAS_AUTO_VECTORS", raising=False)
    ensure_owned_home(home)
    calls = []

    def embedding_transport(self, request):
        assert str(request.url) == "https://embeddings.invalid/v1/embeddings"
        body = json.loads(request.content)
        calls.append(len(body["input"]))
        return httpx.Response(200, json={
            "object": "list", "model": body["model"],
            "data": [{"object": "embedding", "index": index, "embedding": [1.0, 0.0, 0.0, 0.0]}
                     for index, _ in enumerate(body["input"])],
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        })

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", embedding_transport)
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docs.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    config.embeddings.provider = "openai"
    config.embeddings.model = "text-embedding-3-small"
    config.embeddings.dimensions = 4
    config.embeddings.cache = str(tmp_path / "embeddings")
    config.vector_store = VectorStoreConfig(provider="sqlite-vec", options={"db_path": str(tmp_path / "vec.db")})
    config.retrieval.default_mode = "hybrid"
    config.retrieval.max_sections_per_source = 1
    config.retrieval.hierarchical.auto = True
    config.retrieval.hierarchical.auto_min_documents = 1
    config.retrieval.hierarchical.enabled = True
    text = ("# Observatory aperture\n\nObservatory aperture is 73 mm.\n\n"
            "# Observatory shutter\n\nObservatory shutter waits 19 seconds.\n\n"
            "# Observatory archive\n\nObservatory archive retains 41 nights.\n")
    agent = DocmancerAgent(config=config)
    agent.ingest_documents([
        Document(source="observatory.md", content=text, metadata={"format": "markdown"}),
        Document(source="secret.md", content="# Observatory\n\nObservatory secret is HIDDEN_97.\n",
                 metadata={"format": "markdown"}),
    ], with_vectors=True)
    before = database(config.index.db_path)
    evidence = []
    hybrid = dispatcher_for_agent(agent, mode="hybrid")
    with pytest.raises(HybridRetrievalError, match="capability_mismatch:sparse_model"):
        hybrid.run("observatory", mode="hybrid", limit=10, budget=4000, expand="none")
    for mode in ("dense", "hybrid"):
        result = dispatcher_for_agent(agent, mode=mode).run(
            "observatory", mode=mode, limit=10, budget=4000, expand="none",
            filters={"forbidden_sources": ["secret.md"]},
            allow_degraded=mode == "hybrid",
        )
        expected_mode = "dense" if mode == "dense" else "hybrid/lexical_fallback_degraded"
        assert result.mode_used == expected_mode, result
        if mode == "dense":
            assert not result.failures
        else:
            assert result.failures == {"vector": "capability_mismatch:sparse_model"}
        assert result.chunks
        for fact in ("Observatory aperture is 73 mm.", "Observatory shutter waits 19 seconds.",
                     "Observatory archive retains 41 nights."):
            assert any(fact in chunk.text for chunk in result.chunks), result
        for chunk in result.chunks:
            assert chunk.source == "observatory.md"
            assert chunk.text in text
            assert "HIDDEN_97" not in chunk.text
        evidence.append({"mode": result.mode_used, "sources": [chunk.source for chunk in result.chunks],
                         "texts": [chunk.text for chunk in result.chunks], "counts": result.candidate_counts})
    assert database(config.index.db_path) == before
    record_property("vector_runtime_evidence", json.dumps(evidence))
    record_property("embedding_http_calls", json.dumps(calls))


def test_public_patch_plan_literal_sources_without_scores_or_graph_expansion(tmp_path, monkeypatch, record_property):
    """Three public reads: literal members, bounded prefix, explicit member path."""
    from tests._shared_test_docs_service import _service_with_real_agent

    service = _service_with_real_agent(tmp_path, monkeypatch)
    monkeypatch.setenv("DOCATLAS_MCP_ADVANCED_TOOLS", "1")
    root = tmp_path / "project"
    documents = {
        "src/usage.py": "from .neighbor import helper\nvalue = PanelState\n",
        "src/definition.py": "class PanelState:\n    marker = 'DECLARATION_83'\n",
        "src/neighbor.py": "def helper():\n    return 'NEIGHBOR_29'\n",
        "src/panel_state.py": "alias_only = 'SPELLING_61'\n",
        "outside.py": "class PanelState:\n    forbidden = 'UNDECLARED_47'\n",
    }
    runtime.write_project(root, documents)
    (root / "docatlas.project-docs.yaml").write_text(json.dumps({
        "schema_version": 1, "documents": [],
        "code_files": [name for name in documents if name.startswith("src/")],
    }))
    before = files(root)
    args = {"question": "PanelState", "project_path": str(root), "max_tokens": 4000}
    with query_trace(True):
        wide = call_docs_tool_payload("get_patch_plan_context", args, service)
        narrow = call_docs_tool_payload("get_patch_plan_context", {**args, "max_files": 1}, service)
        explicit = call_docs_tool_payload("get_patch_plan_context", {
            **args, "question": "unmatched_term", "changed_files": ["src/neighbor.py", "../outside.py"],
        }, service)
    assert [row["file"] for row in wide["relevant_files"]] == ["src/usage.py", "src/definition.py"], wide
    assert narrow["relevant_files"] == wide["relevant_files"][:1]
    assert [row["file"] for row in explicit["relevant_files"]] == ["src/neighbor.py"], explicit
    for packet in (wide, narrow, explicit):
        assert packet["answer_completeness"] == "partial_navigational"
        assert packet["minimal_patch_path"] == []
        for row in packet["relevant_files"]:
            text = documents[row["file"]]
            assert row["action"] == "read"
            assert row["content_hash"] == "sha256:" + sha(text.encode())
            assert row["refs"]
            for ref in row["refs"]:
                assert ref["text"].rstrip("\n") == "\n".join(text.splitlines()[ref["start_line"]-1:ref["end_line"]])
                assert ref["locate_by_pattern"] in ref["text"]
        assert "UNDECLARED_47" not in json.dumps(packet)
    assert "PanelState" in wide["relevant_files"][0]["refs"][0]["text"]
    assert "NEIGHBOR_29" in explicit["relevant_files"][0]["refs"][0]["text"]
    assert files(root) == before
    record_property("patch_plan_packets", json.dumps([wide, narrow, explicit]))


def test_public_mixed_native_context_keeps_project_and_exact_library(tmp_path, state_root, record_property):
    """One prepared project, one real library index, one mixed public request."""
    from tests.docs.test_dependency_version_transition import _seed, PACKAGE
    from docmancer.docs.service import LibraryDocsService
    from docmancer.core.product_identity import ensure_owned_home
    import os

    root = (tmp_path / "project").resolve()
    runtime.write_project(root, OPTICS_DOCUMENTS)
    with runtime.isolated_service(state_root) as (service, config):
        home = Path(os.environ["DOCATLAS_HOME"])
        home.mkdir(mode=0o700)
        ensure_owned_home(home)
        inventory = runtime.index_project(service, config, root)
        # Explicit fixture provisioning uses the writable service, not the
        # read-only MCP facade. Both point at this isolated host's real stores.
        record = _seed(LibraryDocsService(config=config, library_index_root=home / "mcp-members" / "docs-indexes"), "1.0.0", 'MIXED_🧭<a id="raw"></a>_ONLY')
        library_db = service._index_config_for(record).index.db_path
        before = (database(inventory["storage_path"]), database(library_db), files(root))
        with query_trace(True):
            packet = context(service, root, OPTICS_QUESTION + " Also explain NavigationRegistry.",
                             library=PACKAGE, version="1.0.0")
        assert packet.get("context_available") is True, packet
        assert packet.get("answer_supported") is False and packet.get("edit_ready") is False
        facts(packet, root, OPTICS_FACTS)
        expected = 'NavigationRegistry is a route registry using MIXED_🧭<a id="raw"></a>_ONLY dispatch in version 1.0.0.'
        library_rows = [row for row in packet["sources"] if row["path_or_url"].startswith("https://")]
        assert any(expected in row["snippet"] for row in library_rows), packet
        for row in library_rows:
            assert row["path_or_url"] == f"https://pub.dev/documentation/{PACKAGE}/1.0.0/nav_kit/NavigationRegistry-class.html"
            assert row["snippet"] in f"# NavigationRegistry\n\n{expected}\n"
            assert row["version_binding"] == "exact_snapshot"
        local = {**packet, "sources": [row for row in packet["sources"] if row not in library_rows]}
        assert not integrity(local, root, OPTICS_DOCUMENTS)["errors"]
        assert (database(inventory["storage_path"]), database(library_db), files(root)) == before
        record_property("mixed_context_evidence", json.dumps(packet))
