from pathlib import Path

from docmancer.docs.application.dependency_resolution import project_version_for
from docmancer.docs.project import ProjectMetadataReader


def test_pom_version_is_declared_intent_without_lock(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text(
        """<project xmlns="http://maven.apache.org/POM/4.0.0">
        <properties><jackson.version>2.17.2</jackson.version></properties>
        <dependencies><dependency>
          <groupId>com.fasterxml.jackson.core</groupId>
          <artifactId>jackson-databind</artifactId>
          <version>${jackson.version}</version>
        </dependency></dependencies></project>""",
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(tmp_path)
    dependency = next(item for item in metadata.dependencies if item.ecosystem == "maven")

    assert "maven:com.fasterxml.jackson.core:jackson-databind" not in metadata.packages
    assert dependency.specifier_raw == "2.17.2"
    assert dependency.resolved_version is None
    assert dependency.version_source == "build_declaration_unresolved"
    assert "maven" in metadata.detected_ecosystems


def test_gradle_lock_proves_exact_maven_artifact_version(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text(
        'dependencies { implementation("com.fasterxml.jackson.core:jackson-databind:2.17.0") }',
        encoding="utf-8",
    )
    (tmp_path / "gradle.lockfile").write_text(
        "com.fasterxml.jackson.core:jackson-databind:2.17.2=compileClasspath,runtimeClasspath\n"
        "com.fasterxml.jackson.core:jackson-annotations:2.17.2=compileClasspath\n",
        encoding="utf-8",
    )
    metadata = ProjectMetadataReader().read(tmp_path)

    result = project_version_for(
        library="com.fasterxml.jackson.core:jackson-databind",
        ecosystem="maven",
        project_path=str(tmp_path),
        read_project_metadata=lambda _: metadata,
    )

    assert metadata.packages["maven:com.fasterxml.jackson.core:jackson-databind"] == "2.17.2"
    assert result[0] == "2.17.2"
    assert result[1] == "https://javadoc.io/doc/com.fasterxml.jackson.core/jackson-databind/2.17.2/"
    assert result[5] is True
    assert result[6] == "gradle.lockfile_exact"
    assert metadata.direct_dependencies == ["com.fasterxml.jackson.core:jackson-databind"]


def test_gradle_version_catalog_alias_is_not_guessed(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text(
        "dependencies { implementation(libs.jackson.databind) }",
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(tmp_path)

    assert metadata.packages == {}
    assert metadata.dependencies == []
