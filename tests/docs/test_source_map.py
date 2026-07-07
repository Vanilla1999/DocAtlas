from __future__ import annotations

from docmancer.docs.domain.source_map import (
    _find_symbol_match,
    _split_identifier,
    build_project_repo_map,
    build_project_source_evidence,
)


def test_split_identifier_splits_camel_case():
    assert _split_identifier("PermissionService") == "permission service"
    assert _split_identifier("getProjectContext") == "get project context"
    assert _split_identifier("_sendTicketTitleToChat") == "send ticket title to chat"


def test_split_identifier_splits_snake_case():
    assert _split_identifier("permission_service") == "permission service"
    assert _split_identifier("help_request_details_screen") == "help request details screen"


def test_find_symbol_match_exact_substring():
    match_type, score = _find_symbol_match("PermissionService", "class PermissionService implements GrantAuthority")
    assert match_type == "exact_substring"
    assert score == 1.0


def test_find_symbol_match_symbol_via_camel_case():
    match_type, score = _find_symbol_match("permission service", "class PermissionService implements GrantAuthority")
    assert match_type == "symbol"
    assert score >= 0.9


def test_find_symbol_match_symbol_via_snake_case():
    match_type, score = _find_symbol_match("send ticket title chat", "_sendTicketTitleToChat")
    assert match_type is not None


def test_find_symbol_match_no_match():
    match_type, score = _find_symbol_match("zzzxq", "class HelpService")
    assert match_type is None


def test_build_project_source_evidence_includes_match_type_and_confidence(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "permission_service.dart").write_text(
        """class PermissionService implements GrantAuthority {}"""
    )
    items = build_project_source_evidence(
        tmp_path,
        question="PermissionService grant authority",
        max_items=4,
        token_budget=700,
    )
    assert len(items) >= 1
    ev = next(item for item in items if item.get("evidence_class") == "source_snippet")
    assert ev.get("match_type") in ("exact_substring", "symbol")
    assert ev.get("confidence") in ("high", "medium")
    assert ev.get("confidence_score", 0) > 0


def test_build_project_source_evidence_finds_camel_case_from_nl(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "ticket_service.dart").write_text(
        """String _sendTicketTitleToChat(String title) { return title; }"""
    )
    items = build_project_source_evidence(
        tmp_path,
        question="send ticket title chat",
        max_items=4,
        token_budget=700,
    )
    assert any(
        item.get("match_type") in ("exact_substring", "symbol") and "ticket_service.dart" in item.get("path", "")
        for item in items
        if item.get("evidence_class") == "source_snippet"
    )


def test_build_project_source_evidence_absent_has_unknown_confidence(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("x = 1")
    items = build_project_source_evidence(
        tmp_path,
        question="nonexistent_function_name",
        max_items=4,
        token_budget=700,
    )
    absent = [item for item in items if item.get("evidence_class") == "absent_in_source"]
    if absent:
        assert absent[0].get("confidence") == "unknown"


def test_source_evidence_skips_generated_plugin_registrant(tmp_path):
    android = tmp_path / "android/app/src/main/java/io/flutter/plugins"
    android.mkdir(parents=True)
    (android / "GeneratedPluginRegistrant.java").write_text(
        "public final class GeneratedPluginRegistrant { public static void registerWith() {} }",
        encoding="utf-8",
    )
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "public_api.dart").write_text(
        "class PublicApi { void registerWithHost() {} }",
        encoding="utf-8",
    )

    items = build_project_source_evidence(tmp_path, question="GeneratedPluginRegistrant public API", max_items=8, token_budget=1000)
    paths = {item.get("path") for item in items if item.get("evidence_class") == "source_snippet"}

    assert "android/app/src/main/java/io/flutter/plugins/GeneratedPluginRegistrant.java" not in paths
    assert "lib/public_api.dart" in paths


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
