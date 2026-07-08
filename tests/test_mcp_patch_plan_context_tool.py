from __future__ import annotations

import json
from pathlib import Path

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool, project_tools
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import TOOLS


REQUIRED_SECTIONS = {
    "schema_version",
    "tool",
    "status",
    "reason_code",
    "answer_available",
    "answer_completeness",
    "task",
    "current_behavior",
    "relevant_files",
    "existing_apis",
    "missing_symbols",
    "design_context",
    "minimal_patch_path",
    "risks_and_constraints",
    "verification",
    "evidence",
    "rejected_sources",
    "warnings",
    "next_actions",
    "token_estimate",
    "output_mode",
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _source_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "nbo_menu"
    _write(
        root / "lib/modules/tsd_browser/presentation/menu/menu_line.dart",
        """
import 'menu_page_builder.dart';

class MenuLine extends StatelessWidget {
  const MenuLine({super.key});

  Widget build(BuildContext context) {
    return MenuPageBuilder();
  }
}
""".strip(),
    )
    _write(
        root / "lib/modules/tsd_browser/presentation/menu/menu_icon.dart",
        """
class MenuIcon extends StatelessWidget {
  void toggleMenu() {}
}
""".strip(),
    )
    _write(
        root / "lib/modules/system_line/presentation/system_line.dart",
        """
import '../../tsd_browser/presentation/menu/menu_icon.dart';

class SystemLine extends StatelessWidget {
  Widget build(BuildContext context) => MenuIcon();
}
""".strip(),
    )
    _write(
        root / "lib/modules/tsd_browser/presentation/menu/provider/menu_notifier.dart",
        """
class MenuNotifier {
  bool needFlashLight = false;
  bool needBT = false;
}
""".strip(),
    )
    _write(
        root / "lib/modules/tsd_browser/presentation/browser_screen/widgets/available_tabs/tab_icon.dart",
        """
class TabIcon extends StatelessWidget {
  void openTab() {}
}
""".strip(),
    )
    _write(
        root / "docs/scandoc_web_camera_api_plan.md",
        "Camera dialog bottom sheet plan without exact menu terms.",
    )
    _write(
        root / "lib/generated/menu_line.g.dart",
        "class GeneratedMenuLine {}",
    )
    return root


def _dependency_fixture(tmp_path: Path) -> Path:
    root = _source_fixture(tmp_path)
    dep_root = tmp_path / "deps/ui_base"
    _write(
        dep_root / "lib/src/widgets/pb_bottomsheet.dart",
        """
class PBBottomSheet {
  static Future<void> open(BuildContext context) async {
    return;
  }
}
""".strip(),
    )
    _write(
        dep_root / "lib/src/widgets/pb_button.dart",
        """
class PBButton extends StatelessWidget {
  const PBButton({super.key});
}
""".strip(),
    )
    _write(
        dep_root / "lib/src/icons/pb_icon.dart",
        """
class PBIcon extends StatelessWidget {
  const PBIcon({super.key});
}

class PBIcons {
  static const close = 'close';
}
""".strip(),
    )
    _write(
        root / ".dart_tool/package_config.json",
        json.dumps(
            {
                "configVersion": 2,
                "packages": [
                    {"name": "ui_base", "rootUri": dep_root.as_uri(), "packageUri": "lib/"},
                    {"name": "pole_base_kit", "rootUri": "../deps/ui_base", "packageUri": "lib/"},
                ],
            }
        ),
    )
    _write(
        root / "pubspec.lock",
        """
packages:
  ui_base:
    dependency: transitive
    description:
      name: ui_base
    source: hosted
    version: "1.2.3"
""".strip(),
    )
    _write(
        root / ".pub-cache/hosted/pub.dev/ui_base-9.9.9/lib/decoy.dart",
        """
class DecoyPubCacheOnly {}

class PBCacheOnly {}
""".strip(),
    )
    return root


def test_get_patch_plan_context_exposed_in_public_mcp_tools():
    names = {tool["name"] for tool in TOOLS}

    assert "get_patch_plan_context" in names


def test_get_patch_plan_context_schema_contains_required_fields():
    tool = next(tool for tool in TOOLS if tool["name"] == "get_patch_plan_context")
    schema = tool["inputSchema"]
    properties = schema["properties"]

    assert schema["required"] == ["question"]
    assert properties["question"]["type"] == "string"
    assert properties["project_path"]["type"] == ["string", "null"]
    assert properties["changed_files"]["items"]["type"] == "string"
    assert properties["symbol_queries"]["items"]["type"] == "string"
    assert properties["design_context"]["type"] == ["object", "null"]
    assert properties["include_dependency_source"]["default"] is True
    assert properties["max_files"]["default"] == 12
    assert properties["max_files"]["minimum"] == 1
    assert properties["max_files"]["maximum"] == 50
    assert properties["max_snippets"]["default"] == 16
    assert properties["max_snippets"]["minimum"] == 1
    assert properties["max_snippets"]["maximum"] == 40
    assert properties["max_tokens"]["default"] == 2400
    assert properties["max_tokens"]["minimum"] == 200
    assert properties["max_tokens"]["maximum"] == 12000
    assert properties["output_mode"]["enum"] == ["compact", "debug", "full", None]


def test_get_patch_plan_context_routes_through_project_tools():
    assert "get_patch_plan_context" in [tool["name"] for tool in project_tools(TOOLS)]


def test_get_patch_plan_context_handler_accepts_minimal_question():
    payload = handle_project_tool(
        "get_patch_plan_context",
        {"question": "Plan changing menu_line to bottom sheet"},
        LibraryDocsService(),
    )

    assert payload is not None
    assert REQUIRED_SECTIONS.issubset(payload.keys())
    assert payload["schema_version"] == "patch-plan-context-1"
    assert payload["tool"] == "get_patch_plan_context"
    assert payload["status"] == "partial"
    assert payload["reason_code"] is None
    assert payload["answer_available"] is False
    assert payload["answer_completeness"] == "partial_navigational"
    assert payload["task"] == {"title": "Plan changing menu_line to bottom sheet", "project": None}
    assert payload["warnings"] == ["Patch planning source analysis is not implemented yet."]
    assert isinstance(payload["token_estimate"], int)
    assert payload["output_mode"] == "compact"


def test_get_patch_plan_context_avoids_hardcoded_ui_risks_for_mcp_tasks(tmp_path: Path):
    root = tmp_path / "docmancer"
    _write(
        root / "docmancer/docs/application/library_registry_ops.py",
        """
class LibraryRegistryOps:
    def prune_library_docs(self):
        return None
""".strip(),
    )
    _write(
        root / "docmancer/docs/interfaces/mcp/context_tools.py",
        """
def _answer_payload(payload):
    return payload
""".strip(),
    )

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Fix Docmancer MCP answer_available and prune_library_docs response shape",
            "project_path": str(root),
            "symbol_queries": ["prune_library_docs", "_answer_payload"],
        },
        LibraryDocsService(),
    )

    assert payload is not None
    risk_text = "\n".join(item["risk"] for item in payload["risks_and_constraints"])
    plan_text = json.dumps(payload["minimal_patch_path"], ensure_ascii=False)
    assert "needFlashLight" not in risk_text
    assert "Bluetooth" not in risk_text
    assert "bottom sheet" not in plan_text


def test_get_patch_plan_context_response_is_json_serializable():
    payload = handle_project_tool(
        "get_patch_plan_context",
        {"question": "Plan changing menu_line to bottom sheet"},
        LibraryDocsService(),
    )

    json.dumps(payload)


def test_get_patch_plan_context_finds_relevant_source_files_by_exact_terms(tmp_path: Path):
    root = _source_fixture(tmp_path)

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Plan menu_line, system_line, menu_notifier changes",
            "project_path": str(root),
            "symbol_queries": ["MenuLine", "SystemLine", "MenuNotifier"],
        },
        LibraryDocsService(),
    )

    files = [item["file"] for item in payload["relevant_files"]]
    assert "lib/modules/tsd_browser/presentation/menu/menu_line.dart" in files
    assert "lib/modules/system_line/presentation/system_line.dart" in files
    assert "lib/modules/tsd_browser/presentation/menu/provider/menu_notifier.dart" in files
    assert "docs/scandoc_web_camera_api_plan.md" not in files
    assert "lib/generated/menu_line.g.dart" not in files

    menu_line = next(item for item in payload["relevant_files"] if item["file"].endswith("menu_line.dart"))
    assert menu_line["action"] == "read"
    assert "MenuLine" in menu_line["symbols"]
    assert menu_line["refs"]
    assert menu_line["refs"][0]["start_line"] >= 1
    assert menu_line["refs"][0]["end_line"] >= menu_line["refs"][0]["start_line"]
    assert menu_line["refs"][0]["locate_by_pattern"]


def test_get_patch_plan_context_normalizes_snake_case_and_pascal_case(tmp_path: Path):
    root = _source_fixture(tmp_path)

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Plan MenuIcon and TabIcon changes",
            "project_path": str(root),
            "symbol_queries": ["menu_icon", "tab_icon"],
        },
        LibraryDocsService(),
    )

    files = [item["file"] for item in payload["relevant_files"]]
    assert files[:2] == [
        "lib/modules/tsd_browser/presentation/menu/menu_icon.dart",
        "lib/modules/tsd_browser/presentation/browser_screen/widgets/available_tabs/tab_icon.dart",
    ]
    assert all(item["refs"] for item in payload["relevant_files"][:2])


def test_get_patch_plan_context_compact_source_output_is_json_serializable_and_bounded(tmp_path: Path):
    root = _source_fixture(tmp_path)

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Plan menu_line system_line menu_notifier menu_icon tab_icon",
            "project_path": str(root),
            "max_files": 3,
        },
        LibraryDocsService(),
    )

    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    assert len(payload["relevant_files"]) == 3
    assert len(encoded) < 32_000


def test_get_patch_plan_context_wires_changed_files_design_context_and_rejected_sources(tmp_path: Path):
    root = _source_fixture(tmp_path)
    design_context = {
        "artifact": "menu.pen",
        "summary": "Bottom sheet menu with compact icon buttons.",
        "components": ["bottom_sheet", "icon_button"],
        "dimensions": {"height": 320},
        "visual_rules": ["keep action order"],
    }

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Plan menu_line camera dialog bottom sheet",
            "project_path": str(root),
            "changed_files": ["lib/modules/tsd_browser/presentation/menu/menu_icon.dart"],
            "symbol_queries": ["MenuLine"],
            "design_context": design_context,
            "max_snippets": 1,
            "max_tokens": 200,
        },
        LibraryDocsService(),
    )

    assert payload["design_context"] == design_context
    assert any(item["file"].endswith("menu_icon.dart") for item in payload["relevant_files"])
    assert all(len(item["refs"]) <= 1 for item in payload["relevant_files"])
    assert payload["rejected_sources"] == [
        {
            "file": "docs/scandoc_web_camera_api_plan.md",
            "reason": "Demoted broad docs/source candidate because it matched generic words but none of the exact patch-planning terms.",
            "matched_terms": ["bottom", "camera", "dialog", "plan", "sheet"],
            "missing_exact_terms": ["MenuLine", "menu_line"],
        }
    ]
    assert isinstance(payload["token_estimate"], int)


def test_get_patch_plan_context_prioritizes_changed_files(tmp_path: Path):
    root = _source_fixture(tmp_path)

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Plan BrowserTSD menu bottom sheet with MenuLine and MenuIcon",
            "project_path": str(root),
            "changed_files": [
                "lib/modules/tsd_browser/presentation/menu/menu_icon.dart",
                "lib/modules/tsd_browser/presentation/menu/menu_line.dart",
            ],
            "symbol_queries": ["BrowserTSD", "MenuLine", "MenuIcon"],
            "max_files": 4,
        },
        LibraryDocsService(),
    )

    assert payload is not None
    files = [item["file"] for item in payload["relevant_files"]]
    assert files[:2] == [
        "lib/modules/tsd_browser/presentation/menu/menu_icon.dart",
        "lib/modules/tsd_browser/presentation/menu/menu_line.dart",
    ]
    assert payload["minimal_patch_path"][0]["files"][:2] == files[:2]


def test_get_patch_plan_context_builds_compact_implementation_map_for_flutter_fixture(tmp_path: Path):
    root = _dependency_fixture(tmp_path)

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Replace menu_line inline menu with showBottomDialog or PBBottomSheet.open bottom sheet",
            "project_path": str(root),
            "symbol_queries": ["MenuLine", "MenuIcon", "showBottomDialog", "PBBottomSheet.open"],
            "include_dependency_source": True,
            "max_files": 4,
        },
        LibraryDocsService(),
    )

    assert payload["status"] == "partial"
    assert payload["current_behavior"]
    assert {"behavior", "file", "start_line", "end_line", "symbol", "evidence", "confidence"}.issubset(payload["current_behavior"][0])
    assert payload["minimal_patch_path"]
    plan = payload["minimal_patch_path"][0]
    assert plan["step"] == "Replace inline menu rendering with bottom sheet opening"
    assert "lib/modules/tsd_browser/presentation/menu/menu_line.dart" in plan["files"]
    assert "MenuPageBuilder" in plan["find_patterns"]
    assert plan["change_type"] == "replace"
    assert plan["patch_level_plan"]
    assert plan["patch_level_plan"][0]["proposed_fragment"] is None
    assert plan["patch_level_plan"][0]["fragment_status"] == "omitted_for_safety"

    assert {
        "type": "command",
        "value": "flutter analyze",
        "why": "Static analysis should catch import/type errors after UI refactor.",
    } in payload["verification"]
    assert all({"risk", "severity", "source", "mitigation"}.issubset(item) for item in payload["risks_and_constraints"])
    assert any("generated files must not be edited" in item["risk"] for item in payload["risks_and_constraints"])
    assert any("missing APIs must not be invented" in item["risk"] for item in payload["risks_and_constraints"])
    assert payload["next_actions"]

    missing = next(item for item in payload["missing_symbols"] if item["symbol"] == "showBottomDialog")
    assert missing["result"] == "not_found"
    assert missing["nearest_alternatives"]
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    assert len(encoded) < 32_000


def test_get_patch_plan_context_reports_missing_symbol_from_symbol_queries(tmp_path: Path):
    root = _source_fixture(tmp_path)

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Use showBottomDialog for menu_line",
            "project_path": str(root),
            "symbol_queries": ["showBottomDialog"],
        },
        LibraryDocsService(),
    )

    assert payload is not None
    assert payload["missing_symbols"] == [
        {
            "symbol": "showBottomDialog",
            "searched_scopes": ["project"],
            "result": "not_found",
            "nearest_alternatives": [],
            "negative_evidence": "No exact symbol match found in project source.",
        }
    ]
    json.dumps(payload)


def test_get_patch_plan_context_finds_requested_dart_dependency_apis(tmp_path: Path):
    root = _dependency_fixture(tmp_path)

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Use ui_base PBBottomSheet.open PBButton PBIcon PBIcons for menu_line",
            "project_path": str(root),
            "symbol_queries": ["PBBottomSheet.open", "PBButton", "PBIcon", "PBIcons"],
            "include_dependency_source": True,
        },
        LibraryDocsService(),
    )

    symbols = {item["symbol"]: item for item in payload["existing_apis"]}
    assert {"PBBottomSheet.open", "PBButton", "PBIcon", "PBIcons"}.issubset(symbols)
    assert symbols["PBBottomSheet.open"]["kind"] == "dependency"
    assert symbols["PBBottomSheet.open"]["file"].endswith("/ui_base/lib/src/widgets/pb_bottomsheet.dart")
    assert symbols["PBBottomSheet.open"]["start_line"] >= 1
    assert symbols["PBBottomSheet.open"]["end_line"] >= symbols["PBBottomSheet.open"]["start_line"]
    assert symbols["PBBottomSheet.open"]["usage_example_file"] is None
    assert symbols["PBBottomSheet.open"]["usage_example_lines"] is None
    json.dumps(payload)


def test_get_patch_plan_context_does_not_report_project_root_as_dependency(tmp_path: Path):
    root = _dependency_fixture(tmp_path)
    config_path = root / ".dart_tool/package_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["packages"].append({"name": "nbo_menu", "rootUri": "..", "packageUri": "lib/"})
    config_path.write_text(json.dumps(config), encoding="utf-8")

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Use MenuLine and PBBottomSheet.open for menu_line",
            "project_path": str(root),
            "symbol_queries": ["MenuLine", "PBBottomSheet.open"],
            "include_dependency_source": True,
        },
        LibraryDocsService(),
    )

    assert payload is not None
    assert "PBBottomSheet.open" in {item["symbol"] for item in payload["existing_apis"]}
    assert all(item["symbol"] != "MenuLine" for item in payload["existing_apis"])


def test_get_patch_plan_context_does_not_scan_entire_pub_cache_for_dependency_symbols(tmp_path: Path):
    root = _dependency_fixture(tmp_path)

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Find PBCacheOnly from ui_base",
            "project_path": str(root),
            "symbol_queries": ["PBCacheOnly"],
            "include_dependency_source": True,
        },
        LibraryDocsService(),
    )

    assert all(item["symbol"] != "PBCacheOnly" for item in payload["existing_apis"])
    assert payload["missing_symbols"][0]["symbol"] == "PBCacheOnly"


def test_get_patch_plan_context_adds_dependency_api_as_missing_symbol_alternative(tmp_path: Path):
    root = _dependency_fixture(tmp_path)

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Use showBottomDialog or PBBottomSheet.open from ui_base for bottom sheet",
            "project_path": str(root),
            "symbol_queries": ["showBottomDialog", "PBBottomSheet.open"],
            "include_dependency_source": True,
        },
        LibraryDocsService(),
    )

    missing = next(item for item in payload["missing_symbols"] if item["symbol"] == "showBottomDialog")
    assert missing["searched_scopes"] == ["project", "dependency"]
    assert missing["result"] == "not_found"
    assert missing["nearest_alternatives"][0]["symbol"] == "PBBottomSheet.open"
    assert missing["nearest_alternatives"][0]["file"].endswith("/ui_base/lib/src/widgets/pb_bottomsheet.dart")


def test_get_patch_plan_context_nbo_menu_acceptance_fixture():
    root = Path(__file__).parent / "fixtures/patch_plan_context/nbo_menu"
    design_context = json.loads((root / "design/menu.pen.summary.json").read_text(encoding="utf-8"))
    query = (
        "Изменить Flutter UI menu_line: вместо inline меню открыть bottom sheet/dialog по дизайну menu.pen, "
        "использовать pole_base_kit/ui_base buttons/icons, сохранить "
        "screenshot/camera/tabs/ScanDoc/rating/info/logout/admin, убрать legacy Bluetooth RT40/MS300 QR buttons, "
        "сохранить needFlashLight/needBT/isEmulator semantics."
    )

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": query,
            "project_path": str(root),
            "symbol_queries": [
                "MenuLine",
                "MenuIcon",
                "SystemLine",
                "MenuNotifier",
                "TabIcon",
                "showBottomDialog",
                "PBBottomSheet.open",
                "PBButton",
                "PBIcon",
                "PBIcons",
            ],
            "design_context": design_context,
            "include_dependency_source": True,
            "max_files": 12,
        },
        LibraryDocsService(),
    )

    files = {item["file"] for item in payload["relevant_files"]}
    assert payload["design_context"] == design_context
    assert "lib/modules/tsd_browser/presentation/menu/menu_line.dart" in files
    assert "lib/modules/tsd_browser/presentation/menu/menu_icon.dart" in files
    assert "lib/modules/system_line/presentation/system_line.dart" in files
    assert "lib/modules/tsd_browser/presentation/menu/provider/menu_notifier.dart" in files
    assert "lib/modules/tsd_browser/presentation/browser_screen/widgets/available_tabs/tab_icon.dart" in files

    missing = {item["symbol"]: item for item in payload["missing_symbols"]}
    assert missing["showBottomDialog"]["result"] == "not_found"

    apis = {item["symbol"] for item in payload["existing_apis"]}
    assert {"PBBottomSheet.open", "PBButton", "PBIcon", "PBIcons"}.issubset(apis)

    assert payload["minimal_patch_path"]
    plan = payload["minimal_patch_path"][0]
    assert "bottom sheet" in plan["step"].lower()
    assert "_showRT40QRDialog" in plan["find_patterns"] or any("_showRT40QRDialog" in risk["risk"] for risk in payload["risks_and_constraints"])
    assert "_showMS300QRDialog" in plan["find_patterns"] or any("_showMS300QRDialog" in risk["risk"] for risk in payload["risks_and_constraints"])

    risks = "\n".join(item["risk"] for item in payload["risks_and_constraints"])
    assert "needFlashLight" in risks
    assert "needBT" in risks
    assert "isEmulator" in risks
    assert {
        "type": "command",
        "value": "flutter analyze",
        "why": "Static analysis should catch import/type errors after UI refactor.",
    } in payload["verification"]

    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    assert len(encoded) < 32_000
