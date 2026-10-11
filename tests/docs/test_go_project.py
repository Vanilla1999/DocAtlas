from pathlib import Path

from docmancer.docs.application.dependency_resolution import project_version_for
from docmancer.docs.ecosystem_adapters import EcosystemProjectResult, read_project_ecosystems
from docmancer.docs.go_project import read_go_project
from docmancer.docs.models import DependencyObservation
from docmancer.docs.project import ProjectMetadataReader


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

