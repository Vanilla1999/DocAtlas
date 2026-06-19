from docmancer.docs.project import ProjectMetadataReader


def test_pubspec_lock_exact_version_target_mvp(tmp_path):
    project = tmp_path / "dart_app"
    project.mkdir()
    (project / "pubspec.yaml").write_text(
        "name: dart_app\ndependencies:\n  go_router: ^14.0.0\n",
        encoding="utf-8",
    )
    (project / "pubspec.lock").write_text(
        """
packages:
  go_router:
    dependency: direct main
    source: hosted
    version: "14.8.1"
""".strip(),
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(project)
    observation = next(item for item in metadata.dependencies if item.ecosystem == "pub" and item.package_name == "go_router" and item.resolved_version)

    assert observation.resolved_version == "14.8.1"
    assert observation.version_source == "lockfile_exact"
    assert f"https://pub.dev/documentation/{observation.package_name}/{observation.resolved_version}/" == "https://pub.dev/documentation/go_router/14.8.1/"


def test_cargo_lock_exact_version_target_mvp(tmp_path):
    project = tmp_path / "rust_app"
    project.mkdir()
    (project / "Cargo.toml").write_text(
        '[package]\nname = "rust_app"\nversion = "0.1.0"\n\n[dependencies]\nserde = "1"\n',
        encoding="utf-8",
    )
    (project / "Cargo.lock").write_text(
        """
[[package]]
name = "serde"
version = "1.0.228"
source = "registry+https://github.com/rust-lang/crates.io-index"
""".strip(),
        encoding="utf-8",
    )

    metadata = ProjectMetadataReader().read(project)
    observation = next(item for item in metadata.dependencies if item.ecosystem == "rust" and item.package_name == "serde" and item.resolved_version)

    assert observation.resolved_version == "1.0.228"
    assert observation.version_source == "lockfile_exact"
    assert f"https://docs.rs/{observation.package_name}/{observation.resolved_version}/" == "https://docs.rs/serde/1.0.228/"
