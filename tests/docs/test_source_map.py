from __future__ import annotations

from docmancer.docs.domain.source_map import (
    _find_symbol_match,
    _split_identifier,
    build_project_repo_map,
    build_project_source_evidence,
    collect_project_source_facts,
    source_facts_diagnostics,
)
from docmancer.docs.domain.source_boundary import SourceBoundary, iter_bounded_source_files


def _source_facts_fixture(tmp_path):
    lib = tmp_path / "lib"
    cubit = lib / "cubit"
    generated = lib / "generated"
    app = tmp_path / "app"
    cubit.mkdir(parents=True)
    generated.mkdir(parents=True)
    app.mkdir()
    (lib / "screen.dart").write_text(
        """
import '../cubit/help_requests_cubit.dart';

class HelpRequestScreen {
  final title = "Вернуть в работу";
  void build() {
    HelpRequestsCubit();
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (cubit / "help_requests_cubit.dart").write_text(
        """
class HelpRequestsCubit {
  void reopen() {}
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (app / "service.py").write_text(
        """
from app.permissions import PermissionService

class TicketService:
    def reopen_request(self):
        return "active"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (generated / "GeneratedPluginRegistrant.dart").write_text(
        "class GeneratedPluginRegistrant {}\n",
        encoding="utf-8",
    )
    (generated / "screen.g.dart").write_text(
        "class GeneratedScreen {}\n",
        encoding="utf-8",
    )
    return tmp_path


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


def test_collect_project_source_facts_returns_python_and_dart_facts(tmp_path):
    root = _source_facts_fixture(tmp_path)

    items = collect_project_source_facts(root, question="Вернуть в работу TicketService HelpRequestScreen")

    paths = [item["path"] for item in items]
    assert "lib/screen.dart" in paths
    assert "app/service.py" in paths
    screen = next(item for item in items if item["path"] == "lib/screen.dart")
    service = next(item for item in items if item["path"] == "app/service.py")
    assert screen["source_class"] == "repo_map"
    assert screen["language"] == "dart"
    assert screen["imports"] == ["../cubit/help_requests_cubit.dart"]
    assert {symbol["name"] for symbol in screen["symbols"]} >= {"HelpRequestScreen", "build"}
    assert "HelpRequestsCubit" in screen["references"]
    assert "Вернуть в работу" in screen["string_literals"]
    assert service["language"] == "python"
    assert service["imports"] == ["app.permissions.PermissionService"]
    assert {symbol["name"] for symbol in service["symbols"]} >= {"TicketService", "reopen_request"}


def test_collect_project_source_facts_keeps_repo_map_shape_compatible(tmp_path):
    root = _source_facts_fixture(tmp_path)

    repo_map = build_project_repo_map(root, question="Вернуть в работу HelpRequestScreen", max_files=2, token_budget=4000)
    facts = collect_project_source_facts(root, question="Вернуть в работу HelpRequestScreen", max_files=2, token_budget=4000)

    assert facts == repo_map


def test_collect_project_source_facts_skips_generated_files(tmp_path):
    root = _source_facts_fixture(tmp_path)

    items = collect_project_source_facts(root, question="GeneratedPluginRegistrant GeneratedScreen HelpRequestScreen")

    paths = {item["path"] for item in items}
    assert "lib/screen.dart" in paths
    assert "lib/generated/GeneratedPluginRegistrant.dart" not in paths
    assert "lib/generated/screen.g.dart" not in paths


def test_collect_project_source_facts_skips_benchmark_runtime_artifacts(tmp_path):
    root = _source_facts_fixture(tmp_path)
    artifact = root / "eval/task_level/results/run/uv-cache/archive-v0/package/source.py"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("class RuntimeArtifact: pass\n", encoding="utf-8")

    items = collect_project_source_facts(
        root,
        question="RuntimeArtifact HelpRequestScreen",
        include_unmatched=True,
    )

    assert all(not item["path"].startswith("eval/task_level/results/") for item in items)


def test_source_boundary_loads_project_manifest_and_limits_roots(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "other").mkdir()
    (tmp_path / "app/main.py").write_text("class Included: pass\n", encoding="utf-8")
    (tmp_path / "other/ignored.py").write_text("class OutsideRoot: pass\n", encoding="utf-8")
    (tmp_path / "docmancer.yaml").write_text(
        "project:\n  source_roots: [app]\n  include_extensions: [.py]\n",
        encoding="utf-8",
    )

    items = collect_project_source_facts(
        tmp_path, question="Included OutsideRoot", include_unmatched=True
    )

    assert [item["path"] for item in items] == ["app/main.py"]


def test_source_boundary_applies_excludes_and_gitignore(tmp_path):
    for relative in ("src/keep.py", "src/excluded/drop.py", "src/ignored.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("class BoundaryFact: pass\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("src/ignored.py\n", encoding="utf-8")
    boundary = SourceBoundary(
        exclude_paths=("src/excluded/**",),
        gitignore_patterns=("src/ignored.py",),
    )

    paths = [
        path.relative_to(tmp_path).as_posix()
        for path in iter_bounded_source_files(
            tmp_path, boundary=boundary, supported_extensions=frozenset({".py"})
        )
    ]

    assert paths == ["src/keep.py"]


def test_source_boundary_gitignore_anchored_negation_only_reincludes_root_path(tmp_path):
    for relative in ("keep.py", "nested/keep.py", "drop.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("class BoundaryFact: pass\n", encoding="utf-8")
    boundary = SourceBoundary(gitignore_patterns=("*.py", "!/keep.py"))

    paths = [
        path.relative_to(tmp_path).as_posix()
        for path in iter_bounded_source_files(
            tmp_path, boundary=boundary, supported_extensions=frozenset({".py"})
        )
    ]

    assert paths == ["keep.py"]


def test_source_boundary_distinguishes_anchored_and_nonanchored_directories(tmp_path):
    for relative in ("ignored/root.py", "nested/ignored/nested.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("class BoundaryFact: pass\n", encoding="utf-8")

    anchored = SourceBoundary(gitignore_patterns=("/ignored/",))
    nonanchored = SourceBoundary(gitignore_patterns=("ignored/",))

    anchored_paths = [
        path.relative_to(tmp_path).as_posix()
        for path in iter_bounded_source_files(
            tmp_path, boundary=anchored, supported_extensions=frozenset({".py"})
        )
    ]
    nonanchored_paths = list(iter_bounded_source_files(
        tmp_path, boundary=nonanchored, supported_extensions=frozenset({".py"})
    ))

    assert anchored_paths == ["nested/ignored/nested.py"]
    assert nonanchored_paths == []


def test_source_boundary_preserves_legacy_positional_source_roots(tmp_path):
    source = tmp_path / "src/main.py"
    outside = tmp_path / "other/outside.py"
    source.parent.mkdir()
    outside.parent.mkdir()
    source.write_text("class Included: pass\n", encoding="utf-8")
    outside.write_text("class Outside: pass\n", encoding="utf-8")

    paths = [
        path.relative_to(tmp_path).as_posix()
        for path in iter_bounded_source_files(
            tmp_path,
            boundary=SourceBoundary(("src",)),
            supported_extensions=frozenset({".py"}),
        )
    ]

    assert paths == ["src/main.py"]


def test_source_boundary_invalid_project_manifest_fails_closed(tmp_path):
    source = tmp_path / "src/main.py"
    source.parent.mkdir()
    source.write_text("class MustNotLeak: pass\n", encoding="utf-8")
    (tmp_path / "docmancer.yaml").write_text(
        "project:\n  source_roots: [src]\n  max_scanned_files: 0\n",
        encoding="utf-8",
    )

    items = collect_project_source_facts(
        tmp_path, question="MustNotLeak", include_unmatched=True
    )

    assert items == []


def test_source_boundary_generated_paths_require_explicit_opt_in(tmp_path):
    generated = tmp_path / "artifacts/output.py"
    generated.parent.mkdir()
    generated.write_text("class GeneratedFact: pass\n", encoding="utf-8")
    boundary = SourceBoundary(generated_paths=("artifacts/**",))

    hidden = list(iter_bounded_source_files(
        tmp_path, boundary=boundary, supported_extensions=frozenset({".py"})
    ))
    included = list(iter_bounded_source_files(
        tmp_path,
        boundary=boundary,
        supported_extensions=frozenset({".py"}),
        include_generated=True,
    ))

    assert hidden == []
    assert included == [generated]


def test_source_map_includes_generated_path_for_explicit_artifact_question(tmp_path):
    generated = tmp_path / "generated/model.py"
    generated.parent.mkdir()
    generated.write_text("class GeneratedModel: pass\n", encoding="utf-8")

    items = collect_project_source_facts(
        tmp_path,
        question="Inspect the generated file GeneratedModel",
        include_unmatched=True,
    )

    assert [item["path"] for item in items] == ["generated/model.py"]


def test_source_boundary_never_follows_symlink_outside_project(tmp_path):
    outside = tmp_path.parent / "outside-source-boundary"
    outside.mkdir(exist_ok=True)
    (outside / "secret.py").write_text("class OutsideFact: pass\n", encoding="utf-8")
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)

    paths = list(iter_bounded_source_files(
        tmp_path, boundary=SourceBoundary(), supported_extensions=frozenset({".py"})
    ))

    assert paths == []


def test_source_boundary_enforces_file_byte_depth_and_deadline_budgets(tmp_path):
    for index in range(3):
        path = tmp_path / f"src/file_{index}.py"
        path.parent.mkdir(exist_ok=True)
        path.write_text("value = 'bounded'\n", encoding="utf-8")
    deep = tmp_path / "src/one/two/deep.py"
    deep.parent.mkdir(parents=True)
    deep.write_text("value = 'deep'\n", encoding="utf-8")

    limited = list(iter_bounded_source_files(
        tmp_path,
        boundary=SourceBoundary(max_scanned_files=1, max_directory_depth=2),
        supported_extensions=frozenset({".py"}),
    ))
    ticks = iter((0.0, 1.0, 1.0))
    expired = list(iter_bounded_source_files(
        tmp_path,
        boundary=SourceBoundary(scan_deadline_seconds=0.5),
        supported_extensions=frozenset({".py"}),
        clock=lambda: next(ticks),
    ))

    assert len(limited) == 1
    assert deep not in limited
    assert expired == []


def test_collect_project_source_facts_selection_score_favors_exact_question_term(tmp_path):
    root = _source_facts_fixture(tmp_path)

    items = collect_project_source_facts(root, question="HelpRequestScreen HelpRequestsCubit", max_files=3, token_budget=4000)

    assert items[0]["path"] == "lib/screen.dart"
    cubit = next(item for item in items if item["path"] == "lib/cubit/help_requests_cubit.dart")
    assert items[0]["selection_score"] > cubit["selection_score"]


def test_source_facts_diagnostics_contains_counts(tmp_path):
    root = _source_facts_fixture(tmp_path)
    items = collect_project_source_facts(root, question="Вернуть в работу TicketService HelpRequestScreen")

    diagnostics = source_facts_diagnostics(items)

    assert diagnostics["selected_files"] == len(items)
    assert diagnostics["token_estimate"] == sum(item["token_estimate"] for item in items)
    assert diagnostics["paths"] == [item["path"] for item in items]
    assert set(diagnostics["languages"]) == {"dart", "python"}
    assert diagnostics["symbol_count"] >= 4
    assert diagnostics["import_count"] >= 2
    assert diagnostics["reference_count"] >= 2


def test_collect_project_source_facts_honors_token_budget(tmp_path):
    root = _source_facts_fixture(tmp_path)

    all_items = collect_project_source_facts(root, question="Вернуть в работу TicketService HelpRequestScreen HelpRequestsCubit", token_budget=4000)
    limited = collect_project_source_facts(root, question="Вернуть в работу TicketService HelpRequestScreen HelpRequestsCubit", token_budget=1)

    assert len(all_items) > 1
    assert len(limited) == 1
