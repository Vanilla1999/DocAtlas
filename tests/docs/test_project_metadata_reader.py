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


def test_cargo_project_output_matches_golden_fixture(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "cargo_project_adapter"
    project = tmp_path / "cargo_project"
    shutil.copytree(fixture, project, ignore=shutil.ignore_patterns("expected.json"))

    metadata = ProjectMetadataReader().read(project)
    actual = {
        "packages": {key: value for key, value in metadata.packages.items() if key.startswith("rust:")},
        "observations": [asdict(item) for item in metadata.dependencies if item.ecosystem == "rust"],
        "warnings": [warning for warning in metadata.warnings if warning.startswith("Cargo")],
    }
    expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))

    assert json.dumps(actual, sort_keys=True, separators=(",", ":")) == json.dumps(
        expected, sort_keys=True, separators=(",", ":")
    )


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


def test_pub_project_output_matches_golden_fixture(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "pub_project_adapter"
    expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
    actual: dict[str, dict[str, object]] = {}
    for name in ("valid", "malformed"):
        project = tmp_path / name
        shutil.copytree(fixture / name, project)
        metadata = ProjectMetadataReader().read(project)
        actual[name] = {
            "packages": metadata.packages,
            "direct_dependencies": metadata.direct_dependencies,
            "observations": [asdict(item) for item in metadata.dependencies if item.ecosystem == "pub"],
            "warnings": [warning for warning in metadata.warnings if warning.startswith("pubspec")],
        }

    assert json.dumps(actual, sort_keys=True, separators=(",", ":")) == json.dumps(
        expected, sort_keys=True, separators=(",", ":")
    )


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


def test_python_project_uses_poetry_lock_when_uv_lock_is_absent(tmp_path: Path) -> None:
    root = tmp_path / "python_repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\ndependencies = ['fastapi>=0.110']\n", encoding="utf-8"
    )
    (root / "poetry.lock").write_text(
        "[[package]]\nname = 'fastapi'\nversion = '0.115.6'\n", encoding="utf-8"
    )

    metadata = ProjectMetadataReader().read(root)
    dependency = next(item for item in metadata.dependencies if item.package_name == "fastapi")

    assert metadata.packages["python:fastapi"] == "0.115.6"
    assert dependency.version_source == "poetry.lock_exact"


def test_python_project_uses_pdm_lock_when_it_is_the_available_lock(tmp_path: Path) -> None:
    root = tmp_path / "python_repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        "[project]\nname = 'demo'\ndependencies = ['httpx>=0.27']\n", encoding="utf-8"
    )
    (root / "pdm.lock").write_text(
        "[[package]]\nname = 'httpx'\nversion = '0.28.1'\n", encoding="utf-8"
    )

    metadata = ProjectMetadataReader().read(root)
    dependency = next(item for item in metadata.dependencies if item.package_name == "httpx")

    assert metadata.packages["python:httpx"] == "0.28.1"
    assert dependency.version_source == "pdm.lock_exact"


def test_python_manifest_pin_is_not_claimed_as_resolved_without_lock(tmp_path: Path) -> None:
    root = tmp_path / "python_repo"
    root.mkdir()
    (root / "requirements.txt").write_text("fastapi==0.115.6\n", encoding="utf-8")

    metadata = ProjectMetadataReader().read(root)
    dependency = next(item for item in metadata.dependencies if item.package_name == "fastapi")

    assert "python:fastapi" not in metadata.packages
    assert dependency.specifier_kind == "declared_exact"
    assert dependency.resolved_version is None
    assert dependency.version_source == "manifest_declared_exact"


def test_python_project_reads_pipfile_lock_exact_versions(tmp_path: Path) -> None:
    root = tmp_path / "python_repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        "[project]\nname='demo'\ndependencies=['fastapi>=0.110']\n", encoding="utf-8"
    )
    (root / "Pipfile.lock").write_text(
        '{"default":{"fastapi":{"version":"==0.115.6"}},"develop":{}}', encoding="utf-8"
    )

    metadata = ProjectMetadataReader().read(root)
    dependency = next(item for item in metadata.dependencies if item.package_name == "fastapi")

    assert metadata.packages["python:fastapi"] == "0.115.6"
    assert dependency.version_source == "pipfile.lock_exact"


def test_poetry_path_and_git_dependencies_are_never_registry_version_bindings(tmp_path: Path) -> None:
    root = tmp_path / "poetry_repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        """
[tool.poetry]
name = "demo"
version = "0.1.0"

[tool.poetry.dependencies]
python = ">=3.11"
local-lib = { path = "../local-lib" }
git-lib = { git = "https://github.com/example/git-lib.git" }
""".strip(),
        encoding="utf-8",
    )
    (root / "uv.lock").write_text(
        """
version = 1

[[package]]
name = "local-lib"
version = "1.2.3"

[[package]]
name = "git-lib"
version = "4.5.6"
""".strip(),
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(root)
    python = {item.package_name: item for item in metadata.dependencies if item.ecosystem == "python"}

    assert "python:local-lib" not in metadata.packages
    assert "python:git-lib" not in metadata.packages
    assert python["local-lib"].source_kind == "path"
    assert python["local-lib"].resolved_version is None
    assert python["git-lib"].source_kind == "git"
    assert python["git-lib"].resolved_version is None


def test_python_git_lock_entry_cannot_bind_registry_documentation(tmp_path: Path) -> None:
    root = tmp_path / "python_repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        "[project]\nname='demo'\ndependencies=['sample>=1']\n", encoding="utf-8"
    )
    (root / "uv.lock").write_text(
        "[[package]]\nname='sample'\nversion='1.2.3'\nsource={git='https://example.test/sample.git'}\n",
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(root)
    dependency = next(item for item in metadata.dependencies if item.package_name == "sample")

    assert "python:sample" not in metadata.packages
    assert dependency.resolved_version is None


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


def test_node_project_reads_bun_json_lock_for_direct_dependencies(tmp_path: Path) -> None:
    root = tmp_path / "bun_repo"
    root.mkdir()
    (root / "package.json").write_text(
        '{"packageManager":"bun@1.2.0","dependencies":{"react":"^18.0.0"}}', encoding="utf-8"
    )
    (root / "bun.lock").write_text(
        '{"packages":{"react@18.3.1":{"name":"react","version":"18.3.1"}}}', encoding="utf-8"
    )

    metadata = ProjectMetadataReader().read(root)
    dependency = next(item for item in metadata.dependencies if item.package_name == "react")

    assert metadata.packages["npm:react"] == "18.3.1"
    assert dependency.version_source == "bun.lock_exact"


def test_node_project_reads_realistic_bun_text_lock_array(tmp_path: Path) -> None:
    root = tmp_path / "bun_text_repo"
    root.mkdir()
    (root / "package.json").write_text(
        '{"packageManager":"bun@1.2.0","dependencies":{"react":"^18.0.0","@scope/pkg":"~1.2.0"}}',
        encoding="utf-8",
    )
    (root / "bun.lock").write_text(
        '''{
  "lockfileVersion": 1,
  "packages": {
    "react": ["react@18.3.1", "", {}, "sha512-example"],
    "@scope/pkg": ["@scope/pkg@1.2.4", "", {}, "sha512-example"]
  }
}''',
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


def test_python_lock_version_is_available_to_project_library_resolution(tmp_path: Path) -> None:
    root = tmp_path / "python_resolution_repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample"\ndependencies = ["fastapi>=0.100"]\n',
        encoding="utf-8",
    )
    (root / "uv.lock").write_text(
        'version = 1\n[[package]]\nname = "fastapi"\nversion = "0.115.6"\n',
        encoding="utf-8",
    )
    metadata = ProjectMetadataReader().read(root)

    version, docs_url, template, warnings, requested, exact, source, binding = project_version_for(
        library="fastapi",
        ecosystem="python",
        project_path=str(root),
        read_project_metadata=lambda _: metadata,
    )

    assert version == "0.115.6"
    assert docs_url is None
    assert template is None
    assert requested == "fastapi>=0.100"
    assert exact is None
    assert source == "uv.lock_exact"
    assert binding == "python_registry_version"
    assert warnings == []


def test_pub_git_dependency_is_not_bound_to_pubdev(tmp_path: Path) -> None:
    root = tmp_path / "pub_git_repo"
    root.mkdir()
    (root / "pubspec.yaml").write_text(
        "dependencies:\n  sample:\n    git: https://example.com/sample.git\n",
        encoding="utf-8",
    )
    (root / "pubspec.lock").write_text(
        "packages:\n  sample:\n    dependency: direct main\n    source: git\n    version: 1.2.3\n",
        encoding="utf-8",
    )
    metadata = ProjectMetadataReader().read(root)

    version, docs_url, template, warnings, requested, exact, source, binding = project_version_for(
        library="sample",
        ecosystem="pub",
        project_path=str(root),
        read_project_metadata=lambda _: metadata,
    )

    assert "sample" not in metadata.packages
    assert version is None
    assert docs_url is None
    assert template is None
    assert requested == "1.2.3"
    assert exact is False
    assert source == "lockfile_exact"
    assert binding == "no_docs"
    assert any("cannot be bound to pub.dev" in warning for warning in warnings)


def test_pub_custom_hosted_dependency_is_not_bound_to_pubdev(tmp_path: Path) -> None:
    root = tmp_path / "pub_custom_host_repo"
    root.mkdir()
    (root / "pubspec.yaml").write_text(
        "dependencies:\n  internal_api: 1.2.3\n",
        encoding="utf-8",
    )
    (root / "pubspec.lock").write_text(
        "packages:\n"
        "  internal_api:\n"
        "    dependency: direct main\n"
        "    description:\n"
        "      name: internal_api\n"
        "      url: https://packages.example.com\n"
        "    source: hosted\n"
        "    version: 1.2.3\n",
        encoding="utf-8",
    )
    metadata = ProjectMetadataReader().read(root)

    version, docs_url, template, warnings, _, exact, _, binding = project_version_for(
        library="internal_api",
        ecosystem="pub",
        project_path=str(root),
        read_project_metadata=lambda _: metadata,
    )

    assert "internal_api" not in metadata.packages
    assert version is None
    assert docs_url is None
    assert template is None
    assert exact is False
    assert binding == "no_docs"
    assert any("custom_hosted" in warning for warning in warnings)


def test_project_metadata_exposes_shared_dart_package_source_roots(tmp_path: Path) -> None:
    root = tmp_path / "dart_repo"
    dependency = tmp_path / "pub-cache" / "sample-1.2.3"
    (root / ".dart_tool").mkdir(parents=True)
    dependency.mkdir(parents=True)
    (root / ".dart_tool/package_config.json").write_text(
        json.dumps({
            "configVersion": 2,
            "packages": [
                {"name": "app", "rootUri": "../../dart_repo"},
                {"name": "sample", "rootUri": dependency.as_uri()},
            ],
        }),
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(root)

    assert metadata.dependency_source_roots == {"pub:sample": str(dependency.resolve())}


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
