from pathlib import Path

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService


def test_patch_plan_context_negative_symbol_alternative_from_nbo_fixture():
    root = Path(__file__).parent / "fixtures/patch_plan_context/nbo_menu"

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Use showBottomDialog or PBBottomSheet.open for menu_line bottom sheet",
            "project_path": str(root),
            "symbol_queries": ["showBottomDialog", "PBBottomSheet.open"],
            "include_dependency_source": True,
        },
        LibraryDocsService(),
    )

    assert payload is not None
    missing = next(item for item in payload["missing_symbols"] if item["symbol"] == "showBottomDialog")
    assert missing["result"] == "not_found"
    assert missing["searched_scopes"] == ["project", "dependency"]
    assert missing["nearest_alternatives"][0]["symbol"] == "PBBottomSheet.open"
