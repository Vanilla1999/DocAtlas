"""Temporary validation bootstrap for the candidate stabilization patch.

This file exists only on the validation branch. It applies the downloadable
patch before pytest imports the test modules, allowing the repository's normal
PR CI to exercise the exact patch without changing main.
"""
from __future__ import annotations

from pathlib import Path
import subprocess


_ROOT = Path(__file__).resolve().parent
_PATCH = _ROOT / ".ci" / "docatlas_964d88d_FINAL_stabilization.patch"


def _git_apply(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "apply", *args, str(_PATCH)],
        cwd=_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


_check = _git_apply("--check")
if _check.returncode == 0:
    _apply = _git_apply()
    if _apply.returncode != 0:
        raise RuntimeError(f"candidate patch failed to apply: {_apply.stderr}")
else:
    _reverse = _git_apply("--reverse", "--check")
    if _reverse.returncode != 0:
        raise RuntimeError(
            "candidate patch is neither cleanly applicable nor already applied: "
            f"{_check.stderr}"
        )
