from __future__ import annotations

import fnmatch
import os
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

    @classmethod
    def from_project(cls, root: Path) -> SourceBoundary:
        config_path = root / "docatlas.yaml"
        configured = ProjectSourceBoundaryConfig()
        if config_path.is_file() and not config_path.is_symlink():
            try:
                configured = DocmancerConfig.from_yaml(config_path).project.source_boundary()
            except (OSError, ValueError):
                return cls(enabled=False)
        return cls.from_config(configured, root=root)

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
    if not boundary.enabled:
        return
    deadline = clock() + boundary.scan_deadline_seconds
    scanned_files = 0
    scanned_bytes = 0
    seen_paths: set[Path] = set()
    roots = _safe_source_roots(root, boundary.source_roots)
    for source_root in roots:
        for directory, dirnames, filenames in os.walk(source_root, followlinks=False):
            if clock() >= deadline:
                return
            current = Path(directory)
            relative_directory = current.relative_to(root)
            depth = len(relative_directory.parts)
            if depth > boundary.max_directory_depth:
                dirnames.clear()
                continue
            kept_dirs: list[str] = []
            for name in sorted(dirnames):
                candidate = current / name
                relative = candidate.relative_to(root).as_posix()
                if candidate.is_symlink() or _excluded_directory(relative, name, boundary):
                    continue
                if not include_generated and _generated_path(relative, boundary):
                    continue
                kept_dirs.append(name)
            dirnames[:] = kept_dirs
            for filename in sorted(filenames):
                if clock() >= deadline or scanned_files >= boundary.max_scanned_files:
                    return
                path = current / filename
                if path.is_symlink() or path in seen_paths:
                    continue
                seen_paths.add(path)
                relative = path.relative_to(root).as_posix()
                suffix = path.suffix.lower()
                extensions = frozenset(boundary.include_extensions) or supported_extensions
                if suffix not in extensions or suffix not in supported_extensions:
                    continue
                if _matches_any(relative, boundary.exclude_paths):
                    continue
                if not include_generated and _generated_path(relative, boundary):
                    continue
                if boundary.respect_gitignore and _gitignored(relative, boundary.gitignore_patterns):
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                scanned_files += 1
                if size > boundary.max_file_bytes or scanned_bytes + size > boundary.max_scanned_bytes:
                    if scanned_bytes + size > boundary.max_scanned_bytes:
                        return
                    continue
                scanned_bytes += size
                yield path


def _safe_source_roots(root: Path, configured: tuple[str, ...]) -> tuple[Path, ...]:
    if not configured:
        return (root,)
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
