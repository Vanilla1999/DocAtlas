import json
from pathlib import Path

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService


def test_patch_plan_context_nbo_fixture_acceptance_smoke():
    root = Path(__file__).parent / "fixtures/patch_plan_context/nbo_menu"
    design_context = json.loads((root / "design/menu.pen.summary.json").read_text(encoding="utf-8"))

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Изменить Flutter UI menu_line: вместо inline меню открыть bottom sheet/dialog по дизайну menu.pen, использовать pole_base_kit/ui_base buttons/icons, сохранить screenshot/camera/tabs/ScanDoc/rating/info/logout/admin, убрать legacy Bluetooth RT40/MS300 QR buttons, сохранить needFlashLight/needBT/isEmulator semantics.",
            "project_path": str(root),
            "symbol_queries": ["MenuLine", "MenuIcon", "SystemLine", "MenuNotifier", "TabIcon", "showBottomDialog", "PBBottomSheet.open", "PBButton", "PBIcon", "PBIcons"],
            "design_context": design_context,
            "include_dependency_source": True,
            "max_files": 12,
        },
        LibraryDocsService(),
    )

    assert payload is not None
    files = {item["file"] for item in payload["relevant_files"]}
    assert "lib/modules/tsd_browser/presentation/menu/menu_line.dart" in files
    assert "lib/modules/tsd_browser/presentation/menu/menu_icon.dart" in files
    assert "lib/modules/system_line/presentation/system_line.dart" in files
    assert "lib/modules/tsd_browser/presentation/menu/provider/menu_notifier.dart" in files
    assert "lib/modules/tsd_browser/presentation/browser_screen/widgets/available_tabs/tab_icon.dart" in files
    assert next(item for item in payload["missing_symbols"] if item["symbol"] == "showBottomDialog")["result"] == "not_found"
    assert {"PBBottomSheet.open", "PBButton", "PBIcon", "PBIcons"}.issubset({item["symbol"] for item in payload["existing_apis"]})
    assert payload["minimal_patch_path"]
    assert any(item["value"] == "flutter analyze" for item in payload["verification"])
