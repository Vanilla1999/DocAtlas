from __future__ import annotations

import hashlib
import json
from pathlib import Path

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool, project_tools
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import ALL_TOOLS, TOOLS


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
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _declare_source_members(root: Path, members: tuple[str, ...]) -> dict[str, bytes]:
    """Declare only fixture-authored local files; capture bytes before discovery."""
    original = {member: (root / member).read_bytes() for member in members}
    _write(root / "docatlas.project-docs.yaml", json.dumps({
        "schema_version": 1, "documents": [], "code_files": list(members),
    }))
    return original


def _assert_selected_source_evidence(payload, original: dict[str, bytes]) -> None:
    rows = payload["relevant_files"]
    assert rows
    files = [row["file"] for row in rows]
    assert len(files) == len(set(files))
    assert set(files).issubset(original)
    for row in rows:
        assert row["action"] == "read"
        assert row["refs"]
        lines = original[row["file"]].decode("utf-8").splitlines()
        for ref in row["refs"]:
            assert 1 <= ref["start_line"] <= ref["end_line"] <= len(lines)
            pattern = ref["locate_by_pattern"]
            assert pattern and pattern in "\n".join(lines[ref["start_line"] - 1:ref["end_line"]])
    behavior = {row["file"]: row for row in payload["current_behavior"]}
    assert len(behavior) == len(payload["current_behavior"])
    assert set(behavior) == set(files[:5])
    for path, row in behavior.items():
        assert row["confidence"] == "unknown"
        assert row["content_hash"] == "sha256:" + hashlib.sha256(original[path]).hexdigest()
        lines = original[path].decode("utf-8").splitlines()
        assert 1 <= row["start_line"] <= row["end_line"] <= len(lines)
        assert row["evidence"] and row["evidence"] in "\n".join(lines[row["start_line"] - 1:row["end_line"]])


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










def test_get_patch_plan_context_response_is_json_serializable():
    payload = handle_project_tool(
        "get_patch_plan_context",
        {"question": "Plan changing menu_line to bottom sheet"},
        LibraryDocsService(),
    )

    json.dumps(payload)


def test_get_patch_plan_context_finds_relevant_source_files_by_exact_terms(tmp_path: Path):
    root = _source_fixture(tmp_path)
    _write(
        root / "docatlas.project-docs.yaml",
        json.dumps({
            "schema_version": 1,
            "documents": [],
            "code_files": [
                "lib/modules/tsd_browser/presentation/menu/menu_line.dart",
                "lib/modules/system_line/presentation/system_line.dart",
                "lib/modules/tsd_browser/presentation/menu/provider/menu_notifier.dart",
            ],
        }),
    )

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


def test_get_patch_plan_context_normalizes_snake_case_and_pascal_case(tmp_path: Path, monkeypatch):
    root = _source_fixture(tmp_path)
    members = (
        "lib/modules/tsd_browser/presentation/menu/menu_icon.dart",
        "lib/modules/tsd_browser/presentation/browser_screen/widgets/available_tabs/tab_icon.dart",
    )
    original = _declare_source_members(root, members)
    service = LibraryDocsService()
    resolved_root = root.resolve()
    selected = {(resolved_root / member) for member in members}
    controls = {resolved_root / name for name in ("docatlas.project-docs.yaml", "docatlas.yaml", ".gitignore")}
    opened_sources = set()
    original_open = Path.open

    def scoped_open(path, *args, **kwargs):
        resolved = path.resolve()
        if resolved.is_relative_to(resolved_root):
            assert resolved in selected | controls, f"unselected fixture read: {path}"
        if path.suffix == ".dart":
            assert resolved in selected, f"unselected source read: {path}"
            opened_sources.add(resolved)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", scoped_open)

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Plan MenuIcon and TabIcon changes",
            "project_path": str(root),
            "symbol_queries": ["menu_icon", "tab_icon"],
        },
        service,
    )

    files = [item["file"] for item in payload["relevant_files"]]
    assert files[:2] == [
        "lib/modules/tsd_browser/presentation/menu/menu_icon.dart",
        "lib/modules/tsd_browser/presentation/browser_screen/widgets/available_tabs/tab_icon.dart",
    ]
    assert all(item["refs"] for item in payload["relevant_files"][:2])
    assert files == list(members)
    assert opened_sources == selected
    _assert_selected_source_evidence(payload, original)
    assert {member: (root / member).read_bytes() for member in members} == original


def test_get_patch_plan_context_compact_source_output_is_json_serializable_and_bounded(tmp_path: Path):
    root = _source_fixture(tmp_path)
    members = (
        "lib/modules/tsd_browser/presentation/menu/menu_line.dart",
        "lib/modules/system_line/presentation/system_line.dart",
        "lib/modules/tsd_browser/presentation/menu/provider/menu_notifier.dart",
        "lib/modules/tsd_browser/presentation/menu/menu_icon.dart",
        "lib/modules/tsd_browser/presentation/browser_screen/widgets/available_tabs/tab_icon.dart",
    )
    original = _declare_source_members(root, members)
    service = LibraryDocsService()
    arguments = {
        "question": "Plan menu_line system_line menu_notifier menu_icon tab_icon",
        "project_path": str(root),
    }
    wide = handle_project_tool("get_patch_plan_context", {**arguments, "max_files": 12}, service)
    assert len(wide["relevant_files"]) == len(members) > 3
    _assert_selected_source_evidence(wide, original)

    payload = handle_project_tool(
        "get_patch_plan_context",
        {**arguments, "max_files": 3},
        service,
    )

    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    assert len(payload["relevant_files"]) == 3
    assert len(encoded) < 32_000
    assert [row["file"] for row in payload["relevant_files"]] == [row["file"] for row in wide["relevant_files"][:3]]
    _assert_selected_source_evidence(payload, original)
    assert {member: (root / member).read_bytes() for member in members} == original

