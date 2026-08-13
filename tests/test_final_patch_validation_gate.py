from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_final_candidate_patch_compiles_and_has_clean_diff_whitespace():
    compile_result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "docmancer", "eval", "tests"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert compile_result.returncode == 0, compile_result.stderr

    diff_result = subprocess.run(
        ["git", "diff", "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert diff_result.returncode == 0, diff_result.stdout + diff_result.stderr
