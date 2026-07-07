from __future__ import annotations

from pathlib import Path

from docmancer.docs.project import ProjectMetadataReader


def test_non_flutter_project_does_not_warn_about_missing_flutter_files(tmp_path: Path) -> None:
    root = tmp_path / "python_repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")

    metadata = ProjectMetadataReader().read(root)

    assert ".fvmrc not found." not in metadata.warnings
    assert "pubspec.lock not found." not in metadata.warnings
    assert "pubspec.yaml not found." not in metadata.warnings
    assert "flutter" not in metadata.detected_ecosystems


def test_flutter_project_reads_pubspec_without_requiring_fvmrc_or_lock(tmp_path: Path) -> None:
    root = tmp_path / "flutter_repo"
    root.mkdir()
    (root / "pubspec.yaml").write_text("dependencies:\n  flutter:\n    sdk: flutter\n", encoding="utf-8")

    metadata = ProjectMetadataReader().read(root)

    assert ".fvmrc not found." not in metadata.warnings
    assert "pubspec.lock not found." not in metadata.warnings
    assert "flutter" in metadata.detected_ecosystems
    assert "flutter" in metadata.direct_dependencies
