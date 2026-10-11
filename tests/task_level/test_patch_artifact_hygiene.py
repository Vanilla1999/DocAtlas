from __future__ import annotations

import json
import subprocess
from pathlib import Path

from eval.task_level.artifact_hygiene import (
    apply_patch_hygiene,
    is_preserved_generated_candidate,
    is_runtime_artifact,
    normalize_diff_header_path,
    normalize_repo_path,
)
from eval.task_level.execution import capture_patch
from eval.task_level.evaluators.patch import forbidden_changed_paths














def test_capture_patch_writes_raw_and_normalized_hygiene_artifacts(tmp_path: Path):
    subprocess.run(["git", "init"], cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    subprocess.run(["git", "config", "user.email", "benchmark@example.invalid"], cwd=tmp_path, check=False)
    subprocess.run(["git", "config", "user.name", "Task Benchmark"], cwd=tmp_path, check=False)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "example.py").write_text("before\n", encoding="utf-8")
    pycache = tmp_path / "tests" / "__pycache__"
    pycache.mkdir(parents=True)
    (pycache / "test_example.cpython-311.pyc").write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=False)
    subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    (tmp_path / "src" / "example.py").write_text("after\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/example.py"], cwd=tmp_path, check=True)
    (pycache / "test_example.cpython-311.pyc").write_text("after\n", encoding="utf-8")
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "service.py").write_text("new\n", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (pycache / "untracked.cpython-311.pyc").write_text("new\n", encoding="utf-8")

    patch_path, status_path, changed_path, changed = capture_patch(tmp_path, tmp_path)

    assert patch_path.name == "patch.diff"
    assert status_path.name == "git_status.txt"
    assert changed == ["src/example.py", "a/service.py", "package-lock.json"]
    assert json.loads(changed_path.read_text(encoding="utf-8")) == ["src/example.py", "a/service.py", "package-lock.json"]
    assert json.loads((tmp_path / "changed_files.raw.json").read_text(encoding="utf-8")) == [
        "src/example.py",
        "tests/__pycache__/test_example.cpython-311.pyc",
        "a/service.py",
        "package-lock.json",
    ]
    ignored = json.loads((tmp_path / "ignored_runtime_artifacts.json").read_text(encoding="utf-8"))
    assert ignored == ["tests/__pycache__/test_example.cpython-311.pyc", "tests/__pycache__/untracked.cpython-311.pyc"]
    hygiene = json.loads((tmp_path / "patch_hygiene.json").read_text(encoding="utf-8"))
    assert hygiene["raw_counts"]["changed_files"] == 4
    assert hygiene["filtered_counts"]["changed_files"] == 3
    assert hygiene["filtered_counts"]["ignored_runtime_artifacts"] == 2
    assert (tmp_path / "patch.raw.diff").exists()
    patch = patch_path.read_text(encoding="utf-8", errors="replace")
    assert "__pycache__" not in patch
    assert "+after" in patch
    assert "+new" in patch
    assert "package-lock.json" in patch
