from pathlib import Path
import shutil

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService
from tests.test_mcp_patch_plan_context_tool import _assert_selected_source_evidence, _declare_source_members


def test_patch_plan_context_output_contract_shapes(tmp_path):
    fixture = Path(__file__).parent / "fixtures/patch_plan_context/nbo_menu"
    root = tmp_path / "nbo_menu"
    shutil.copytree(fixture, root)
    member = "lib/modules/tsd_browser/presentation/menu/menu_line.dart"
    original = _declare_source_members(root, (member,))

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
    assert [row["file"] for row in payload["relevant_files"]] == [member]
    _assert_selected_source_evidence(payload, original)
    assert (root / member).read_bytes() == original[member]
