from __future__ import annotations

from pathlib import Path

import docmancer.docs.patch_plan_context as patch_plan_context
from docmancer.docs.patch_plan_context import build_patch_plan_context


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_patch_plan_context_uses_code_graph_hints_for_imported_cubit(tmp_path: Path):
    root = tmp_path / "repo"
    _write(
        root / "lib/screens/help_request_screen.dart",
        """
import '../cubit/help_requests_cubit.dart';

class HelpRequestScreen {
  void build() {
    HelpRequestsCubit();
  }
}
""".strip()
        + "\n",
    )
    _write(root / "lib/cubit/help_requests_cubit.dart", "class HelpRequestsCubit {}\n")

    payload = build_patch_plan_context(
        "Где используется HelpRequestsCubit?",
        project_path=str(root),
        max_files=8,
        max_tokens=4000,
        output_mode="debug",
    )

    files = [item["file"] for item in payload["relevant_files"]]
    assert "lib/screens/help_request_screen.dart" in files
    assert "lib/cubit/help_requests_cubit.dart" in files
    assert payload["diagnostics"]["code_graph"]["graph_used"] is True
    assert payload["diagnostics"]["code_graph"]["selected_graph_files"]


def test_patch_plan_context_graph_depth_one_adds_direct_impacted_importer_only(tmp_path: Path):
    root = tmp_path / "repo"
    _write(
        root / "lib/screens/help_request_screen.dart",
        """
import '../cubit/help_requests_cubit.dart';

class HelpRequestScreen {
  void build() {
    HelpRequestsCubit();
  }
}
""".strip()
        + "\n",
    )
    _write(
        root / "lib/cubit/help_requests_cubit.dart",
        """
import '../services/help_requests_service.dart';

class HelpRequestsCubit {
  final service = HelpRequestsService();
}
""".strip()
        + "\n",
    )
    _write(root / "lib/services/help_requests_service.dart", "class HelpRequestsService {}\n")

    payload = build_patch_plan_context(
        "Измени поведение сервиса заявок",
        project_path=str(root),
        changed_files=["lib/services/help_requests_service.dart"],
        max_files=8,
        max_tokens=4000,
        output_mode="debug",
    )

    files = [item["file"] for item in payload["relevant_files"]]
    assert "lib/services/help_requests_service.dart" in files
    assert "lib/cubit/help_requests_cubit.dart" in files
    assert "lib/screens/help_request_screen.dart" not in files
    cubit = next(item for item in payload["relevant_files"] if item["file"] == "lib/cubit/help_requests_cubit.dart")
    assert "code_graph" in cubit["why"]
    assert payload["diagnostics"]["code_graph"]["max_depth"] == 1


def test_patch_plan_context_graph_failure_falls_back_to_existing_discovery(tmp_path: Path, monkeypatch):
    root = tmp_path / "repo"
    _write(root / "lib/help_requests_cubit.dart", "class HelpRequestsCubit {}\n")

    def fail_build(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(patch_plan_context, "build_project_code_graph", fail_build)

    payload = build_patch_plan_context(
        "HelpRequestsCubit",
        project_path=str(root),
        max_files=8,
        max_tokens=4000,
        output_mode="debug",
    )

    assert [item["file"] for item in payload["relevant_files"]] == ["lib/help_requests_cubit.dart"]
    assert payload["diagnostics"]["code_graph"]["graph_used"] is False
    assert "RuntimeError: boom" in payload["diagnostics"]["code_graph"]["fallback_reason"]
