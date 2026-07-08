from __future__ import annotations

from pathlib import Path

from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.domain.code_graph import (
    build_code_graph_context_items,
    build_project_code_graph,
    code_graph_diagnostics,
    find_code_graph_paths,
    render_code_graph_path,
)
from docmancer.docs.domain.source_map import collect_project_source_facts
from docmancer.docs.service import LibraryDocsService


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
    _write(root / "lib/generated/GeneratedPluginRegistrant.dart", "class GeneratedPluginRegistrant {}")
    _write(
        root / "app/api.py",
        '''
from app.permissions import PermissionService

def check():
    return PermissionService()
''',
    )
    _write(
        root / "app/permissions.py",
        '''
class PermissionService:
    def can_reopen(self):
        return "active"
''',
    )


def _edge_tuples(graph):
    return sorted((edge.kind, edge.from_path, edge.to_path, edge.symbol, edge.confidence) for edge in graph.edges)


def test_code_graph_golden_source_facts_cover_dart_python_and_skip_generated(tmp_path: Path):
    _golden_help_requests_project(tmp_path)

    facts = collect_project_source_facts(
        tmp_path,
        question="Вернуть в работу HelpRequestsCubit HelpRequestsService PermissionService active GeneratedPluginRegistrant",
        max_files=10,
        token_budget=4000,
    )
    by_path = {item["path"]: item for item in facts}

    assert "lib/screens/help_request_screen.dart" in by_path
    assert "lib/cubit/help_requests_cubit.dart" in by_path
    assert "lib/services/help_requests_service.dart" in by_path
    assert "app/api.py" in by_path
    assert "app/permissions.py" in by_path
    assert "lib/generated/GeneratedPluginRegistrant.dart" not in by_path
    assert "Вернуть в работу" in by_path["lib/screens/help_request_screen.dart"]["string_literals"]
    assert "Вернуть в работу" in by_path["lib/screens/help_request_screen.dart"]["status_like_tokens"]
    assert "active" in by_path["app/permissions.py"]["string_literals"]
    assert "active" in by_path["app/permissions.py"]["status_like_tokens"]


def test_code_graph_golden_mixed_dart_python_graph_edges(tmp_path: Path):
    _golden_help_requests_project(tmp_path)

    graph = build_project_code_graph(
        tmp_path,
        question="Вернуть в работу HelpRequestsCubit HelpRequestsService PermissionService active",
        max_files=10,
        token_budget=4000,
    )
    file_paths = {node.path for node in graph.nodes if node.kind == "file"}
    symbol_names = {node.name for node in graph.nodes if node.kind == "symbol"}
    edges = _edge_tuples(graph)
    diagnostics = code_graph_diagnostics(graph)

    assert {
        "lib/screens/help_request_screen.dart",
        "lib/cubit/help_requests_cubit.dart",
        "lib/services/help_requests_service.dart",
        "app/api.py",
        "app/permissions.py",
    }.issubset(file_paths)
    assert "lib/generated/GeneratedPluginRegistrant.dart" not in file_paths
    assert {"HelpRequestScreen", "HelpRequestsCubit", "HelpRequestsService", "PermissionService"}.issubset(symbol_names)
    assert ("imports", "lib/screens/help_request_screen.dart", "lib/cubit/help_requests_cubit.dart", "../cubit/help_requests_cubit.dart", "exact") in edges
    assert ("imports", "lib/cubit/help_requests_cubit.dart", "lib/services/help_requests_service.dart", "../services/help_requests_service.dart", "exact") in edges
    assert ("imports", "app/api.py", "app/permissions.py", "app.permissions.PermissionService", "heuristic") in edges
    assert ("references", "lib/screens/help_request_screen.dart", "lib/cubit/help_requests_cubit.dart", "HelpRequestsCubit", "heuristic") in edges
    assert ("references", "lib/cubit/help_requests_cubit.dart", "lib/services/help_requests_service.dart", "HelpRequestsService", "heuristic") in edges
    assert ("references", "app/api.py", "app/permissions.py", "PermissionService", "heuristic") in edges
    assert diagnostics["unresolved_import_count"] == 0
    assert diagnostics["unresolved_reference_count"] >= 0


def test_code_graph_golden_patch_constraints_include_cautious_graph_hint(tmp_path: Path):
    _golden_help_requests_project(tmp_path)
    service = PatchConstraintsService(LibraryDocsService())

    packet = service.get_patch_constraints(
        question="Измени поведение Вернуть в работу",
        project_path=str(tmp_path),
        max_constraints=20,
        max_tokens=4000,
    )
    graph_constraints = [c for c in packet.constraints if any(ref.get("kind") == "code_graph" for ref in c.source_refs)]

    assert graph_constraints
    assert any("inspect" in c.instruction.lower() and "linked" in c.instruction.lower() for c in graph_constraints)
    assert not any("call graph" in c.instruction.lower() or "call graph" in c.evidence.lower() for c in graph_constraints)


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
