from __future__ import annotations

from pathlib import Path

from docmancer.docs.domain.code_graph import (
    build_code_graph_context_items,
    build_project_code_graph,
    code_graph_diagnostics,
    find_code_graph_paths,
    render_code_graph_path,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _golden_help_requests_project(root: Path) -> None:
    _write(
        root / "lib/screens/help_request_screen.dart",
        '''
import '../cubit/help_requests_cubit.dart';

class HelpRequestScreen {
  final label = "Вернуть в работу";

  void build() {
    HelpRequestsCubit();
  }
}
''',
    )
    _write(
        root / "lib/cubit/help_requests_cubit.dart",
        '''
import '../services/help_requests_service.dart';

class HelpRequestsCubit {
  final service = HelpRequestsService();
}
''',
    )
    _write(
        root / "lib/services/help_requests_service.dart",
        '''
class HelpRequestsService {
  void reopenRequest() {}
}
''',
    )


def _edge_tuples(graph):
    return sorted((edge.kind, edge.from_path, edge.to_path, edge.symbol, edge.confidence) for edge in graph.edges)


def test_code_graph_golden_help_requests_graph_shape(tmp_path: Path):
    _golden_help_requests_project(tmp_path)

    graph = build_project_code_graph(
        tmp_path,
        question="Вернуть в работу HelpRequestsCubit HelpRequestsService",
        max_files=10,
        token_budget=4000,
    )

    file_paths = sorted(node.path for node in graph.nodes if node.kind == "file")
    symbol_names = sorted(node.name for node in graph.nodes if node.kind == "symbol")
    edges = _edge_tuples(graph)

    assert file_paths == [
        "lib/cubit/help_requests_cubit.dart",
        "lib/screens/help_request_screen.dart",
        "lib/services/help_requests_service.dart",
    ]
    assert symbol_names == [
        "HelpRequestScreen",
        "HelpRequestsCubit",
        "HelpRequestsService",
        "build",
        "reopenRequest",
    ]
    assert ("imports", "lib/screens/help_request_screen.dart", "lib/cubit/help_requests_cubit.dart", "../cubit/help_requests_cubit.dart", "exact") in edges
    assert ("imports", "lib/cubit/help_requests_cubit.dart", "lib/services/help_requests_service.dart", "../services/help_requests_service.dart", "exact") in edges
    assert ("references", "lib/screens/help_request_screen.dart", "lib/cubit/help_requests_cubit.dart", "HelpRequestsCubit", "heuristic") in edges
    assert ("references", "lib/cubit/help_requests_cubit.dart", "lib/services/help_requests_service.dart", "HelpRequestsService", "heuristic") in edges
    assert not any("call" in edge.kind for edge in graph.edges)


def test_code_graph_golden_help_requests_context_and_diagnostics(tmp_path: Path):
    _golden_help_requests_project(tmp_path)
    graph = build_project_code_graph(
        tmp_path,
        question="Где используется кнопка Вернуть в работу через HelpRequestsCubit и HelpRequestsService?",
        max_files=10,
        token_budget=4000,
    )

    items = build_code_graph_context_items(
        graph,
        question="Где используется кнопка Вернуть в работу через HelpRequestsCubit и HelpRequestsService?",
        token_budget=1800,
        max_items=3,
    )
    diagnostics = code_graph_diagnostics(graph)

    assert [item["path"] for item in items] == [
        "lib/screens/help_request_screen.dart",
        "lib/cubit/help_requests_cubit.dart",
        "lib/services/help_requests_service.dart",
    ]
    assert items[0]["metadata"]["score"] > items[1]["metadata"]["score"] > items[2]["metadata"]["score"]
    assert any(reason["reason"] == "string_or_status_match" for reason in items[0]["metadata"]["score_breakdown"])
    assert "Likely paths:" in items[0]["content"]
    assert "call chain" not in items[0]["content"].lower()
    assert diagnostics["node_count"] == 8
    assert diagnostics["file_node_count"] == 3
    assert diagnostics["symbol_node_count"] == 5
    assert diagnostics["edge_kinds"] == {"contains": 5, "imports": 2, "references": 4, "unresolved_reference": 2}
    assert diagnostics["unresolved_import_count"] == 0
    assert diagnostics["unresolved_reference_count"] == 2
    assert diagnostics["selected_paths"] == [
        "lib/screens/help_request_screen.dart",
        "lib/cubit/help_requests_cubit.dart",
        "lib/services/help_requests_service.dart",
    ]


def test_code_graph_golden_help_requests_likely_path_rendering(tmp_path: Path):
    _golden_help_requests_project(tmp_path)
    graph = build_project_code_graph(
        tmp_path,
        question="Вернуть в работу HelpRequestsService",
        max_files=10,
        token_budget=4000,
    )

    paths = find_code_graph_paths(
        graph,
        start_terms=["Вернуть в работу"],
        target_terms=["HelpRequestsService"],
        max_depth=2,
        max_paths=3,
    )

    assert paths
    rendered = render_code_graph_path(paths[0])
    assert rendered == "\n".join(
        [
            "lib/screens/help_request_screen.dart",
            "  --imports[exact]-->",
            "lib/cubit/help_requests_cubit.dart",
            "  --imports[exact]-->",
            "lib/services/help_requests_service.dart",
        ]
    )
    assert paths[0].explanation in {
        "Linked through local import edge.",
        "Likely implementation path based on local imports/references.",
    }
