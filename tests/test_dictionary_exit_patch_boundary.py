"""Advisory patch context cannot claim code symbols or mutation authority."""
import pytest

from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService




@pytest.mark.parametrize("question", ["close menu", "`closeMenu`"])
def test_public_patch_packet_presence_is_not_answer_or_edit_authority(question):
    payload = handle_project_tool("get_patch_constraints", {
        "question": question, "max_constraints": 2, "max_tokens": 180,
    }, LibraryDocsService())
    assert payload["packet_available"] is True
    assert payload["status"] == "insufficient_evidence"
    assert payload["policy_coverage"] == "unresolved"
    for key in ("answer_available", "answer_supported", "mutation_authorized", "edit_ready"):
        assert payload[key] is False
    assert payload["token_estimate"] <= 180



