"""Composable project dependency metadata adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from docmancer.docs.cargo_project import read_cargo_project
from docmancer.docs.go_project import read_go_project
from docmancer.docs.models import DependencyObservation
from docmancer.docs.node_project import read_node_project
from docmancer.docs.pub_project import read_pub_project
from docmancer.docs.python_project import read_python_project


@dataclass
class EcosystemProjectResult:
    packages: dict[str, str] = field(default_factory=dict)
    direct_dependencies: list[str] = field(default_factory=list)
    observations: list[DependencyObservation] = field(default_factory=list)
    source_roots: dict[str, Path] = field(default_factory=dict)


class ProjectEcosystemAdapter(Protocol):
    name: str

    def read(self, root: Path, warnings: list[str]) -> EcosystemProjectResult: ...


@dataclass(frozen=True)
class FunctionProjectAdapter:
    name: str
    reader: Callable[[Path, list[str]], EcosystemProjectResult]

    def read(self, root: Path, warnings: list[str]) -> EcosystemProjectResult:
        return self.reader(root, warnings)


def _pub(root: Path, warnings: list[str]) -> EcosystemProjectResult:
    packages, direct, observations = read_pub_project(root, warnings)
    return EcosystemProjectResult(packages, direct, observations)


def _cargo(root: Path, warnings: list[str]) -> EcosystemProjectResult:
    packages, observations = read_cargo_project(root, warnings)
    return EcosystemProjectResult(packages=packages, observations=observations)


def _node(root: Path, warnings: list[str]) -> EcosystemProjectResult:
    packages, direct, observations = read_node_project(root, warnings)
    return EcosystemProjectResult(packages, direct, observations)


def _python(root: Path, warnings: list[str]) -> EcosystemProjectResult:
    packages, direct, observations = read_python_project(root, warnings)
    return EcosystemProjectResult(packages, direct, observations)


def _go(root: Path, warnings: list[str]) -> EcosystemProjectResult:
    packages, observations, roots = read_go_project(root, warnings)
    direct = [
        item.package_name for item in observations
        if item.dependency_group == "dependencies"
    ]
    return EcosystemProjectResult(packages, direct, observations, roots)


BUILTIN_PROJECT_ECOSYSTEM_ADAPTERS: tuple[ProjectEcosystemAdapter, ...] = (
    FunctionProjectAdapter("pub", _pub),
    FunctionProjectAdapter("rust", _cargo),
    FunctionProjectAdapter("npm", _node),
    FunctionProjectAdapter("python", _python),
    FunctionProjectAdapter("go", _go),
)


def read_project_ecosystems(
    root: Path,
    warnings: list[str],
    *,
    adapters: tuple[ProjectEcosystemAdapter, ...] = BUILTIN_PROJECT_ECOSYSTEM_ADAPTERS,
) -> EcosystemProjectResult:
    combined = EcosystemProjectResult()
    for adapter in adapters:
        result = adapter.read(root, warnings)
        combined.packages.update(result.packages)
        combined.direct_dependencies.extend(result.direct_dependencies)
        combined.observations.extend(result.observations)
        combined.source_roots.update(result.source_roots)
    combined.direct_dependencies = sorted(set(combined.direct_dependencies))
    return combined
