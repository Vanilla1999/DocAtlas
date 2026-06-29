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


def test_runtime_artifacts_are_filtered_from_changed_files():
    hygiene = apply_patch_hygiene(
        raw_status_lines=[" M tests/__pycache__/test_example.cpython-311.pyc"],
        raw_changed_files=["tests/__pycache__/test_example.cpython-311.pyc", "src/example.py"],
        raw_patch_diff="diff --git a/tests/__pycache__/test_example.cpython-311.pyc b/tests/__pycache__/test_example.cpython-311.pyc\nindex 1..2 100644\n--- a/tests/__pycache__/test_example.cpython-311.pyc\n+++ b/tests/__pycache__/test_example.cpython-311.pyc\n@@ -1 +1 @@\n-old\n+new\ndiff --git a/src/example.py b/src/example.py\nindex 1..2 100644\n--- a/src/example.py\n+++ b/src/example.py\n@@ -1 +1 @@\n-old\n+new\n",
    )

    assert hygiene.filtered_changed_files == ["src/example.py"]
    assert hygiene.ignored_runtime_artifacts == ["tests/__pycache__/test_example.cpython-311.pyc"]
    assert "__pycache__" not in hygiene.filtered_patch_diff
    assert hygiene.raw_counts["changed_files"] == 2
    assert hygiene.filtered_counts["changed_files"] == 1
    assert hygiene.filtered_counts["ignored_runtime_artifacts"] == 1


def test_repo_path_normalization_does_not_strip_top_level_a_or_b_dirs():
    assert normalize_repo_path("a/service.py") == "a/service.py"
    assert normalize_repo_path("b/generated/client.pb.go") == "b/generated/client.pb.go"
    assert normalize_diff_header_path("a/service.py") == "service.py"
    assert normalize_diff_header_path("b/generated/client.pb.go") == "generated/client.pb.go"


def test_generated_and_lockfile_candidates_are_preserved():
    changed = [
        "lib/model/foo.g.dart",
        "lib/model/foo.freezed.dart",
        "generated/client.pb.go",
        "pubspec.lock",
        "package-lock.json",
        "src/.generated.client.ts",
    ]

    hygiene = apply_patch_hygiene(raw_status_lines=[], raw_changed_files=changed, raw_patch_diff="")

    assert hygiene.filtered_changed_files == changed
    assert hygiene.preserved_generated_candidates == changed
    assert not hygiene.ignored_runtime_artifacts
    assert all(is_preserved_generated_candidate(path) for path in changed)


def test_untracked_non_runtime_files_are_included_and_runtime_files_ignored():
    hygiene = apply_patch_hygiene(
        raw_status_lines=[
            "?? src/new_feature.py",
            "?? tests/__pycache__/test_new.cpython-312.pyc",
            "?? generated/client.pb.go",
            "?? package-lock.json",
        ],
        raw_changed_files=[],
        raw_patch_diff="",
    )

    assert hygiene.filtered_changed_files == ["src/new_feature.py", "generated/client.pb.go", "package-lock.json"]
    assert hygiene.ignored_runtime_artifacts == ["tests/__pycache__/test_new.cpython-312.pyc"]
    assert hygiene.preserved_generated_candidates == ["generated/client.pb.go", "package-lock.json"]


def test_runtime_artifact_detection_does_not_hide_real_generated_paths():
    assert is_runtime_artifact("tests/__pycache__/x.cpython-311.pyc")
    assert is_runtime_artifact(".pytest_cache/v/cache/nodeids")
    assert not is_runtime_artifact("generated/client.pb.go")
    assert not is_runtime_artifact("dist/client.js")
    assert not is_runtime_artifact("package-lock.json")


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
    assert "__pycache__" not in patch_path.read_text(encoding="utf-8", errors="replace")
