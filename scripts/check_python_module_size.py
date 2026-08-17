#!/usr/bin/env python3
"""Fail when a hand-written Python module grows beyond the project line budget."""
from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_MAX_LINES = 1000
IGNORED_PARTS = {
    ".git", ".venv", "venv", "build", "dist", "site-packages",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}


def iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if not path.is_file() or path.is_symlink():
            continue
        yield path


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def oversized_modules(root: Path, limit: int = DEFAULT_MAX_LINES):
    return sorted(
        ((line_count(path), path.relative_to(root).as_posix()) for path in iter_python_files(root)
         if line_count(path) > limit),
        reverse=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    violations = oversized_modules(root, args.max_lines)
    if violations:
        print(f"Python module line budget exceeded ({args.max_lines} lines):")
        for lines, path in violations:
            print(f"  {lines:5d}  {path}")
        return 1
    print(f"Python module size gate: PASS (all .py <= {args.max_lines} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
