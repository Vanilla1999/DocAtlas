from __future__ import annotations

from dataclasses import asdict
import ast
import json
from pathlib import Path
import shutil

from docmancer.docs.cargo_project import read_cargo_project
from docmancer.docs.application.dependency_resolution import project_version_for
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.pub_project import read_pub_project


def test_cargo_adapter_matches_golden_fixture_and_keeps_import_boundary(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "cargo_project_adapter"
    project = tmp_path / "cargo_project"
    shutil.copytree(fixture, project, ignore=shutil.ignore_patterns("expected.json"))
    warnings: list[str] = []

    packages, observations = read_cargo_project(project, warnings)
    actual = {"packages": packages, "observations": [asdict(item) for item in observations], "warnings": warnings}
    expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
    source = (Path(__file__).parents[2] / "docmancer" / "docs" / "cargo_project.py").read_text(encoding="utf-8")
    project_source = (Path(__file__).parents[2] / "docmancer" / "docs" / "project.py").read_text(encoding="utf-8")
    imported_modules = {
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert json.dumps(actual, sort_keys=True, separators=(",", ":")) == json.dumps(
        expected, sort_keys=True, separators=(",", ":")
    )
    assert not {
        module
        for module in imported_modules
        if module.startswith(("docmancer.cli", "docmancer.mcp", "docmancer.docs.application"))
    }
    assert "def _read_cargo" not in project_source


def test_pub_adapter_matches_golden_fixture_and_keeps_import_boundary(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "pub_project_adapter"
    expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
    actual: dict[str, dict[str, object]] = {}
    for name in ("valid", "malformed"):
        project = tmp_path / name
        shutil.copytree(fixture / name, project)
        warnings: list[str] = []
        packages, direct_dependencies, observations = read_pub_project(project, warnings)
        actual[name] = {
            "packages": packages,
            "direct_dependencies": direct_dependencies,
            "observations": [asdict(item) for item in observations],
            "warnings": warnings,
        }
    source = (Path(__file__).parents[2] / "docmancer" / "docs" / "pub_project.py").read_text(encoding="utf-8")
    project_source = (Path(__file__).parents[2] / "docmancer" / "docs" / "project.py").read_text(encoding="utf-8")
    imported_modules = {
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert json.dumps(actual, sort_keys=True, separators=(",", ":")) == json.dumps(
        expected, sort_keys=True, separators=(",", ":")
    )
    assert not {
        module
        for module in imported_modules
        if module.startswith(("docmancer.cli", "docmancer.mcp", "docmancer.docs.application"))
    }
    assert "def _read_pubspec" not in project_source


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
