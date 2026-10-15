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


