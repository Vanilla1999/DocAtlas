from pathlib import Path

from docmancer.docs.application.dependency_resolution import project_version_for
from docmancer.docs.ecosystem_adapters import EcosystemProjectResult, read_project_ecosystems
from docmancer.docs.go_project import read_go_project
from docmancer.docs.models import DependencyObservation
from docmancer.docs.project import ProjectMetadataReader


def test_go_mod_requirement_is_detected_but_not_claimed_as_resolved(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text(
        "module example.com/app\n\ngo 1.24\nrequire github.com/gin-gonic/gin v1.10.0\n",
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(tmp_path)

    assert metadata.detected_ecosystems == ["go"]
    assert metadata.packages == {}
    dependency = metadata.dependencies[0]
    assert dependency.package_name == "github.com/gin-gonic/gin"
    assert dependency.specifier_raw == "v1.10.0"
    assert dependency.resolved_version is None
    assert dependency.version_source == "go_mod_requirement"
    assert "minimum requirement" in dependency.warnings[0]


def test_vendor_modules_proves_exact_go_version_and_pkg_docs_binding(tmp_path: Path) -> None:
    (tmp_path / "go.mod").write_text(
        "module example.com/app\n\nrequire github.com/gin-gonic/gin v1.10.0\n",
        encoding="utf-8",
    )
    (tmp_path / "vendor").mkdir()
    (tmp_path / "vendor/modules.txt").write_text(
        "# github.com/gin-gonic/gin v1.10.0\n## explicit; go 1.20\ngithub.com/gin-gonic/gin\n",
        encoding="utf-8",
    )
    metadata = ProjectMetadataReader().read(tmp_path)

    result = project_version_for(
        library="github.com/gin-gonic/gin",
        ecosystem="go",
        project_path=str(tmp_path),
        read_project_metadata=lambda _: metadata,
    )

    assert metadata.packages["go:github.com/gin-gonic/gin"] == "v1.10.0"
    assert result[0] == "v1.10.0"
    assert result[1] == "https://pkg.go.dev/github.com/gin-gonic/gin@v1.10.0"
    assert result[5] is True
    assert result[7] == "pkg_go_dev"


def test_local_go_replace_is_exposed_as_local_source_not_public_docs(tmp_path: Path) -> None:
    local = tmp_path / "localmod"
    local.mkdir()
    (local / "go.mod").write_text("module example.com/local\n", encoding="utf-8")
    (tmp_path / "go.mod").write_text(
        "module example.com/app\n\nrequire example.com/local v1.2.3\nreplace example.com/local => ./localmod\n",
        encoding="utf-8",
    )

    packages, observations, roots = read_go_project(tmp_path, [])

    assert packages == {}
    assert observations[0].source_kind == "path"
    assert roots == {"go:example.com/local": local.resolve()}


def test_go_work_reads_multiple_workspace_modules(tmp_path: Path) -> None:
    for name, dependency in (("api", "github.com/gin-gonic/gin"), ("worker", "golang.org/x/sync")):
        module = tmp_path / name
        module.mkdir()
        (module / "go.mod").write_text(
            f"module example.com/{name}\n\nrequire {dependency} v1.10.0\n",
            encoding="utf-8",
        )
    (tmp_path / "go.work").write_text("go 1.24\nuse (\n ./api\n ./worker\n)\n", encoding="utf-8")

    _, observations, _ = read_go_project(tmp_path, [])

    assert {item.package_name for item in observations} == {
        "github.com/gin-gonic/gin", "golang.org/x/sync",
    }


def test_project_ecosystem_adapter_contract_is_extensible_without_reader_branching(tmp_path: Path) -> None:
    class Adapter:
        name = "sample"

        def read(self, root, warnings):
            assert root == tmp_path
            return EcosystemProjectResult(
                packages={"sample:lib": "1.0.0"},
                direct_dependencies=["lib"],
                observations=[DependencyObservation(
                    ecosystem="sample",
                    package_name="lib",
                    resolved_version="1.0.0",
                )],
            )

    result = read_project_ecosystems(tmp_path, [], adapters=(Adapter(),))

    assert result.packages == {"sample:lib": "1.0.0"}
    assert result.direct_dependencies == ["lib"]
