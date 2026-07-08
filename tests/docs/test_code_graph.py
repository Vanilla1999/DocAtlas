from __future__ import annotations

import json

from docmancer.docs.domain.code_graph import (
    CodeGraph,
    CodeGraphEdge,
    CodeGraphNode,
    build_project_code_graph,
    build_code_graph_context_items,
    code_graph_diagnostics,
    code_graph_context_diagnostics,
    confidence_score_for,
    find_code_graph_paths,
    make_edge_id,
    make_file_node_id,
    make_symbol_node_id,
    render_code_graph_path,
)


def test_make_file_node_id_normalizes_windows_separators():
    assert make_file_node_id("lib\\a.dart") == "file:lib/a.dart"


def test_make_symbol_node_id_includes_path_line_and_symbol():
    assert make_symbol_node_id("lib\\a.dart", "TicketService", 12) == "symbol:lib/a.dart:12:TicketService"
    assert make_symbol_node_id("lib/a.dart", "TicketService") == "symbol:lib/a.dart:0:TicketService"


def test_make_edge_id_is_stable_and_changes_when_identity_changes():
    first = make_edge_id("contains", "file:lib/a.dart", "symbol:lib/a.dart:1:A")
    second = make_edge_id("contains", "file:lib/a.dart", "symbol:lib/a.dart:1:A")
    changed_kind = make_edge_id("references", "file:lib/a.dart", "symbol:lib/a.dart:1:A")
    changed_target = make_edge_id("contains", "file:lib/a.dart", "symbol:lib/a.dart:2:B")

    assert first == second
    assert first.startswith("edge:")
    assert len(first) == len("edge:") + 16
    assert first != changed_kind
    assert first != changed_target


def test_code_graph_to_context_dict_is_json_serializable():
    file_node = CodeGraphNode(
        id=make_file_node_id("lib/a.dart"),
        kind="file",
        name="a.dart",
        path="lib/a.dart",
        language="dart",
    )
    symbol_node = CodeGraphNode(
        id=make_symbol_node_id("lib/a.dart", "TicketService", 3),
        kind="symbol",
        name="TicketService",
        path="lib/a.dart",
        language="dart",
        line_start=3,
        line_end=5,
    )
    edge = CodeGraphEdge(
        id=make_edge_id("contains", file_node.id, symbol_node.id, symbol="TicketService", line_start=3),
        kind="contains",
        from_node_id=file_node.id,
        to_node_id=symbol_node.id,
        from_path="lib/a.dart",
        to_path="lib/a.dart",
        symbol="TicketService",
        line_start=3,
        confidence="exact",
        confidence_score=confidence_score_for("exact"),
        evidence="class TicketService",
    )
    graph = CodeGraph(
        nodes=[file_node, symbol_node],
        edges=[edge],
        diagnostics={"node_count": 2, "edge_count": 1},
    )

    payload = graph.to_context_dict()

    assert payload["nodes"][0]["id"] == "file:lib/a.dart"
    assert payload["edges"][0]["confidence"] == "exact"
    assert payload["diagnostics"] == {"node_count": 2, "edge_count": 1}
    json.dumps(payload)


def test_code_graph_lookup_helpers_group_by_id_and_source():
    file_node = CodeGraphNode(id="file:lib/a.dart", kind="file", name="a.dart", path="lib/a.dart")
    edge = CodeGraphEdge(id="edge:abc", kind="unresolved_reference", from_node_id=file_node.id, symbol="MissingApi")
    graph = CodeGraph(nodes=[file_node], edges=[edge])

    assert graph.node_by_id() == {file_node.id: file_node}
    assert graph.edges_by_from() == {file_node.id: [edge]}


def test_confidence_score_for_known_and_unknown_values():
    assert confidence_score_for("exact") == 1.0
    assert confidence_score_for("parser") == 0.9
    assert confidence_score_for("regex") == 0.7
    assert confidence_score_for("heuristic") == 0.45
    assert confidence_score_for("unresolved") == 0.1
    assert confidence_score_for("future") == 0.45


def test_mutable_metadata_defaults_are_not_shared():
    first_node = CodeGraphNode(id="file:a.py", kind="file", name="a.py", path="a.py")
    second_node = CodeGraphNode(id="file:b.py", kind="file", name="b.py", path="b.py")
    first_edge = CodeGraphEdge(id="edge:a", kind="references", from_node_id="file:a.py")
    second_edge = CodeGraphEdge(id="edge:b", kind="references", from_node_id="file:b.py")
    first_graph = CodeGraph(nodes=[], edges=[])
    second_graph = CodeGraph(nodes=[], edges=[])

    first_node.metadata["changed"] = True
    first_edge.metadata["changed"] = True
    first_graph.diagnostics["changed"] = True

    assert second_node.metadata == {}
    assert second_edge.metadata == {}
    assert second_graph.diagnostics == {}


def test_build_project_code_graph_links_python_local_import_and_reference(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "api.py").write_text(
        """
from app.service import TicketService

def route():
    return TicketService()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (app / "service.py").write_text(
        """
class TicketService:
    def reopen_request(self):
        return "active"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    graph = build_project_code_graph(tmp_path, question="TicketService route reopen_request")

    nodes = graph.node_by_id()
    assert "file:app/api.py" in nodes
    assert "file:app/service.py" in nodes
    ticket_node = next(node for node in graph.nodes if node.kind == "symbol" and node.name == "TicketService")
    assert ticket_node.id.startswith("symbol:app/service.py:")
    assert any(edge.kind == "contains" and edge.from_node_id == "file:app/service.py" and edge.to_node_id == ticket_node.id for edge in graph.edges)
    assert any(edge.kind == "imports" and edge.from_path == "app/api.py" and edge.to_path == "app/service.py" for edge in graph.edges)
    assert any(edge.kind == "references" and edge.from_path == "app/api.py" and edge.to_node_id == ticket_node.id for edge in graph.edges)
    assert graph.diagnostics["edge_count"] == len(graph.edges)
    assert graph.diagnostics["edge_kinds"]["contains"] >= 1


def test_build_project_code_graph_links_dart_relative_imports_and_references(tmp_path):
    screens = tmp_path / "lib" / "screens"
    cubit = tmp_path / "lib" / "cubit"
    services = tmp_path / "lib" / "services"
    screens.mkdir(parents=True)
    cubit.mkdir(parents=True)
    services.mkdir(parents=True)
    (screens / "help_request_screen.dart").write_text(
        """
import '../cubit/help_requests_cubit.dart';

class HelpRequestScreen {
  final label = "Вернуть в работу";

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
import '../services/help_requests_service.dart';

class HelpRequestsCubit {
  final service = HelpRequestsService();
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (services / "help_requests_service.dart").write_text(
        """
class HelpRequestsService {
  void reopenRequest() {}
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    graph = build_project_code_graph(
        tmp_path,
        question="HelpRequestScreen HelpRequestsCubit HelpRequestsService Вернуть в работу",
    )

    symbol_names = {node.name for node in graph.nodes if node.kind == "symbol"}
    assert {"HelpRequestScreen", "HelpRequestsCubit", "HelpRequestsService"}.issubset(symbol_names)
    assert any(edge.kind == "imports" and edge.from_path == "lib/screens/help_request_screen.dart" and edge.to_path == "lib/cubit/help_requests_cubit.dart" for edge in graph.edges)
    assert any(edge.kind == "imports" and edge.from_path == "lib/cubit/help_requests_cubit.dart" and edge.to_path == "lib/services/help_requests_service.dart" for edge in graph.edges)
    cubit_node = next(node for node in graph.nodes if node.name == "HelpRequestsCubit")
    service_node = next(node for node in graph.nodes if node.name == "HelpRequestsService")
    assert any(edge.kind == "references" and edge.from_path == "lib/screens/help_request_screen.dart" and edge.to_node_id == cubit_node.id for edge in graph.edges)
    assert any(edge.kind == "references" and edge.from_path == "lib/cubit/help_requests_cubit.dart" and edge.to_node_id == service_node.id for edge in graph.edges)
    screen_node = nodes_by_path(graph, "lib/screens/help_request_screen.dart")
    assert "Вернуть в работу" in screen_node.metadata["string_literals"]
    assert "Вернуть в работу" in screen_node.metadata["status_like_tokens"]


def test_build_project_code_graph_skips_generated_files(tmp_path):
    generated = tmp_path / "lib" / "generated"
    generated.mkdir(parents=True)
    (generated / "GeneratedPluginRegistrant.dart").write_text("class GeneratedPluginRegistrant {}\n", encoding="utf-8")
    (tmp_path / "lib" / "public_api.dart").write_text("class PublicApi {}\n", encoding="utf-8")

    graph = build_project_code_graph(tmp_path, question="PublicApi GeneratedPluginRegistrant")

    paths = {node.path for node in graph.nodes}
    assert "lib/public_api.dart" in paths
    assert "lib/generated/GeneratedPluginRegistrant.dart" not in paths


def test_build_project_code_graph_marks_unresolved_external_import(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "screen.dart").write_text(
        """
import 'package:external_pkg/widget.dart';

class HelpRequestScreen {}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    graph = build_project_code_graph(tmp_path, question="HelpRequestScreen external_pkg")

    edge = next(edge for edge in graph.edges if edge.kind == "unresolved_import")
    assert edge.confidence == "unresolved"
    assert edge.confidence_score == 0.1
    assert edge.metadata["import_value"] == "package:external_pkg/widget.dart"
    assert edge.metadata["external"] is True
    assert graph.diagnostics["unresolved_import_count"] == 1


def test_build_project_code_graph_invalid_root_returns_empty_graph(tmp_path):
    graph = build_project_code_graph(tmp_path / "missing", question="TicketService")

    assert graph.nodes == []
    assert graph.edges == []
    assert graph.diagnostics == {"status": "invalid_root"}


def nodes_by_path(graph: CodeGraph, path: str) -> CodeGraphNode:
    return next(node for node in graph.nodes if node.kind == "file" and node.path == path)


def test_build_code_graph_context_items_selects_screen_for_cubit_reference(tmp_path):
    graph = _dart_help_graph(tmp_path)

    items = build_code_graph_context_items(graph, question="Где используется HelpRequestsCubit?")

    assert items
    item = items[0]
    assert item["source_class"] == "code_graph"
    assert item["path"] == "lib/screens/help_request_screen.dart"
    assert "HelpRequestsCubit" in item["content"]
    assert "raw graph" not in item["content"].casefold()
    assert set(item["metadata"]["edge_kinds"]) & {"references", "imports"}
    assert item["source"] == {
        "source_class": "code_graph",
        "path": item["path"],
        "title": "Code graph: lib/screens/help_request_screen.dart",
    }


def test_build_code_graph_context_items_string_match_beats_connected_cubit(tmp_path):
    graph = _dart_help_graph(tmp_path)

    items = build_code_graph_context_items(graph, question="Где кнопка Вернуть в работу?", token_budget=1200)

    assert items
    assert items[0]["path"] == "lib/screens/help_request_screen.dart"
    assert "Вернуть в работу" in items[0]["content"]
    assert "Strings:" in items[0]["content"]
    if len(items) > 1:
        assert any(item["path"] == "lib/cubit/help_requests_cubit.dart" for item in items[1:])


def test_build_code_graph_context_items_external_import_does_not_dominate(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "screen.dart").write_text(
        """
import 'package:external_pkg/widget.dart';

class HelpRequestScreen {
  final label = "Вернуть в работу";
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (lib / "external_only.dart").write_text(
        """
import 'package:external_pkg/widget.dart';

class ExternalOnly {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    graph = build_project_code_graph(tmp_path, question="external_pkg Вернуть в работу HelpRequestScreen")

    items = build_code_graph_context_items(graph, question="external_pkg Вернуть в работу")

    assert items
    assert items[0]["path"] == "lib/screen.dart"
    external_only = next((item for item in items if item["path"] == "lib/external_only.dart"), None)
    if external_only:
        assert external_only["metadata"]["score"] < items[0]["metadata"]["score"]


def test_build_code_graph_context_items_respects_small_token_budget_and_stays_compact(tmp_path):
    graph = _dart_help_graph(tmp_path)

    items = build_code_graph_context_items(graph, question="HelpRequestsCubit Вернуть в работу", token_budget=35, max_items=8)

    assert items
    assert sum(item["token_estimate"] for item in items) <= 35
    assert all("class HelpRequestScreen {" not in item["content"] for item in items)
    assert all("void build()" not in item["content"] for item in items)
    assert all(len(item["metadata"]["edge_ids"]) <= 6 for item in items)


def test_code_graph_context_diagnostics_summarizes_items(tmp_path):
    graph = _dart_help_graph(tmp_path)
    items = build_code_graph_context_items(graph, question="HelpRequestsCubit Вернуть в работу")

    diagnostics = code_graph_context_diagnostics(items)

    assert diagnostics["selected_items"] == len(items)
    assert diagnostics["token_estimate"] == sum(item["token_estimate"] for item in items)
    assert diagnostics["paths"] == [item["path"] for item in items]
    assert "references" in diagnostics["edge_kinds"] or "imports" in diagnostics["edge_kinds"]
    assert diagnostics["confidence_summary"]


def _dart_help_graph(tmp_path):
    screens = tmp_path / "lib" / "screens"
    cubit = tmp_path / "lib" / "cubit"
    services = tmp_path / "lib" / "services"
    screens.mkdir(parents=True)
    cubit.mkdir(parents=True)
    services.mkdir(parents=True)
    (screens / "help_request_screen.dart").write_text(
        """
import '../cubit/help_requests_cubit.dart';

class HelpRequestScreen {
  final label = "Вернуть в работу";

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
import '../services/help_requests_service.dart';

class HelpRequestsCubit {
  final service = HelpRequestsService();
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (services / "help_requests_service.dart").write_text(
        """
class HelpRequestsService {
  void reopenRequest() {}
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return build_project_code_graph(
        tmp_path,
        question="HelpRequestScreen HelpRequestsCubit HelpRequestsService Вернуть в работу",
    )


def test_find_code_graph_paths_finds_screen_to_cubit_and_renders_edges(tmp_path):
    graph = _dart_help_graph(tmp_path)

    paths = find_code_graph_paths(graph, start_terms=["Вернуть в работу", "HelpRequestsCubit"], max_depth=2)

    assert paths
    rendered = [render_code_graph_path(path) for path in paths]
    assert any("lib/screens/help_request_screen.dart" in text and "lib/cubit/help_requests_cubit.dart" in text for text in rendered)
    assert any("--imports[exact]-->" in text or "--references[heuristic]-->" in text for text in rendered)
    assert all("call" not in path.explanation.casefold() for path in paths)


def test_find_code_graph_paths_can_reach_service_with_target_terms_and_depth_two(tmp_path):
    graph = _dart_help_graph(tmp_path)

    paths = find_code_graph_paths(
        graph,
        start_terms=["Вернуть в работу"],
        target_terms=["HelpRequestsService"],
        max_depth=2,
    )

    assert paths
    rendered = render_code_graph_path(paths[0])
    assert "lib/screens/help_request_screen.dart" in rendered
    assert "lib/services/help_requests_service.dart" in rendered
    assert "imports" in rendered or "references" in rendered


def test_find_code_graph_paths_respects_max_depth(tmp_path):
    graph = _dart_help_graph(tmp_path)

    paths = find_code_graph_paths(
        graph,
        start_terms=["Вернуть в работу"],
        target_terms=["HelpRequestsService"],
        max_depth=1,
    )

    assert not any("lib/services/help_requests_service.dart" in render_code_graph_path(path) for path in paths)


def test_find_code_graph_paths_ignores_unresolved_edges(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "screen.dart").write_text(
        """
import 'package:external_pkg/widget.dart';

class HelpRequestScreen {
  final label = "Вернуть в работу";
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    graph = build_project_code_graph(tmp_path, question="Вернуть в работу external_pkg")

    paths = find_code_graph_paths(graph, start_terms=["Вернуть в работу"], target_terms=["external_pkg"], max_depth=2)

    assert paths == []


def test_build_code_graph_context_items_includes_likely_paths_for_high_score_file(tmp_path):
    graph = _dart_help_graph(tmp_path)

    items = build_code_graph_context_items(graph, question="Где кнопка Вернуть в работу через HelpRequestsCubit?", token_budget=1200)

    assert items
    assert "Likely paths:" in items[0]["content"]
    assert "call chain" not in items[0]["content"].casefold()


def test_build_project_code_graph_resolves_dart_package_self_import_with_metadata(tmp_path):
    (tmp_path / "pubspec.yaml").write_text("name: my_app\n", encoding="utf-8")
    lib = tmp_path / "lib"
    (lib / "features").mkdir(parents=True)
    (lib / "screens").mkdir(parents=True)
    (lib / "features" / "a.dart").write_text("class FeatureA {}\n", encoding="utf-8")
    (lib / "screens" / "screen.dart").write_text(
        """
import 'package:my_app/features/a.dart';

class Screen {
  final feature = FeatureA();
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    graph = build_project_code_graph(tmp_path, question="FeatureA Screen")

    edge = next(edge for edge in graph.edges if edge.kind == "imports" and edge.from_path == "lib/screens/screen.dart")
    assert edge.to_path == "lib/features/a.dart"
    assert edge.confidence == "exact"
    assert edge.metadata["resolver"] == "dart_package_self"
    assert edge.metadata["external"] is False
    assert edge.metadata["confidence"] == "exact"
    assert "lib/features/a.dart" in edge.metadata["attempted_paths"]


def test_build_project_code_graph_marks_dart_external_package_unresolved_with_metadata(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "screen.dart").write_text(
        """
import 'dart:async';
import 'package:provider/provider.dart';

class Screen {}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    graph = build_project_code_graph(tmp_path, question="Screen provider async")

    unresolved = [edge for edge in graph.edges if edge.kind == "unresolved_import"]
    assert {edge.metadata["import_value"] for edge in unresolved} >= {"dart:async", "package:provider/provider.dart"}
    assert all(edge.metadata["external"] is True for edge in unresolved)
    assert all(edge.metadata["resolver"].startswith("dart_") for edge in unresolved)
    assert all(edge.metadata["confidence"] == "unresolved" for edge in unresolved)


def test_build_project_code_graph_resolves_python_dotted_import_forms(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "service.py").write_text("class TicketService: pass\n", encoding="utf-8")
    (app / "api.py").write_text(
        """
import app.service
from app.service import TicketService
from app import service
from .service import TicketService as RelativeTicketService

class Api:
    pass
""".strip()
        + "\n",
        encoding="utf-8",
    )

    graph = build_project_code_graph(tmp_path, question="Api TicketService service")

    import_edges = [edge for edge in graph.edges if edge.kind == "imports" and edge.from_path == "app/api.py"]
    assert import_edges
    assert all(edge.to_path == "app/service.py" for edge in import_edges)
    assert all(edge.confidence == "heuristic" for edge in import_edges)
    assert all(edge.metadata["resolver"].startswith("python_") for edge in import_edges)
    assert all(edge.metadata["external"] is False for edge in import_edges)


def test_build_project_code_graph_resolves_ts_extensionless_relative_import(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "foo.ts").write_text("export class Foo {}\n", encoding="utf-8")
    (src / "main.ts").write_text(
        """
import { Foo } from './foo';

export class Main {
  foo = new Foo();
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    graph = build_project_code_graph(tmp_path, question="Main Foo")

    edge = next(edge for edge in graph.edges if edge.kind == "imports" and edge.from_path == "src/main.ts")
    assert edge.to_path == "src/foo.ts"
    assert edge.confidence == "heuristic"
    assert edge.metadata["resolver"] == "ts_relative"
    assert edge.metadata["external"] is False
    assert "src/foo.ts" in edge.metadata["attempted_paths"]


def test_build_project_code_graph_does_not_pick_random_basename_when_import_ambiguous(tmp_path):
    src = tmp_path / "src"
    (src / "foo").mkdir(parents=True)
    (src / "main.ts").write_text("import { Foo } from './foo';\nclass Main {}\n", encoding="utf-8")
    (src / "foo.ts").write_text("export class FooTs {}\n", encoding="utf-8")
    (src / "foo" / "index.ts").write_text("export class FooIndex {}\n", encoding="utf-8")

    graph = build_project_code_graph(tmp_path, question="Main Foo")

    edge = next(edge for edge in graph.edges if edge.kind == "unresolved_import" and edge.from_path == "src/main.ts")
    assert edge.to_path is None
    assert edge.confidence == "unresolved"
    assert edge.metadata["candidate_count"] == 2
    assert set(edge.metadata["candidate_paths"]) == {"src/foo.ts", "src/foo/index.ts"}
    assert edge.metadata["reason"] == "ambiguous_local_import"


def test_code_graph_diagnostics_reports_counts_unresolved_and_is_deterministic(tmp_path):
    graph = _dart_help_graph(tmp_path)

    first = code_graph_diagnostics(graph)
    second = code_graph_diagnostics(graph)

    assert first == second
    assert first["status"] == "ok"
    assert first["graph_scope"] == "selected_files"
    assert first["node_count"] == len(graph.nodes)
    assert first["edge_count"] == len(graph.edges)
    assert first["file_node_count"] >= 3
    assert first["symbol_node_count"] >= 3
    assert first["selected_files"] <= 20
    assert len(first["selected_paths"]) <= 20
    assert "imports" in first["edge_kinds"]
    assert first["confidence_summary"]
    assert first["unresolved_import_count"] >= 0
    assert first["unresolved_reference_count"] >= 0
    assert "dart" in first["languages"]
    assert "not_call_graph" in first["limitations"]


def test_code_graph_diagnostics_caps_lists_and_excludes_source_text(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    full_source_text = "class VeryLongSecretSource { final value = 'do-not-leak-full-source'; }\n"
    for index in range(25):
        (lib / f"file_{index}.dart").write_text(full_source_text, encoding="utf-8")

    graph = build_project_code_graph(tmp_path, question="VeryLongSecretSource", max_files=30, token_budget=12000)
    diagnostics = code_graph_diagnostics(graph)
    text = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)

    assert len(diagnostics["selected_paths"]) <= 20
    assert full_source_text.strip() not in text
    assert "do-not-leak-full-source" not in text


def test_code_graph_context_diagnostics_includes_capped_score_reasons_by_path(tmp_path):
    graph = _dart_help_graph(tmp_path)
    items = build_code_graph_context_items(graph, question="HelpRequestsCubit Вернуть в работу", token_budget=1200)

    diagnostics = code_graph_context_diagnostics(items)

    assert diagnostics["selected_items"] == len(items)
    assert diagnostics["paths"] == [item["path"] for item in items]
    assert diagnostics["score_reasons_by_path"]
    assert all(len(reasons) <= 8 for reasons in diagnostics["score_reasons_by_path"].values())
    assert diagnostics == code_graph_context_diagnostics(items)
