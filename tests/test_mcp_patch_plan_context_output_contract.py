from pathlib import Path

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService


def test_patch_plan_context_output_contract_shapes():
    root = Path(__file__).parent / "fixtures/patch_plan_context/nbo_menu"

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Plan menu_line bottom sheet with showBottomDialog fallback",
            "project_path": str(root),
            "symbol_queries": ["MenuLine", "showBottomDialog"],
        },
        LibraryDocsService(),
    )

    assert payload is not None
    assert payload["reason_code"] is None
    assert isinstance(payload["token_estimate"], int)
    assert {"behavior", "file", "start_line", "end_line", "symbol", "evidence", "confidence"}.issubset(payload["current_behavior"][0])
    assert all({"risk", "severity", "source", "mitigation"}.issubset(item) for item in payload["risks_and_constraints"])
