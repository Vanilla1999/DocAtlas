from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from docmancer.docs.interfaces.mcp.project_tools import MCP_COMPACT_OUTPUT_MAX_BYTES, _compact_mcp_payload, _compact_project_context, handle_project_tool
from docmancer.docs.application.project_context_service import ProjectContextService
from docmancer.docs.models import ProjectDocsChunk, ProjectDocsResult
from tests.docs.test_project_context_service import FakeProjectContextFacade


def test_compact_output_omits_raw_project_docs_results():
    result = asdict(ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "use go_router"))

    compact = _compact_project_context(result)

    assert compact["project_docs"]["omitted"] is True
    assert compact["project_docs"]["results"] == []
    assert compact["project_docs"]["see"] == "context_pack"


def test_full_output_preserves_raw_project_docs_results():
    result = asdict(ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "use go_router"))

    assert result["project_docs"]["results"]


def test_mcp_project_context_details_stays_compact_without_full_output_opt_in():
    service: Any = type(
        "FakeService",
        (),
        {"get_project_context": lambda self, *args, **kwargs: ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "use go_router")},
    )()

    payload = handle_project_tool("get_project_context", {"project_path": "/repo", "question": "use go_router", "details": True}, service)

    assert payload is not None
    assert payload["output_mode"] == "compact"
    assert payload["project_docs"]["results"] == []
    assert payload["warnings"][-1]["code"] == "project_context_full_output_requires_output_mode_full"


def test_mcp_project_context_full_output_requires_explicit_output_mode():
    service: Any = type(
        "FakeService",
        (),
        {"get_project_context": lambda self, *args, **kwargs: ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "use go_router")},
    )()

    payload = handle_project_tool("get_project_context", {"project_path": "/repo", "question": "use go_router", "details": True, "output_mode": "full"}, service)

    assert payload is not None
    assert payload["output_mode"] == "full"
    assert payload["project_docs"]["results"]


def test_mcp_project_context_compact_output_has_hard_size_cap():
    large = "x" * 120_000
    result = ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "find current web API camera implementation")
    result.context_pack.append({"doc_scope": "project", "source_class": "project_doc", "path": "docs/ScanDoc.md", "content": large})
    result.trust_contract["selected"] = [{"path": "docs/ScanDoc.md", "snippet": large}]
    service: Any = type("FakeService", (), {"get_project_context": lambda self, *args, **kwargs: result})()

    payload = handle_project_tool("get_project_context", {"project_path": "/repo", "question": "find current web API camera implementation"}, service)

    assert payload is not None
    assert len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) <= MCP_COMPACT_OUTPUT_MAX_BYTES
    assert payload["mcp_compaction"]["truncated"] is True
    assert any(isinstance(warning, dict) and warning["code"] == "mcp_compact_output_truncated" for warning in payload["warnings"])


def test_mcp_compact_output_hard_cap_handles_many_small_mapping_fields():
    payload = {
        "project_path": "/repo",
        "question": "find current web API camera implementation",
        "status": "success",
        "trust_contract": {f"source_{index}": {"path": f"docs/{index}.md", "score": index} for index in range(5_000)},
        "diagnostics": {f"metric_{index}": index for index in range(2_000)},
        "warnings": [],
    }

    compact = _compact_mcp_payload(payload)

    assert len(json.dumps(compact, ensure_ascii=False).encode("utf-8")) <= MCP_COMPACT_OUTPUT_MAX_BYTES
    assert compact["mcp_compaction"]["hard_cap_enforced"] is True
    assert "trust_contract" in compact["mcp_compaction"]["omitted_sections"]
    assert compact["trust_contract"]["omitted"] is True


def test_compact_output_keeps_context_pack_trust_contract_and_outline():
    result = asdict(ProjectContextService(FakeProjectContextFacade()).get_project_context("/repo", "use go_router"))
    compact = _compact_project_context(result)

    assert compact["context_pack"]
    assert compact["trust_contract"]
    assert compact["answer_outline"]


def test_compact_output_preserves_trust_contract_context_sources(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "help_request_details_screen.dart").write_text(
        """
class HelpRequestDetailsScreen {
  final label = 'Вернуть в работу';
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path=str(tmp_path),
        query='Как реализовать кнопку "Вернуть в работу"?',
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="Help requests follow UI -> Cubit -> Service -> Repository -> API with enough context for stable project-doc selection.",
                source=str(tmp_path / "ARCHITECTURE.md"),
                url=None,
                path="ARCHITECTURE.md",
            )
        ],
        indexed_sources=[{"path": "ARCHITECTURE.md", "source": str(tmp_path / "ARCHITECTURE.md")}],
    )

    result = asdict(ProjectContextService(facade).get_project_context(str(tmp_path), 'Как реализовать кнопку "Вернуть в работу"?', mode="project-only"))
    compact = _compact_project_context(result)

    source_evidence = compact["trust_contract"]["context_sources"]["source_evidence"]
    assert source_evidence[0]["path"] == "lib/help_request_details_screen.dart"
    assert source_evidence[0]["line_start"] == 2
    assert source_evidence[0]["matched_terms"] == ["Вернуть в работу"]


def test_compact_output_exposes_answer_completeness_contract():
    facade = FakeProjectContextFacade()
    facade.project_docs = ProjectDocsResult(
        project_path="/repo",
        query='Как реализовать кнопку "Вернуть в работу"?',
        results=[
            ProjectDocsChunk(
                title="Architecture",
                content="Help requests follow UI -> Cubit -> Service -> Repository -> API via help_request_details_screen.",
                source="/repo/ARCHITECTURE.md",
                url=None,
                path="ARCHITECTURE.md",
            )
        ],
    )
    result = asdict(ProjectContextService(facade).get_project_context("/repo", 'Как реализовать кнопку "Вернуть в работу"?', mode="project-only"))

    compact = _compact_project_context(result)

    assert compact["answer_type"] == "partial_navigational"
    assert compact["answer_completeness"]["status"] == "partial"
    assert compact["answer_completeness"]["missing_terms"] == ["Вернуть в работу"]
    assert compact["recommended_next_actions"][-1]["action"] == "search_project_sources"
