import pytest


@pytest.mark.parametrize("question", [
    "Какой срок хранения документации предписывает лунный квантовый регламент DocAtlas?",
])
def test_live_normative_premise_cannot_use_generic_storage_evidence(tmp_path, monkeypatch, question):
    from tests.test_named_document_context_integration import _named_document_service
    from docmancer.mcp.docs_server import call_docs_tool_payload

    service, project = _named_document_service(
        tmp_path, monkeypatch, ["ARCHITECTURE.md"], {"ARCHITECTURE.md": (
            "# Project documentation storage and isolation\n\n"
            "Project documentation storage uses a per-project SQLite index.\n"
        )},
    )
    result = call_docs_tool_payload(
        "get_docs_context", {"question": question, "project_path": project}, service,
    )
    assert result["status"] == "insufficient_evidence"
    assert result["answer_supported"] is False
    assert result["context_available"] is False
    assert not result.get("sources")
