from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PatchStats:
    files_changed: int
    lines_added: int
    lines_removed: int


def diff_stats(repo: Path) -> PatchStats:
    completed = subprocess.run(
        ["git", "diff", "--numstat"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    files = added = removed = 0
    for line in completed.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        files += 1
        if parts[0].isdigit():
            added += int(parts[0])
        if parts[1].isdigit():
            removed += int(parts[1])
    return PatchStats(files_changed=files, lines_added=added, lines_removed=removed)


def patch_touches_forbidden_paths(repo: Path, allowed_prefixes: tuple[str, ...]) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    forbidden = []
    for path in completed.stdout.splitlines():
        if not any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in allowed_prefixes):
            forbidden.append(path)
    return forbidden


def forbidden_changed_paths(changed_files: list[str], allowed_prefixes: tuple[str, ...]) -> list[str]:
    """Classify the already-captured pre-evaluation patch inventory.

    Using the captured inventory avoids both untracked-file blind spots and changes
    introduced later by hidden-test materialization.
    """
    return [
        path
        for path in changed_files
        if not any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in allowed_prefixes)
    ]
