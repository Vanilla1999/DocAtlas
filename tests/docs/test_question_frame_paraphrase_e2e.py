from __future__ import annotations

from docmancer.agent import DocmancerAgent
from docmancer.core.config import DocmancerConfig
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import call_docs_tool_payload


def _service(tmp_path, monkeypatch) -> LibraryDocsService:
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=DocmancerAgent(config=config),
        job_tracker=DocsJobTracker(),
    )


def test_reusable_question_frames_survive_real_manifest_sync_and_public_mcp(tmp_path, monkeypatch):
    project = tmp_path / "project"
    docs = project / "docs"
    docs.mkdir(parents=True)
    (project / "README.md").write_text("# Frame test project\n", encoding="utf-8")
    (docs / "sources.md").write_text(
        "# Supported source types\n\n"
        "DocAtlas Docs supports exactly five source types: `GitBook sites`, "
        "`Mintlify sites`, `Generic web docs`, `GitHub repos`, and `Local files`.\n",
        encoding="utf-8",
    )
    (docs / "formats.md").write_text(
        "# Local file formats\n\n"
        "Local file formats are `.md`, `.pdf`, `.docx`, `.rtf`, `.txt`, and `.html`.\n",
        encoding="utf-8",
    )
    (docs / "testing.md").write_text(
        "# Test markers\n\n"
        "The test suite markers are `integration`, `advanced`, `live`, and `live_network`.\n",
        encoding="utf-8",
    )
    (docs / "sync.md").write_text(
        "# Project documentation sync\n\n"
        "After changing a project documentation file, call "
        "`prepare_docs(action=\"sync_project_docs\")` to reconcile the project-docs index.\n",
        encoding="utf-8",
    )
    (docs / "smoke.md").write_text(
        "# Two-cell smoke procedure requirements\n\n"
        "The two-cell smoke procedure requires a provider-free preflight, one canary, "
        "exactly two cells, no retries, an event-stream audit, and harness verification.\n",
        encoding="utf-8",
    )
    entries = (
        ("README.md", "overview"),
        ("docs/sources.md", "other"),
        ("docs/formats.md", "other"),
        ("docs/testing.md", "development"),
        ("docs/sync.md", "runbook"),
        ("docs/smoke.md", "runbook"),
    )
    manifest = ["schema_version: 1", "documents:"]
    for path, role in entries:
        manifest.extend((
            f"  - path: {path}",
            f"    role: {role}",
            "    scope: project",
            f"    description: Test evidence from {path}.",
            "    authority: source_of_truth",
            "    status: active",
            "    impact: track",
        ))
    (project / "docatlas.project-docs.yaml").write_text("\n".join(manifest) + "\n", encoding="utf-8")

    service = _service(tmp_path, monkeypatch)
    assert service.sync_project_docs(str(project), with_vectors=False).status == "success"

    cases = (
        ("What source types are supported for indexing?", "GitBook sites"),
        ("Which source types are supported for indexing?", "GitBook sites"),
        ("Какие типы источников поддерживаются для индексации?", "GitBook sites"),
        ("Which file formats are supported for indexing?", ".docx"),
        ("Which document formats are supported for indexing?", ".rtf"),
        ("What test markers are available?", "live_network"),
        ("Which pytest markers are available?", "live_network"),
        ("What does the two-cell smoke procedure require?", "exactly two cells"),
        ("What is required by the two-cell smoke procedure?", "exactly two cells"),
        ("How do I sync project docs after changing a file?", "sync_project_docs"),
        ("Как синхронизировать документацию проекта после изменения файла?", "sync_project_docs"),
    )
    for mode in (None, "project"):
        for question, expected in cases:
            arguments = {"question": question, "project_path": str(project)}
            if mode is not None:
                arguments["mode"] = mode
            payload = call_docs_tool_payload(
                "get_docs_context",
                arguments,
                service,
            )
            assert payload["status"] == "ok", (mode, question, payload)
            assert expected in str(payload), (mode, question, payload)

    rejected = (
        "What markers are available?",
        "Which formats are supported?",
        "How do I update the docs index?",
        "What does the project require?",
        "Which source types are supported for indexing; what is the Bitcoin price?",
        "Which source types are supported for indexing. What is the Bitcoin price?",
        "Which source types are supported for indexing plus tell me the Bitcoin price?",
        "How do I sync project docs after changing a file and rebuild vectors?",
    )
    for mode in (None, "project"):
        for question in rejected:
            arguments = {"question": question, "project_path": str(project)}
            if mode is not None:
                arguments["mode"] = mode
            payload = call_docs_tool_payload(
                "get_docs_context",
                arguments,
                service,
            )
            assert payload["status"] != "ok", (mode, question, payload)
