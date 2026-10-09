from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from docmancer.docs.domain.source_map import (
    _find_symbol_match,
    _split_identifier,
    build_project_repo_map,
    build_project_source_evidence,
    collect_project_source_facts,
    source_facts_diagnostics,
)
from docmancer.docs.domain.source_boundary import SourceBoundary, iter_bounded_source_files


def _declare_code_files(root, *paths):
    # These are explicit fixture members, not a discovered recursive source grant.
    (root / "docatlas.project-docs.yaml").write_text(
        json.dumps({"schema_version": 1, "documents": [], "code_files": list(paths)}),
        encoding="utf-8",
    )


def _observe_source_reads(monkeypatch, root):
    original_read_text = Path.read_text
    observed = {}

    def read_text(path, *args, **kwargs):
        value = original_read_text(path, *args, **kwargs)
        if path.is_relative_to(root) and path.suffix in {".py", ".dart", ".java"}:
            observed.setdefault(path.relative_to(root).as_posix(), []).append(
                sha256(value.encode("utf-8")).hexdigest()
            )
        return value

    monkeypatch.setattr(Path, "read_text", read_text)
    return observed


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
    _declare_code_files(tmp_path, "lib/screen.dart", "lib/cubit/help_requests_cubit.dart", "app/service.py")
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


def test_build_project_source_evidence_includes_match_type_and_confidence(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "permission_service.dart").write_text(
        """class PermissionService implements GrantAuthority {}"""
    )
    (lib / "unlisted.dart").write_text("class PermissionService {}\n", encoding="utf-8")
    declared_path = "lib/permission_service.dart"
    source_bytes = (tmp_path / declared_path).read_bytes()
    observed = _observe_source_reads(monkeypatch, tmp_path)
    assert build_project_source_evidence(tmp_path, question="PermissionService grant authority") == []
    assert observed == {}
    _declare_code_files(tmp_path, declared_path)
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
    assert ev["symbols"] == [
        {"kind": "class", "name": "PermissionService", "line_start": 1, "line_end": 1}
    ]
    assert observed == {declared_path: [sha256(source_bytes).hexdigest()]}
    assert ev["path"] == ev["source"]["path"] == declared_path
    assert ev["line_start"] == ev["line_end"] == 1
    assert ev["source"]["line_start"] == ev["source"]["line_end"] == 1
    assert ev["snippet"].encode("utf-8") == source_bytes
    assert sha256(ev["snippet"].encode("utf-8")).hexdigest() == observed[declared_path][0]


def test_named_gate_source_evidence_exposes_declaration_metadata(tmp_path, monkeypatch):
    relative = "lib/modules/sync/application/offline_sync_gate.dart"
    source = tmp_path / relative
    source.parent.mkdir(parents=True)
    declaration = "class OfflineSyncGate {}\n"
    source.write_text(declaration, encoding="utf-8")
    # An unlisted declaration cannot supply evidence or consume the term pool.
    unlisted = tmp_path / "lib/unlisted.dart"
    unlisted.write_text(declaration, encoding="utf-8")
    observed = _observe_source_reads(monkeypatch, tmp_path)
    assert build_project_source_evidence(tmp_path, question="OfflineSyncGate") == []
    assert observed == {}
    _declare_code_files(tmp_path, relative)

    items = build_project_source_evidence(
        tmp_path, question="OfflineSyncGate", max_items=4, token_budget=700,
    )

    match = next(item for item in items if item.get("path") == relative)
    assert match["symbols"][0]["name"] == "OfflineSyncGate"
    assert match["line_start"] == 1
    assert observed == {relative: [sha256(declaration.encode("utf-8")).hexdigest()]}

    # Crossing the former eight-match cutoff must preserve this declaration.
    # Only its source coordinate changes when earlier uses are prepended.
    for earlier_uses in (8, 16):
        prefix = "".join(
            f"final gate_{index} = OfflineSyncGate();\n"
            for index in range(earlier_uses)
        )
        padded = prefix + declaration
        source.write_text(padded, encoding="utf-8")
        observed.clear()
        items = build_project_source_evidence(
            tmp_path, question="OfflineSyncGate", max_items=4, token_budget=700,
        )
        assert [(item["path"], item["line_start"]) for item in items] == [
            (relative, earlier_uses + 1), (relative, 1),
        ]
        assert items[0]["symbols"][0]["name"] == match["symbols"][0]["name"]
        assert items[0]["snippet"] == match["snippet"] == declaration.strip()
        assert observed == {relative: [sha256(padded.encode("utf-8")).hexdigest()]}


def test_build_project_source_evidence_finds_camel_case_from_nl(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "ticket_service.dart").write_text(
        """String _sendTicketTitleToChat(String title) { return title; }"""
    )
    _declare_code_files(tmp_path, "lib/ticket_service.dart")
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
    _declare_code_files(tmp_path, "src/main.py")
    items = build_project_source_evidence(
        tmp_path,
        question="nonexistent_function_name",
        max_items=4,
        token_budget=700,
    )
    absent = [item for item in items if item.get("evidence_class") == "absent_in_source"]
    assert absent
    if absent:
        assert absent[0].get("confidence") == "unknown"


def test_source_evidence_skips_generated_plugin_registrant(tmp_path, monkeypatch):
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

    _declare_code_files(tmp_path, "lib/public_api.dart")
    observed = _observe_source_reads(monkeypatch, tmp_path)
    items = build_project_source_evidence(tmp_path, question="GeneratedPluginRegistrant public API", max_items=8, token_budget=1000)
    paths = {item.get("path") for item in items if item.get("evidence_class") == "source_snippet"}

    assert "android/app/src/main/java/io/flutter/plugins/GeneratedPluginRegistrant.java" not in paths
    assert "lib/public_api.dart" in paths
    assert set(observed) == {"lib/public_api.dart"}
    observed.clear()
    _declare_code_files(
        tmp_path, "lib/public_api.dart",
        "android/app/src/main/java/io/flutter/plugins/GeneratedPluginRegistrant.java",
    )
    denied = build_project_source_evidence(tmp_path, question="GeneratedPluginRegistrant public API")
    assert denied == []
    assert observed == {}


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

    _declare_code_files(tmp_path, "lib/help_request_details_screen.dart", "lib/help_service.py")
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

    assert facts
    assert facts == repo_map


def test_collect_project_source_facts_skips_generated_files(tmp_path, monkeypatch):
    root = _source_facts_fixture(tmp_path)
    observed = _observe_source_reads(monkeypatch, root)

    items = collect_project_source_facts(root, question="GeneratedPluginRegistrant GeneratedScreen HelpRequestScreen")

    paths = {item["path"] for item in items}
    assert "lib/screen.dart" in paths
    assert "lib/generated/GeneratedPluginRegistrant.dart" not in paths
    assert "lib/generated/screen.g.dart" not in paths
    assert set(observed) == {"lib/screen.dart", "lib/cubit/help_requests_cubit.dart", "app/service.py"}
    for generated in ("lib/generated/GeneratedPluginRegistrant.dart", "lib/generated/screen.g.dart"):
        observed.clear()
        boundary = replace(SourceBoundary.from_project(root), code_files=("lib/screen.dart", generated))
        denied = collect_project_source_facts(root, question="HelpRequestScreen", source_boundary=boundary)
        assert denied == []
        assert observed == {}


def test_collect_project_source_facts_skips_benchmark_runtime_artifacts(tmp_path, monkeypatch):
    root = _source_facts_fixture(tmp_path)
    artifact = root / "eval/task_level/results/run/uv-cache/archive-v0/package/source.py"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("class RuntimeArtifact: pass\n", encoding="utf-8")
    observed = _observe_source_reads(monkeypatch, root)

    items = collect_project_source_facts(
        root,
        question="RuntimeArtifact HelpRequestScreen",
        include_unmatched=True,
    )

    assert items
    assert all(not item["path"].startswith("eval/task_level/results/") for item in items)
    assert set(observed) == {"lib/screen.dart", "lib/cubit/help_requests_cubit.dart", "app/service.py"}
    observed.clear()
    boundary = replace(
        SourceBoundary.from_project(root),
        code_files=("lib/screen.dart", "eval/task_level/results/run/uv-cache/archive-v0/package/source.py"),
    )
    denied = collect_project_source_facts(
        root, question="RuntimeArtifact HelpRequestScreen", include_unmatched=True, source_boundary=boundary,
    )
    assert denied == []
    assert observed == {}


def test_source_boundary_loads_project_manifest_and_limits_roots(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "other").mkdir()
    (tmp_path / "app/main.py").write_text("class Included: pass\n", encoding="utf-8")
    (tmp_path / "other/ignored.py").write_text("class OutsideRoot: pass\n", encoding="utf-8")
    _declare_code_files(tmp_path, "app/main.py")
    (tmp_path / "docatlas.yaml").write_text(
        "project:\n  source_roots: [app]\n  include_extensions: [.py]\n",
        encoding="utf-8",
    )

    items = collect_project_source_facts(
        tmp_path, question="Included OutsideRoot", include_unmatched=True
    )

    assert [item["path"] for item in items] == ["app/main.py"]
    boundary = SourceBoundary.from_project(tmp_path)
    assert boundary.source_roots == ("app",)
    assert boundary.code_files == ("app/main.py",)
    assert collect_project_source_facts(
        tmp_path, question="Included OutsideRoot", include_unmatched=True,
        source_boundary=replace(boundary, code_files=("app/main.py", "other/ignored.py")),
    ) == []


def test_source_boundary_applies_excludes_and_gitignore(tmp_path):
    for relative in ("src/keep.py", "src/excluded/drop.py", "src/ignored.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("class BoundaryFact: pass\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("src/ignored.py\n", encoding="utf-8")
    boundary = SourceBoundary(
        exclude_paths=("src/excluded/**",),
        gitignore_patterns=("src/ignored.py",),
        code_files=("src/keep.py",),
    )

    paths = [
        path.relative_to(tmp_path).as_posix()
        for path in iter_bounded_source_files(
            tmp_path, boundary=boundary, supported_extensions=frozenset({".py"})
        )
    ]

    assert paths == ["src/keep.py"]
    for denied in ("src/excluded/drop.py", "src/ignored.py"):
        assert list(iter_bounded_source_files(
            tmp_path, boundary=replace(boundary, code_files=("src/keep.py", denied)),
            supported_extensions=frozenset({".py"}),
        )) == []


def test_source_boundary_gitignore_anchored_negation_only_reincludes_root_path(tmp_path):
    for relative in ("keep.py", "nested/keep.py", "drop.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("class BoundaryFact: pass\n", encoding="utf-8")
    boundary = SourceBoundary(gitignore_patterns=("*.py", "!/keep.py"), code_files=("keep.py",))

    paths = [
        path.relative_to(tmp_path).as_posix()
        for path in iter_bounded_source_files(
            tmp_path, boundary=boundary, supported_extensions=frozenset({".py"})
        )
    ]

    assert paths == ["keep.py"]
    for denied in ("nested/keep.py", "drop.py"):
        assert list(iter_bounded_source_files(
            tmp_path, boundary=replace(boundary, code_files=("keep.py", denied)),
            supported_extensions=frozenset({".py"}),
        )) == []


def test_source_boundary_distinguishes_anchored_and_nonanchored_directories(tmp_path):
    for relative in ("ignored/root.py", "nested/ignored/nested.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("class BoundaryFact: pass\n", encoding="utf-8")

    anchored = SourceBoundary(gitignore_patterns=("/ignored/",), code_files=("nested/ignored/nested.py",))
    nonanchored = SourceBoundary(gitignore_patterns=("ignored/",), code_files=("nested/ignored/nested.py",))

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
    assert list(iter_bounded_source_files(
        tmp_path, boundary=replace(anchored, code_files=("ignored/root.py",)),
        supported_extensions=frozenset({".py"}),
    )) == []


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
            boundary=SourceBoundary(("src",), code_files=("src/main.py",)),
            supported_extensions=frozenset({".py"}),
        )
    ]

    assert paths == ["src/main.py"]
    assert list(iter_bounded_source_files(
        tmp_path, boundary=SourceBoundary(("src",), code_files=("src/main.py", "other/outside.py")),
        supported_extensions=frozenset({".py"}),
    )) == []


def test_source_boundary_invalid_project_manifest_fails_closed(tmp_path):
    source = tmp_path / "src/main.py"
    source.parent.mkdir()
    source.write_text("class MustNotLeak: pass\n", encoding="utf-8")
    _declare_code_files(tmp_path, "src/main.py")
    (tmp_path / "docatlas.yaml").write_text(
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
    boundary = SourceBoundary(generated_paths=("artifacts/**",), code_files=("artifacts/output.py",))

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
    assert list(iter_bounded_source_files(
        tmp_path, boundary=boundary, supported_extensions=frozenset({".py"}), include_generated="true",
    )) == []


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
        tmp_path, boundary=SourceBoundary(code_files=("linked/secret.py",)), supported_extensions=frozenset({".py"})
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
        boundary=SourceBoundary(max_scanned_files=1, max_directory_depth=2, code_files=("src/file_0.py",)),
        supported_extensions=frozenset({".py"}),
    ))
    ticks = iter((0.0, 1.0, 1.0))
    expired = list(iter_bounded_source_files(
        tmp_path,
        boundary=SourceBoundary(scan_deadline_seconds=0.5, code_files=("src/file_0.py",)),
        supported_extensions=frozenset({".py"}),
        clock=lambda: next(ticks),
    ))

    assert len(limited) == 1
    assert deep not in limited
    assert expired == []
    for boundary in (
        SourceBoundary(max_scanned_files=1, code_files=("src/file_0.py", "src/file_1.py")),
        SourceBoundary(max_directory_depth=2, code_files=("src/one/two/deep.py",)),
        SourceBoundary(max_file_bytes=1, code_files=("src/file_0.py",)),
        SourceBoundary(max_scanned_bytes=1, code_files=("src/file_0.py",)),
    ):
        assert list(iter_bounded_source_files(
            tmp_path, boundary=boundary, supported_extensions=frozenset({".py"}),
        )) == []


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
