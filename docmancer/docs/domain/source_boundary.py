from __future__ import annotations

import fnmatch
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from docmancer.core.config import DocmancerConfig, ProjectSourceBoundaryConfig
from docmancer.docs.project import EXCLUDED_DIR_NAMES


_PACKAGE_AND_TOOL_DIRS = frozenset({
    ".dart_tool", ".gradle", ".mypy_cache", ".next", ".npm", ".pytest_cache",
    ".ruff_cache", ".tox", ".venv", "archive-v0", "build", "coverage",
    "dist", "node_modules", "site-packages", "target", "uv-cache", "vendor",
})
_GENERATED_DIRS = frozenset({"generated", "gen"})
_GENERATED_MARKERS = (
    ".g.dart", ".freezed.dart", ".pb.go", ".generated.", ".gen.",
    "generatedpluginregistrant.",
)


@dataclass(frozen=True)
class SourceBoundary:
    source_roots: tuple[str, ...] = ()
    documentation_roots: tuple[str, ...] = ()
    exclude_paths: tuple[str, ...] = ()
    generated_paths: tuple[str, ...] = ()
    include_extensions: tuple[str, ...] = ()
    respect_gitignore: bool = True
    max_scanned_files: int = 5000
    max_scanned_bytes: int = 32 * 1024 * 1024
    max_file_bytes: int = 256_000
    scan_deadline_seconds: float = 5.0
    max_directory_depth: int = 20
    gitignore_patterns: tuple[str, ...] = field(default=(), repr=False)
    enabled: bool = True
    code_files: tuple[str, ...] = ()

    @classmethod
    def from_project(cls, root: Path) -> SourceBoundary:
        config_path = root / "docatlas.yaml"
        configured = ProjectSourceBoundaryConfig()
        if config_path.is_file() and not config_path.is_symlink():
            try:
                configured = DocmancerConfig.from_yaml(config_path).project.source_boundary()
            except (OSError, ValueError):
                return cls(enabled=False)
        from dataclasses import replace
        from docmancer.docs.project_docs_catalog import read_project_docs_catalog
        catalog = read_project_docs_catalog(root)
        boundary = cls.from_config(configured, root=root)
        return replace(boundary, code_files=catalog.code_files if catalog.present and catalog.valid else (),
                       enabled=boundary.enabled and catalog.present and catalog.valid)

    @classmethod
    def from_config(
        cls, config: ProjectSourceBoundaryConfig, *, root: Path
    ) -> SourceBoundary:
        extensions = tuple(
            sorted({value if value.startswith(".") else f".{value}" for value in config.include_extensions})
        )
        return cls(
            source_roots=tuple(config.source_roots),
            documentation_roots=tuple(config.documentation_roots),
            exclude_paths=tuple(config.exclude_paths),
            generated_paths=tuple(config.generated_paths),
            include_extensions=extensions,
            respect_gitignore=config.respect_gitignore,
            max_scanned_files=config.max_scanned_files,
            max_scanned_bytes=config.max_scanned_bytes,
            max_file_bytes=config.max_file_bytes,
            scan_deadline_seconds=config.scan_deadline_seconds,
            max_directory_depth=config.max_directory_depth,
            gitignore_patterns=_read_gitignore(root) if config.respect_gitignore else (),
        )


def iter_bounded_source_files(
    root: Path,
    *,
    boundary: SourceBoundary,
    supported_extensions: frozenset[str],
    include_generated: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> Iterator[Path]:
    if not boundary.enabled or not boundary.code_files or len(boundary.code_files) > boundary.max_scanned_files:
        return
    include_generated = include_generated is True
    deadline = clock() + boundary.scan_deadline_seconds
    scanned_files = 0
    scanned_bytes = 0
    seen_paths: set[Path] = set()
    # Whole declaration preflight: an invalid member cannot yield a partial grant.
    paths = []
    for relative in boundary.code_files:
        if clock() >= deadline:
            return
        path = finite_local_path(root, relative, boundary=boundary,
                                 supported_extensions=supported_extensions,
                                 include_generated=include_generated)
        if path is None or path in seen_paths:
            return
        seen_paths.add(path)
        paths.append(path)
    for path in paths:
        if clock() >= deadline or scanned_files >= boundary.max_scanned_files:
            return
        try:
            size = path.stat().st_size
        except OSError:
            return
        if scanned_bytes + size > boundary.max_scanned_bytes:
            return
        scanned_files += 1
        scanned_bytes += size
        yield path


def finite_local_path(root: Path, relative: str, *, boundary: SourceBoundary,
                      supported_extensions: frozenset[str],
                      include_generated: bool = False,
                      use_configured_extensions: bool = True) -> Path | None:
    """Check one literal member without visiting siblings or following symlinks."""
    from pathlib import PurePosixPath
    from docmancer.docs.project_docs_catalog import _literal_path
    include_generated = include_generated is True
    if not boundary.enabled or not isinstance(relative, str) or not _literal_path(relative):
        return None
    parts = PurePosixPath(relative).parts
    if use_configured_extensions and boundary.source_roots and not any(
        value == "." or (_literal_path(value) and
            (relative == value or relative.startswith(value + "/")))
        for value in boundary.source_roots
    ):
        return None
    if len(parts) - 1 > boundary.max_directory_depth:
        return None
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            return None
    try:
        path = current.resolve()
        path.relative_to(root.resolve())
        if not path.is_file() or path.stat().st_size > boundary.max_file_bytes:
            return None
    except (OSError, ValueError):
        return None
    if any(_excluded_directory('/'.join(parts[:index + 1]), part, boundary)
           for index, part in enumerate(parts[:-1])):
        return None
    extensions = (frozenset(boundary.include_extensions) or supported_extensions) if use_configured_extensions else supported_extensions
    if path.suffix.lower() not in extensions or path.suffix.lower() not in supported_extensions:
        return None
    if _matches_any(relative, boundary.exclude_paths):
        return None
    if not include_generated and _generated_path(relative, boundary):
        return None
    if boundary.respect_gitignore and _gitignored(relative, boundary.gitignore_patterns):
        return None
    return path


def _safe_source_roots(root: Path, configured: tuple[str, ...]) -> tuple[Path, ...]:
    if not configured:
        return ()
    roots: list[Path] = []
    for value in configured:
        candidate = root / value
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        if candidate.is_symlink() or not resolved.is_dir() or resolved in roots:
            continue
        roots.append(resolved)
    return tuple(sorted(roots, key=lambda path: path.relative_to(root).as_posix()))


def _excluded_directory(relative: str, name: str, boundary: SourceBoundary) -> bool:
    return (
        name in EXCLUDED_DIR_NAMES
        or name in _PACKAGE_AND_TOOL_DIRS
        or _matches_any(relative, boundary.exclude_paths)
        or (
            boundary.respect_gitignore
            and not any(pattern.startswith("!") for pattern in boundary.gitignore_patterns)
            and _gitignored(f"{relative}/", boundary.gitignore_patterns)
        )
    )


def _generated_path(relative: str, boundary: SourceBoundary) -> bool:
    lowered = relative.casefold()
    parts = lowered.split("/")
    return (
        any(part in _GENERATED_DIRS for part in parts[:-1])
        or any(marker in parts[-1] for marker in _GENERATED_MARKERS)
        or _matches_any(relative, boundary.generated_paths)
    )


def _matches_any(relative: str, patterns: tuple[str, ...]) -> bool:
    return any(_match_path(relative, pattern) for pattern in patterns)


def _match_path(relative: str, pattern: str) -> bool:
    normalized = pattern.strip().replace("\\", "/")
    if not normalized or normalized.startswith("#"):
        return False
    anchored = normalized.startswith("/")
    normalized = normalized[1:] if anchored else normalized
    if normalized.endswith("/"):
        prefix = normalized.rstrip("/")
        if anchored or "/" in prefix:
            return relative == prefix or relative.startswith(f"{prefix}/")
        parts = relative.rstrip("/").split("/")
        directory_parts = parts if relative.endswith("/") else parts[:-1]
        return relative.rstrip("/") == prefix or prefix in directory_parts
    if anchored:
        return fnmatch.fnmatchcase(relative, normalized)
    if "/" not in normalized:
        return any(fnmatch.fnmatchcase(part, normalized) for part in relative.split("/"))
    return fnmatch.fnmatchcase(relative, normalized)


def _read_gitignore(root: Path) -> tuple[str, ...]:
    path = root / ".gitignore"
    if path.is_symlink():
        # An unreviewed external ignore file must not relax local boundaries.
        return ("*",)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ()
    return tuple(line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#"))


def _gitignored(relative: str, patterns: tuple[str, ...]) -> bool:
    ignored = False
    for raw in patterns:
        negated = raw.startswith("!")
        pattern = raw[1:] if negated else raw
        if _match_path(relative, pattern):
            ignored = not negated
    return ignored
