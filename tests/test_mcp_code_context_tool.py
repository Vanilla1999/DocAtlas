from __future__ import annotations

import json
from pathlib import Path

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool, project_tools
from docmancer.docs.service import LibraryDocsService
from docmancer.mcp.docs_server import TOOLS


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
    return root


def test_get_code_context_exposed_in_public_mcp_tools():
    names = {tool["name"] for tool in TOOLS}

    assert "get_code_context" in names
    assert "get_code_context" in [tool["name"] for tool in project_tools(TOOLS)]


def test_get_code_context_schema_contains_agentic_source_fields():
    tool = next(tool for tool in TOOLS if tool["name"] == "get_code_context")
    schema = tool["inputSchema"]
    properties = schema["properties"]

    assert schema["required"] == ["question", "project_path"]
    assert properties["changed_files"]["items"]["type"] == "string"
    assert properties["entry_symbols"]["items"]["type"] == "string"
    assert properties["max_hops"]["default"] == 2
    assert properties["max_files"]["default"] == 12
    assert properties["max_snippets"]["default"] == 20
    assert properties["max_lines_per_snippet"]["default"] == 80
    assert properties["output_mode"]["enum"] == ["answer", "compact", "debug", "full"]


def test_get_code_context_returns_answer_ready_real_source_snippets(tmp_path: Path):
    root = _tab_fixture(tmp_path)

    payload = handle_project_tool(
        "get_code_context",
        {
            "question": "How does tab navigation work?",
            "project_path": str(root),
            "entry_symbols": ["FlutterTabType", "TabBrowserNotifier"],
            "max_hops": 1,
            "max_files": 8,
            "max_snippets": 8,
            "output_mode": "answer",
        },
        LibraryDocsService(),
    )

    assert payload is not None
    assert payload["answer_available"] is True
    assert payload["answer_type"] == "source_context"
    assert payload["safe_to_answer"] is True
    assert "Use file paths and line ranges" in payload["agent_instruction"]
    assert payload["summary"]

    snippets = payload["snippets"]
    assert snippets
    assert all({"path", "start_line", "end_line", "language", "code"}.issubset(snippet) for snippet in snippets)
    assert any("enum FlutterTabType" in snippet["code"] for snippet in snippets)
    assert any("class TabBrowserNotifier" in snippet["code"] for snippet in snippets)
    assert all("GeneratedTabBrowserNotifier" not in snippet["code"] for snippet in snippets)

    chain = payload["source_chain"]
    assert chain
    assert all({"path", "start_line", "end_line", "why_selected"}.issubset(item) for item in chain)


def test_get_code_context_reference_expansion_follows_symbol_usage(tmp_path: Path):
    root = _tab_fixture(tmp_path)

    payload = handle_project_tool(
        "get_code_context",
        {
            "question": "Where is FlutterTabType used?",
            "project_path": str(root),
            "entry_symbols": ["FlutterTabType"],
            "max_hops": 1,
            "max_files": 8,
            "max_snippets": 8,
        },
        LibraryDocsService(),
    )

    paths = {snippet["path"] for snippet in payload["snippets"]}
    assert "lib/modules/tsd_browser/domain/model/tabs.dart" in paths
    assert any("tab_browser_notifier.dart" in path for path in paths)
    assert any("tsd_tab_controller.dart" in path for path in paths)
    assert payload["references"]


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
