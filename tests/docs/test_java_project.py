from pathlib import Path

from docmancer.docs.application.dependency_resolution import project_version_for
from docmancer.docs.project import ProjectMetadataReader


def test_gradle_version_catalog_alias_is_not_guessed(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text(
        "dependencies { implementation(libs.jackson.databind) }",
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(tmp_path)

    assert metadata.packages == {}
    assert metadata.dependencies == []
