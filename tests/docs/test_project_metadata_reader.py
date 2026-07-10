from __future__ import annotations

from pathlib import Path

from docmancer.docs.application.dependency_resolution import project_version_for
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


def test_python_project_binds_direct_dependencies_to_uv_lock_versions(tmp_path: Path) -> None:
    root = tmp_path / "python_repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        """
[project]
name = "demo"
dependencies = ["fastapi>=0.110", "httpx==0.27.2"]

[dependency-groups]
dev = ["pytest>=8"]
""".strip(),
        encoding="utf-8",
    )
    (root / "uv.lock").write_text(
        """
version = 1

[[package]]
name = "fastapi"
version = "0.115.6"

[[package]]
name = "httpx"
version = "0.27.2"

[[package]]
name = "pytest"
version = "8.3.4"
""".strip(),
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(root)
    python = {item.package_name: item for item in metadata.dependencies if item.ecosystem == "python"}

    assert metadata.packages["python:fastapi"] == "0.115.6"
    assert metadata.packages["python:httpx"] == "0.27.2"
    assert metadata.packages["python:pytest"] == "8.3.4"
    assert python["fastapi"].version_source == "uv.lock_exact"
    assert python["pytest"].dependency_group == "dev"
    assert "python" in metadata.detected_ecosystems


def test_flutter_project_reads_pubspec_without_requiring_fvmrc_or_lock(tmp_path: Path) -> None:
    root = tmp_path / "flutter_repo"
    root.mkdir()
    (root / "pubspec.yaml").write_text("dependencies:\n  flutter:\n    sdk: flutter\n", encoding="utf-8")

    metadata = ProjectMetadataReader().read(root)

    assert ".fvmrc not found." not in metadata.warnings
    assert "pubspec.lock not found." not in metadata.warnings
    assert "flutter" in metadata.detected_ecosystems
    assert "flutter" in metadata.direct_dependencies


def test_node_project_reads_direct_exact_versions_from_package_lock(tmp_path: Path) -> None:
    root = tmp_path / "node_repo"
    root.mkdir()
    (root / "package.json").write_text(
        '{"packageManager":"npm@10.8.0","dependencies":{"react":"^18.0.0","local-ui":"file:../ui"},"devDependencies":{"@types/react":"^18.2.0"}}',
        encoding="utf-8",
    )
    (root / "package-lock.json").write_text(
        '{"lockfileVersion":3,"packages":{"":{"dependencies":{"react":"^18.0.0","local-ui":"file:../ui"},"devDependencies":{"@types/react":"^18.2.0"}},"node_modules/react":{"version":"18.3.1"},"node_modules/@types/react":{"version":"18.3.3"},"node_modules/local-ui":{"resolved":"../ui","link":true}}}',
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(root)
    by_name = {item.package_name: item for item in metadata.dependencies if item.ecosystem == "npm"}

    assert metadata.packages["npm:react"] == "18.3.1"
    assert metadata.packages["npm:@types/react"] == "18.3.3"
    assert "npm:local-ui" not in metadata.packages
    assert metadata.direct_dependencies == ["@types/react", "local-ui", "react"]
    assert by_name["react"].version_source == "package-lock.json_exact"
    assert by_name["@types/react"].dependency_group == "dev"
    assert by_name["local-ui"].source_kind == "path"
    assert "npm" in metadata.detected_ecosystems


def test_node_project_prefers_package_manager_pnpm_lock_and_normalizes_peer_suffix(tmp_path: Path) -> None:
    root = tmp_path / "pnpm_repo"
    root.mkdir()
    (root / "package.json").write_text(
        '{"packageManager":"pnpm@9.12.0","dependencies":{"react":"^18.0.0"},"devDependencies":{"vite":"^5.0.0"}}',
        encoding="utf-8",
    )
    (root / "package-lock.json").write_text('{"dependencies":{"react":{"version":"1.0.0"}}}', encoding="utf-8")
    (root / "pnpm-lock.yaml").write_text(
        """
lockfileVersion: '9.0'
importers:
  .:
    dependencies:
      react:
        specifier: ^18.0.0
        version: 18.3.1(@types/react@18.3.3)
    devDependencies:
      vite:
        specifier: ^5.0.0
        version: 5.4.14
""".strip(),
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(root)

    assert metadata.packages["npm:react"] == "18.3.1"
    assert metadata.packages["npm:vite"] == "5.4.14"
    assert all(item.version_source == "pnpm-lock.yaml_exact" for item in metadata.dependencies if item.ecosystem == "npm")


def test_node_project_reads_yarn_v1_lock_for_scoped_and_unscoped_packages(tmp_path: Path) -> None:
    root = tmp_path / "yarn_repo"
    root.mkdir()
    (root / "package.json").write_text(
        '{"packageManager":"yarn@1.22.22","dependencies":{"react":"^18.0.0","@scope/pkg":"~1.2.0"}}',
        encoding="utf-8",
    )
    (root / "yarn.lock").write_text(
        '''
react@^18.0.0:
  version "18.3.1"

"@scope/pkg@~1.2.0":
  version "1.2.4"
'''.strip(),
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(root)

    assert metadata.packages["npm:react"] == "18.3.1"
    assert metadata.packages["npm:@scope/pkg"] == "1.2.4"


def test_node_exact_version_is_available_to_project_library_resolution(tmp_path: Path) -> None:
    root = tmp_path / "resolution_repo"
    root.mkdir()
    (root / "package.json").write_text('{"dependencies":{"react":"^18.0.0"}}', encoding="utf-8")
    (root / "package-lock.json").write_text(
        '{"packages":{"":{"dependencies":{"react":"^18.0.0"}},"node_modules/react":{"version":"18.3.1"}}}',
        encoding="utf-8",
    )
    metadata = ProjectMetadataReader().read(root)

    version, docs_url, template, warnings, requested, exact, source, binding = project_version_for(
        library="react",
        ecosystem="npm",
        project_path=str(root),
        read_project_metadata=lambda _: metadata,
    )

    assert version == "18.3.1"
    assert docs_url is None
    assert template is None
    assert requested == "^18.0.0"
    assert exact is None
    assert source == "package-lock.json_exact"
    assert binding == "npm_registry_version"
    assert warnings == []


def test_node_manifest_ranges_are_never_reported_as_exact_without_lockfile(tmp_path: Path) -> None:
    root = tmp_path / "range_only_repo"
    root.mkdir()
    (root / "package.json").write_text(
        '{"dependencies":{"major":"18","minor":"18.2","tag":"latest","caret":"^18.0.0","wildcard":"18.x"}}',
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(root)
    npm = {item.package_name: item for item in metadata.dependencies if item.ecosystem == "npm"}

    assert not any(key.startswith("npm:") for key in metadata.packages)
    assert all(item.resolved_version is None for item in npm.values())
    assert npm["major"].specifier_kind == "range"
    assert npm["minor"].specifier_kind == "range"
    assert npm["wildcard"].specifier_kind == "range"
    assert npm["tag"].specifier_kind == "tag"


def test_node_full_semver_manifest_is_exact_without_lockfile(tmp_path: Path) -> None:
    root = tmp_path / "exact_manifest_repo"
    root.mkdir()
    (root / "package.json").write_text(
        '{"dependencies":{"react":"18.3.1","prerelease":"v2.0.0-beta.1"}}',
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(root)

    assert metadata.packages["npm:react"] == "18.3.1"
    assert metadata.packages["npm:prerelease"] == "2.0.0-beta.1"
