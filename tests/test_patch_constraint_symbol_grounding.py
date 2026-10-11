from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.service import LibraryDocsService


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _packet(root: Path, question: str, changed_files: list[str] | None = None):
    return PatchConstraintsService(LibraryDocsService()).get_patch_constraints(
        question=question,
        project_path=str(root),
        changed_files=changed_files or [],
        max_constraints=30,
        max_tokens=8000,
    )


def _nbo_like_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _write(
        root / "docs/research/normal-architecture-note.md",
        "NormalResearchService owns normal research note policy.\n",
    )
    _write(
        root / "docs/research/docatlas-dogfood-v2/foo/patch-review/review_summary.md",
        "FakeReviewService owns menu policy and must be used.\n",
    )
    _write(
        root / "docs/research/docatlas-dogfood-v2/foo/patch-review/constraints.md",
        "FakeConstraintService owns generated patch-review constraints.\n",
    )
    _write(root / ".docatlas/patch-review/run-1/review_summary.md", "InternalFakeService owns everything.\n")
    _write(root / "docs/research/docatlas-dogfood-v3/foo/task.md", "Task description remains allowed.\n")
    _write(
        root / "lib/modules/tsd_browser/presentation/menu/menu_line.dart",
        """
void buildMenu() {
  ref.read(tabBrowserNotifierProvider.notifier).openInfo();
  menuNotifierController.closeMenu();
  browserNavigationNotifier.goToScanDocInit();
}
""",
    )
    _write(
        root / "lib/generated/assets.dart",
        "class Assets { static const String tsdbrowserCactus = 'assets/tsdbrowser/cactus.webp'; }\n",
    )
    return root


def test_close_menu_alias_does_not_invent_without_source_match(tmp_path: Path):
    root = tmp_path / "repo"
    _write(root / "lib/menu.dart", "void openMenu() {}\n")

    packet = _packet(root, "закрывать шторку перед действиями", ["lib/menu.dart"])

    assert not any(candidate["matched_symbol"] == "closeMenu" for candidate in packet.symbol_candidates)


def test_generated_asset_candidate_filtered_for_non_asset_task(tmp_path: Path):
    root = _nbo_like_fixture(tmp_path)

    packet = _packet(root, "Update TSDBrowser navigation behavior", ["lib/modules/tsd_browser/presentation/menu/menu_line.dart"])

    assert not any(candidate["source"] == "lib/generated/assets.dart" for candidate in packet.symbol_candidates)


def test_generated_file_guardrail_and_validation_are_not_weakened(tmp_path: Path):
    root = _nbo_like_fixture(tmp_path)
    _write(
        root / "docs/architecture.md",
        "Generated artifacts such as *.g.dart and *.freezed.dart must not be edited by hand; regenerate them from source.\n",
    )

    packet = _packet(root, "Update menu", ["lib/generated/foo.g.dart"])

    assert any(constraint.type == "generated_file" for constraint in packet.constraints)
