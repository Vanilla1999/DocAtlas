from __future__ import annotations

from typing import Any, Callable

from docmancer.docs.models import ProjectMetadata
from docmancer.docs.resolver import normalize_library_name


PUB_DOCS_URL_TEMPLATE = "https://pub.dev/documentation/{library}/{version}/"
NO_PROJECT_VERSION_WARNING = "No version was found in project metadata; using latest/default docs."
PACKAGE_NOT_FOUND_WARNING = "Package was not found in pubspec.lock."
FLUTTER_CHANNEL_DOCS_WARNING = (
    "Flutter project version {version} was detected, but api.flutter.dev provides current stable API docs, "
    "not an exact archived snapshot."
)


def is_flutter_library(library: str) -> bool:
    return normalize_library_name(library) in {"flutter", "flutter-api"}


def flutter_docs_url_for(version: str | None, channel: str | None) -> str:
    selected = (channel or version or "").lower()
    if selected in {"main", "master"}:
        return "https://main-api.flutter.dev/"
    return "https://api.flutter.dev/"


def flutter_docs_version_for(version: str | None, channel: str | None) -> str | None:
    selected = (channel or version or "").lower()
    if selected in {"main", "master"}:
        return "main"
    if channel:
        return channel
    if version:
        return "stable"
    return None


def project_resolution_summary(metadata: ProjectMetadata) -> dict[str, int]:
    exact_versions = sum(1 for item in metadata.dependencies if item.resolved_version and item.version_source.endswith("exact"))
    best_effort_docs = sum(1 for item in metadata.dependencies if item.source_kind != "registry")
    return {
        "dependencies_seen": len(metadata.dependencies),
        "exact_versions": exact_versions,
        "best_effort_docs": best_effort_docs,
        "no_docs": 0,
    }


def dependency_observation_for(metadata: ProjectMetadata, library: str, ecosystem: str | None) -> Any | None:
    candidates = [item for item in metadata.dependencies if item.package_name == library]
    if ecosystem:
        candidates = [item for item in candidates if item.ecosystem == ecosystem]
    if candidates:
        return next((item for item in candidates if item.resolved_version), candidates[0])
    rust_key = metadata.packages.get(f"rust:{library}")
    if rust_key and ecosystem in {None, "rust"}:
        return next((item for item in metadata.dependencies if item.ecosystem == "rust" and item.package_name == library), None)
    return None


def project_version_for(
    *,
    library: str,
    ecosystem: str | None,
    project_path: str | None,
    read_project_metadata: Callable[[str], ProjectMetadata],
) -> tuple[str | None, str | None, str | None, list[str], str | None, bool | None, str | None, str | None]:
    if not project_path:
        return None, None, None, [], None, None, None, None
    metadata = read_project_metadata(project_path)
    warnings = list(metadata.warnings)
    if is_flutter_library(library):
        selected = flutter_docs_version_for(metadata.flutter_version, metadata.flutter_channel)
        if selected:
            if metadata.flutter_version and selected == "stable":
                warnings.append(FLUTTER_CHANNEL_DOCS_WARNING.format(version=metadata.flutter_version))
            return (
                selected,
                flutter_docs_url_for(metadata.flutter_version, metadata.flutter_channel),
                None,
                warnings,
                metadata.flutter_version or metadata.flutter_channel,
                False,
                "project_flutter_sdk",
                "flutter_api_current_channel",
            )
        warnings.append(NO_PROJECT_VERSION_WARNING)
        return None, None, None, warnings, None, None, None, None

    observation = dependency_observation_for(metadata, library, ecosystem)
    if observation and observation.ecosystem == "rust":
        if observation.source_kind != "registry":
            warnings.append(f"{library}: Rust path/git dependencies cannot be bound to docs.rs exactly.")
            return None, None, None, warnings, observation.specifier_raw, False, observation.version_source, "no_docs"
        if observation.resolved_version:
            return (
                observation.resolved_version,
                f"https://docs.rs/{library}/{observation.resolved_version}/",
                None,
                warnings,
                observation.specifier_raw or observation.resolved_version,
                True,
                observation.version_source,
                "docs_rs",
            )
        warnings.append(NO_PROJECT_VERSION_WARNING)
        return None, None, None, warnings, observation.specifier_raw, False, observation.version_source, "no_docs"

    if observation and observation.ecosystem == "npm":
        if observation.source_kind != "registry":
            warnings.append(
                f"{library}: npm path/git dependencies cannot be bound to "
                "registry documentation exactly."
            )
            return None, None, None, warnings, observation.specifier_raw, False, observation.version_source, "no_docs"
        if observation.resolved_version:
            return (
                observation.resolved_version,
                None,
                None,
                warnings,
                observation.specifier_raw or observation.resolved_version,
                None,
                observation.version_source,
                "npm_registry_version",
            )
        warnings.append(NO_PROJECT_VERSION_WARNING)
        return None, None, None, warnings, observation.specifier_raw, False, observation.version_source, "no_docs"

    if ecosystem == "pub" or library in metadata.packages:
        version = metadata.packages.get(library)
        if version:
            source = observation.version_source if observation else "lockfile_exact"
            return version, None, PUB_DOCS_URL_TEMPLATE, warnings, version, True, source, "pub_dartdoc"
        warnings.append(PACKAGE_NOT_FOUND_WARNING)
        warnings.append(NO_PROJECT_VERSION_WARNING)
        return None, None, None, warnings, None, None, None, None

    warnings.append(NO_PROJECT_VERSION_WARNING)
    return None, None, None, warnings, None, None, None, None
