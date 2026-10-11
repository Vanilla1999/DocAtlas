from __future__ import annotations

import json
from pathlib import Path

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool, project_tools
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import ALL_TOOLS, TOOLS


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _tab_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "app"
    _write(
        root / "lib/modules/tsd_browser/domain/model/tabs.dart",
        """
enum FlutterTabType {
  helpChat,
  web,
}

class BaseTab {
  final FlutterTabType type;
  BaseTab(this.type);
}
""".strip(),
    )
    _write(
        root / "lib/modules/tsd_browser/presentation/browser_screen/browser_tsd/tab_provider/tab_browser_notifier.dart",
        """
import '../../../../domain/model/tabs.dart';
import '../tsd_tab_controller.dart';

class TabBrowserNotifier {
  final TSDTabController controller;

  TabBrowserNotifier(this.controller);

  void openHelpChat() {
    controller.switchTo(FlutterTabType.helpChat);
  }

  void openWeb() {
    controller.switchTo(FlutterTabType.web);
  }
}
""".strip(),
    )
    _write(
        root / "lib/modules/tsd_browser/presentation/browser_screen/browser_tsd/tsd_tab_controller.dart",
        """
import '../../../domain/model/tabs.dart';

class TSDTabController {
  FlutterTabType current = FlutterTabType.web;

  void switchTo(FlutterTabType type) {
    current = type;
  }
}
""".strip(),
    )
    _write(root / "lib/generated/tabs.g.dart", "class GeneratedTabBrowserNotifier {}")
    _write(root / "lib/modules/profile/tab_badge_key.dart", "class TabBadgeKey {}")
    _write(root / "lib/downloaded_files/downloaded_files_sh.dart", "class DownloadedFilesSh {}")
    return root






def test_get_code_context_filters_unconnected_generic_keyword_matches(tmp_path: Path):
    root = _tab_fixture(tmp_path)

    payload = handle_project_tool(
        "get_code_context",
        {
            "question": "How does tab navigation work in tsd_browser?",
            "project_path": str(root),
            "entry_symbols": ["TabBrowserNotifier"],
            "max_hops": 1,
            "max_files": 8,
            "max_snippets": 8,
        },
        LibraryDocsService(),
    )

    paths = {item["path"] for item in payload["source_chain"]}
    assert "lib/modules/profile/tab_badge_key.dart" not in paths
    assert "lib/downloaded_files/downloaded_files_sh.dart" not in paths
    assert all(item["connection_reason"] != "generic_keyword_match" for item in payload["source_chain"])


def test_get_code_context_navigation_only_when_no_source_snippets(tmp_path: Path):
    root = tmp_path / "empty"
    root.mkdir()

    payload = handle_project_tool(
        "get_code_context",
        {"question": "How does tab navigation work?", "project_path": str(root)},
        LibraryDocsService(),
    )

    assert payload["answer_available"] is False
    assert payload["answer_type"] == "navigation_only"
    assert payload["safe_to_answer"] is False
    assert payload["required_next_step"] == "read_or_search_suggested_sources"
    assert payload["files_to_read"] == []
    assert payload["search_queries"]


def test_get_code_context_response_is_json_serializable(tmp_path: Path):
    root = _tab_fixture(tmp_path)

    payload = handle_project_tool(
        "get_code_context",
        {"question": "How does tab navigation work?", "project_path": str(root)},
        LibraryDocsService(),
    )

    json.dumps(payload)
