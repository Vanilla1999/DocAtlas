from __future__ import annotations

from hashlib import sha256

from eval.heuristic_removal.receipts import database, files

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


def _service(tmp_path, monkeypatch) -> LibraryDocsService:
    monkeypatch.setenv("DOCATLAS_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )


def test_two_module_docs_manifest_sync_filter_and_public_mcp(tmp_path, monkeypatch):
    from tests._fixture_member_transaction import indexed_fixture_member_service

    project = tmp_path / "project"
    (project / "modules" / "orion").mkdir(parents=True)
    (project / "modules" / "vega").mkdir(parents=True)
    (project / "README.md").write_text("# Example architecture\n\nTwo documented modules share a proof contract.\n", encoding="utf-8")
    docs = project / "docs" / "modules"
    docs.mkdir(parents=True)
    (docs / "orion-routing.md").write_text(
        "# Orion routing\n\n"
        "`OrionRouter` routes each bounded project question into explicit proof facets. "
        "It publishes those facets through `ModuleEvidenceContract` for the proof module. "
        "`ModuleEvidenceContract` is the boundary that carries planned facets from OrionRouter to VegaProof.\n",
        encoding="utf-8",
    )
    (docs / "vega-proof.md").write_text(
        "# Vega proof\n\n"
        "`VegaProof` validates every mandatory facet received through "
        "`ModuleEvidenceContract` and rejects incomplete evidence. "
        "`ModuleEvidenceContract` is the boundary that carries planned facets from OrionRouter to VegaProof.\n",
        encoding="utf-8",
    )
    (project / "docatlas.project-docs.yaml").write_text(
        "schema_version: 1\n"
        "documents:\n"
        "  - path: README.md\n"
        "    role: overview\n"
        "    scope: project\n"
        "    description: Example project architecture overview.\n"
        "    authority: source_of_truth\n"
        "    status: active\n"
        "    impact: track\n"
        "  - path: docs/modules/orion-routing.md\n"
        "    role: module_architecture\n"
        "    scope: module\n"
        "    module_path: modules/orion\n"
        "    description: Orion question routing contract.\n"
        "    authority: source_of_truth\n"
        "    status: active\n"
        "    impact: track\n"
        "  - path: docs/modules/vega-proof.md\n"
        "    role: module_architecture\n"
        "    scope: module\n"
        "    module_path: modules/vega\n"
        "    description: Vega proof validation contract.\n"
        "    authority: source_of_truth\n"
        "    status: active\n"
        "    impact: track\n",
        encoding="utf-8",
    )
    service, sync = indexed_fixture_member_service(
        tmp_path, monkeypatch, project,
        ("README.md", "docs/modules/orion-routing.md", "docs/modules/vega-proof.md"),
    )
    assert sync.status == "success"
    # One real preparation, two service queries and eleven public MCP reads.
    # Independent source bytes and catalog/index state are fixed before reads.
    documents = {name: (project / name).read_text(encoding="utf-8") for name in (
        "README.md", "docs/modules/orion-routing.md", "docs/modules/vega-proof.md",
    )}
    before_files = files(project)
    before_db = database(service.config.index.db_path)

    def check_sources(payload, expected_paths, expected_scope):
        assert payload.get("status") == "ok", payload
        assert payload.get("answer_supported") is False
        assert payload.get("edit_ready") is False
        rows = payload.get("sources") or []
        assert rows, payload
        delivered_paths = set()
        for row in rows:
            path = row["path_or_url"]
            if path.startswith(str(project) + "/"):
                path = path[len(str(project)) + 1:]
            assert path in expected_paths, row
            delivered_paths.add(path)
            text = documents[path]
            snippet = row["snippet"]
            assert snippet and snippet in text
            assert row["scope"] == expected_scope
            # Public content_sha256 is a DTO fingerprint, not a raw-file hash.
            fingerprint = row["content_sha256"]
            assert len(fingerprint) == 64 and all(ch in "0123456789abcdef" for ch in fingerprint)
            assert row["project_identity"] == "local:" + sha256(str(project).encode()).hexdigest()
            assert row["version_binding"] == "unversioned"
            start, end = row["line_start"], row["line_end"]
            assert type(start) is int and type(end) is int
            assert 1 <= start <= end <= len(text.splitlines())
            assert snippet in "".join(text.splitlines(keepends=True)[start - 1:end])
        assert delivered_paths == set(expected_paths), payload
        required_facts = {
            "README.md": "Two documented modules share a proof contract.",
            "docs/modules/orion-routing.md": "It publishes those facets through `ModuleEvidenceContract` for the proof module.",
            "docs/modules/vega-proof.md": "`VegaProof` validates every mandatory facet received through `ModuleEvidenceContract` and rejects incomplete evidence.",
        }
        for path in expected_paths:
            assert any(required_facts[path] in row["snippet"] for row in rows), (path, payload)

    orion = service.get_project_docs(
        str(project), "OrionRouter ModuleEvidenceContract",
        module_path="modules/orion", scope="module", tokens=1200, limit=4,
    )
    vega = service.get_project_docs(
        str(project), "VegaProof ModuleEvidenceContract",
        module_path="modules/vega", scope="module", tokens=1200, limit=4,
    )
    assert orion.status == vega.status == "success"
    assert orion.results and vega.results
    assert {item.module_path for item in orion.results} == {"modules/orion"}
    assert {item.module_path for item in vega.results} == {"modules/vega"}
    assert {item.path for item in orion.results} == {"docs/modules/orion-routing.md"}
    assert {item.path for item in vega.results} == {"docs/modules/vega-proof.md"}

    orion_public = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "What does OrionRouter do?",
            "project_path": str(project),
            "module_path": "modules/orion",
            "scope": "module",
        },
        service,
    )
    vega_public = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "What does VegaProof do?",
            "project_path": str(project),
            "module_path": "modules/vega",
            "scope": "module",
        },
        service,
    )
    for payload, name, marker in ((orion_public, "orion", "OrionRouter"),
                                  (vega_public, "vega", "VegaProof")):
        path = f"docs/modules/{name}-{'routing' if name == 'orion' else 'proof'}.md"
        check_sources(payload, {path}, "module")
        assert any(marker in row["snippet"] for row in payload["sources"])
        # Three explicit argument forms, not natural-language scope guesses.
        # A supplied path must never widen to siblings, even with scope=all.
        for scope in (None, "all", "project"):
            arguments = {"question": f"What does {marker} do?",
                         "project_path": str(project), "module_path": f"modules/{name}"}
            if scope is not None:
                arguments["scope"] = scope
            narrowed = call_docs_tool_payload("get_docs_context", arguments, service)
            check_sources(narrowed, {path}, "module")
            assert any(marker in row["snippet"] for row in narrowed["sources"])

    cross = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "What is ModuleEvidenceContract?",
            "project_path": str(project),
        },
        service,
    )
    module_paths = {"docs/modules/orion-routing.md", "docs/modules/vega-proof.md"}
    check_sources(cross, module_paths, "module")
    full = call_docs_tool_payload("get_docs_context", {
        "question": "What is ModuleEvidenceContract?", "project_path": str(project), "scope": "all",
    }, service)
    check_sources(full, module_paths, "module")
    project_only = call_docs_tool_payload("get_docs_context", {
        "question": "Example architecture", "project_path": str(project), "scope": "project",
    }, service)
    check_sources(project_only, {"README.md"}, "project")
    assert any("Two documented modules share a proof contract." in row["snippet"]
               for row in project_only["sources"])
    assert files(project) == before_files
    assert database(service.config.index.db_path) == before_db
