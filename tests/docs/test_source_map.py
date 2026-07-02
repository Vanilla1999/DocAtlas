from __future__ import annotations

from docmancer.docs.domain.source_map import build_project_repo_map


def test_project_repo_map_extracts_static_source_facts_and_honors_budget(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "help_request_details_screen.dart").write_text(
        """
import 'package:flutter/material.dart';
import '../services/help_request_service.dart';

class HelpRequestDetailsScreen extends StatelessWidget {
  void reopenRequest() {
    final label = 'Вернуть в работу';
    final status = 'active';
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (lib / "help_service.py").write_text(
        """
from .repositories import HelpRepository

class HelpService:
    def create_request(self):
        return "Создать новый запрос"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    items = build_project_repo_map(tmp_path, question="Вернуть в работу HelpService", max_files=1, token_budget=180)

    assert [item["path"] for item in items] == ["lib/help_request_details_screen.dart"]
    item = items[0]
    assert item["source_class"] == "repo_map"
    assert item["language"] == "dart"
    assert item["line_start"] == 1
    assert item["line_end"] == item["line_count"]
    assert item["token_estimate"] <= 180
    assert item["imports"] == ["package:flutter/material.dart", "../services/help_request_service.dart"]
    assert {symbol["name"] for symbol in item["symbols"]} >= {"HelpRequestDetailsScreen", "reopenRequest"}
    assert any(symbol["kind"] == "class" and symbol["line_start"] == 4 for symbol in item["symbols"])
    assert item["string_literals"] == ["Вернуть в работу", "active"]
    assert item["source"] == {"source_class": "repo_map", "path": "lib/help_request_details_screen.dart", "title": "Source map: lib/help_request_details_screen.dart"}
    assert "Вернуть в работу" in item["content"]
