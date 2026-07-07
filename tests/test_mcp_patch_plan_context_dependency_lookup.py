from pathlib import Path

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService


def test_patch_plan_context_resolves_dart_dependency_source_from_nbo_fixture():
    root = Path(__file__).parent / "fixtures/patch_plan_context/nbo_menu"

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Use pole_base_kit PBBottomSheet.open PBButton PBIcon PBIcons",
            "project_path": str(root),
            "symbol_queries": ["PBBottomSheet.open", "PBButton", "PBIcon", "PBIcons"],
            "include_dependency_source": True,
        },
        LibraryDocsService(),
    )

    assert payload is not None
    symbols = {item["symbol"]: item for item in payload["existing_apis"]}
    assert {"PBBottomSheet.open", "PBButton", "PBIcon", "PBIcons"}.issubset(symbols)
    assert symbols["PBBottomSheet.open"]["file"].endswith("fake_pub_cache/ui_base/lib/src/widgets/pb_bottomsheet.dart")
