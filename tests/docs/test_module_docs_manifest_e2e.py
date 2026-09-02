from __future__ import annotations

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
    service = _service(tmp_path, monkeypatch)

    sync = service.sync_project_docs(str(project), with_vectors=False)
    assert sync.status == "success"

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
    for payload, marker in ((orion_public, "OrionRouter"), (vega_public, "VegaProof")):
        assert payload["status"] == "ok", payload
        rendered = str(payload)
        assert marker in rendered

    cross = call_docs_tool_payload(
        "get_docs_context",
        {
            "question": "What is ModuleEvidenceContract?",
            "project_path": str(project),
        },
        service,
    )
    assert cross["status"] == "ok", cross
    assert "ModuleEvidenceContract" in str(cross)
