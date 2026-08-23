#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SHA_RE = re.compile(r"[0-9a-f]{40}")
REPORT_PROTOCOL = "docatlas-source-real-task-gold-v1"
EXCLUDED_PREFIXES = (
    ".github/",
    ".product-truth/",
    "docs/",
    "wiki/",
    "tests/",
    "test/",
)
EXCLUDED_NAMES = {
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
}
TEST_MARKERS = ("/tests/", "/test/", "_test.py", ".test.", ".spec.")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def run_git(*args: str, cwd: Path = ROOT, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def require_git(*args: str, cwd: Path = ROOT, input_bytes: bytes | None = None) -> bytes:
    result = run_git(*args, cwd=cwd, input_bytes=input_bytes)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace")[-1000:]
        raise ValueError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def first_parent(fix_commit: str) -> str:
    raw = require_git("rev-list", "--parents", "-n", "1", fix_commit).decode().strip().split()
    if len(raw) != 2:
        raise ValueError(f"{fix_commit}: historical task requires exactly one parent")
    return raw[1]


def changed_paths(base: str, fix: str) -> list[str]:
    raw = require_git("diff", "--name-only", base, fix).decode("utf-8", errors="strict")
    return [line for line in raw.splitlines() if line]


def is_test_path(path: str) -> bool:
    normalized = "/" + path.replace("\\", "/")
    return any(marker in normalized for marker in TEST_MARKERS)


def production_paths(paths: list[str]) -> list[str]:
    result: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        if normalized in EXCLUDED_NAMES:
            continue
        if normalized.startswith(EXCLUDED_PREFIXES):
            continue
        if is_test_path(normalized):
            continue
        if normalized.endswith((".md", ".rst")):
            continue
        result.append(normalized)
    return result


def git_blob(commit: str, path: str) -> bytes:
    return require_git("show", f"{commit}:{path}")


def path_exists(commit: str, path: str) -> bool:
    return run_git("cat-file", "-e", f"{commit}:{path}").returncode == 0


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != 1 or manifest.get("protocol") != "docatlas-source-real-task-pack-v1":
        raise ValueError("real-task manifest identity mismatch")
    frozen = str(manifest.get("frozen_inventory_head") or "")
    if SHA_RE.fullmatch(frozen) is None:
        raise ValueError("frozen inventory head must be a full Git SHA")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 8:
        raise ValueError("real-task pack requires exactly eight tasks")
    ids: set[str] = set()
    commits: set[str] = set()
    for task in tasks:
        if not isinstance(task, Mapping):
            raise ValueError("task row must be an object")
        task_id = str(task.get("id") or "")
        fix = str(task.get("fix_commit") or "")
        if not task_id or task_id in ids:
            raise ValueError("real-task ids must be unique")
        if SHA_RE.fullmatch(fix) is None or fix in commits:
            raise ValueError("historical fix commits must be unique full Git SHAs")
        ids.add(task_id)
        commits.add(fix)
        for field in ("issue_text", "hidden_test_path", "public_nodeid", "hidden_nodeid"):
            value = task.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{task_id}: {field} is required")
        hidden_path = str(task["hidden_test_path"])
        if not is_test_path(hidden_path):
            raise ValueError(f"{task_id}: hidden path is not a repository test")
        if ".." in Path(hidden_path).parts or Path(hidden_path).is_absolute():
            raise ValueError(f"{task_id}: hidden test path escapes repository")
        if len(str(task["issue_text"])) > 1200:
            raise ValueError(f"{task_id}: issue text is not bounded")


def test_environment(worktree: Path, manifest: Mapping[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    roots = [str(worktree)]
    for item in manifest.get("pythonpath", []):
        roots.append(str((worktree / str(item)).resolve()))
    if env.get("PYTHONPATH"):
        roots.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(roots)
    return env


def run_test(
    worktree: Path,
    manifest: Mapping[str, Any],
    nodeid: str,
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    working = worktree / str(manifest.get("working_directory") or ".")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", nodeid],
        cwd=working,
        env=test_environment(worktree, manifest),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stdout_sha256": sha256_bytes(result.stdout),
        "stderr_sha256": sha256_bytes(result.stderr),
    }


def overlay_hidden_test(worktree: Path, fix: str, path: str) -> tuple[bytes | None, bool]:
    target = worktree / path
    existed = target.is_file()
    previous = target.read_bytes() if existed else None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(git_blob(fix, path))
    return previous, existed


def restore_hidden_test(worktree: Path, path: str, previous: bytes | None, existed: bool) -> None:
    target = worktree / path
    if existed:
        assert previous is not None
        target.write_bytes(previous)
    else:
        target.unlink(missing_ok=True)


def run_attempt(
    manifest: Mapping[str, Any],
    task: Mapping[str, Any],
    *,
    base: str,
    fix: str,
    prod_paths: list[str],
    gold_patch: bytes,
    attempt: int,
) -> dict[str, Any]:
    hidden_path = str(task["hidden_test_path"])
    timeout_seconds = int(task.get("test_timeout_seconds") or 180)
    with tempfile.TemporaryDirectory(prefix=f"docatlas-real-{task['id']}-{attempt}-") as raw:
        worktree = Path(raw) / "workspace"
        require_git("worktree", "add", "--detach", str(worktree), base)
        try:
            public_base = run_test(
                worktree,
                manifest,
                str(task["public_nodeid"]),
                timeout_seconds=timeout_seconds,
            )
            previous, existed = overlay_hidden_test(worktree, fix, hidden_path)
            try:
                hidden_base = run_test(
                    worktree,
                    manifest,
                    str(task["hidden_nodeid"]),
                    timeout_seconds=timeout_seconds,
                )
            finally:
                restore_hidden_test(worktree, hidden_path, previous, existed)

            apply_result = run_git("apply", "--whitespace=nowarn", "-", cwd=worktree, input_bytes=gold_patch)
            patch_applied = apply_result.returncode == 0
            changed_after_gold = []
            public_gold = {"returncode": 99, "stdout_sha256": "", "stderr_sha256": ""}
            hidden_gold = dict(public_gold)
            if patch_applied:
                changed_after_gold = require_git("diff", "--name-only", cwd=worktree).decode().splitlines()
                public_gold = run_test(
                    worktree,
                    manifest,
                    str(task["public_nodeid"]),
                    timeout_seconds=timeout_seconds,
                )
                previous, existed = overlay_hidden_test(worktree, fix, hidden_path)
                try:
                    hidden_gold = run_test(
                        worktree,
                        manifest,
                        str(task["hidden_nodeid"]),
                        timeout_seconds=timeout_seconds,
                    )
                finally:
                    restore_hidden_test(worktree, hidden_path, previous, existed)

            surface_ok = sorted(changed_after_gold) == sorted(prod_paths)
            passed = bool(
                public_base["returncode"] == 0
                and hidden_base["returncode"] in {1, 2}
                and patch_applied
                and surface_ok
                and public_gold["returncode"] == 0
                and hidden_gold["returncode"] == 0
            )
            return {
                "attempt": attempt,
                "public_base": public_base,
                "hidden_base": hidden_base,
                "patch_applied": patch_applied,
                "gold_surface_exact": surface_ok,
                "public_gold": public_gold,
                "hidden_gold": hidden_gold,
                "passed": passed,
            }
        finally:
            run_git("worktree", "remove", "--force", str(worktree))
            run_git("worktree", "prune")


def run_task(manifest: Mapping[str, Any], task: Mapping[str, Any]) -> dict[str, Any]:
    fix = str(task["fix_commit"])
    frozen = str(manifest["frozen_inventory_head"])
    ancestor = run_git("merge-base", "--is-ancestor", fix, frozen).returncode == 0
    if not ancestor:
        raise ValueError(f"{task['id']}: fix is not reachable from frozen inventory head")
    base = first_parent(fix)
    paths = changed_paths(base, fix)
    prod_paths = production_paths(paths)
    if not prod_paths:
        raise ValueError(f"{task['id']}: fix has no production-code change")
    hidden_path = str(task["hidden_test_path"])
    if hidden_path not in paths or not path_exists(fix, hidden_path):
        raise ValueError(f"{task['id']}: hidden repository test was not changed by the fix")
    patch = require_git("diff", "--binary", base, fix, "--", *prod_paths)
    if not patch.strip():
        raise ValueError(f"{task['id']}: production-only gold patch is empty")
    attempts = [
        run_attempt(
            manifest,
            task,
            base=base,
            fix=fix,
            prod_paths=prod_paths,
            gold_patch=patch,
            attempt=index,
        )
        for index in (1, 2)
    ]
    gold_reproducible = all(row["passed"] for row in attempts)
    return {
        "id": task["id"],
        "fix_commit": fix,
        "base_commit": base,
        "issue_sha256": sha256_bytes(str(task["issue_text"]).encode("utf-8")),
        "hidden_test_path": hidden_path,
        "hidden_test_sha256": sha256_bytes(git_blob(fix, hidden_path)),
        "production_paths": prod_paths,
        "gold_patch_sha256": sha256_bytes(patch),
        "attempts": attempts,
        "gold_reproducible": gold_reproducible,
        "real_model_oracle_executed": False,
        "real_model_oracle_passed": False,
        "valid": False,
    }


def build_report(manifest: Mapping[str, Any]) -> dict[str, Any]:
    validate_manifest(manifest)
    tasks = [run_task(manifest, task) for task in manifest["tasks"]]
    gold_count = sum(row["gold_reproducible"] for row in tasks)
    report = {
        "schema_version": 1,
        "protocol": REPORT_PROTOCOL,
        "repository": manifest["repository"],
        "frozen_inventory_head": manifest["frozen_inventory_head"],
        "manifest_sha256": sha256_bytes(canonical_json(manifest).encode("utf-8")),
        "tasks": tasks,
        "summary": {
            "task_count": len(tasks),
            "gold_reproducible_tasks": gold_count,
            "real_model_oracle_tasks": 0,
            "valid_tasks": 0,
        },
        "claim_boundary": {
            "gold_control_complete": gold_count == 8,
            "real_model_oracle_complete": False,
            "task_pack_ready": False,
            "product_truth_proven": False,
            "product_failure_proven": False,
            "product_maturity": "Beta",
        },
    }
    verify_report(report)
    return report


def verify_report(report: Mapping[str, Any]) -> None:
    tasks = report.get("tasks")
    if report.get("schema_version") != 1 or report.get("protocol") != REPORT_PROTOCOL:
        raise ValueError("real-task report identity mismatch")
    if not isinstance(tasks, list) or len(tasks) != 8:
        raise ValueError("real-task report requires eight tasks")
    gold_count = 0
    for row in tasks:
        if not isinstance(row, Mapping):
            raise ValueError("real-task result row must be an object")
        attempts = row.get("attempts")
        if not isinstance(attempts, list) or [item.get("attempt") for item in attempts] != [1, 2]:
            raise ValueError("each task requires exactly two clean gold attempts")
        expected_gold = all(item.get("passed") is True for item in attempts)
        if row.get("gold_reproducible") is not expected_gold:
            raise ValueError("gold reproducibility claim drift")
        gold_count += int(expected_gold)
        if row.get("real_model_oracle_executed") is not False or row.get("valid") is not False:
            raise ValueError("gold control cannot self-authorize model-oracle validity")
    summary = report.get("summary")
    expected_summary = {
        "task_count": 8,
        "gold_reproducible_tasks": gold_count,
        "real_model_oracle_tasks": 0,
        "valid_tasks": 0,
    }
    if summary != expected_summary:
        raise ValueError("real-task summary drift")
    boundary = report.get("claim_boundary")
    if not isinstance(boundary, Mapping):
        raise ValueError("real-task claim boundary missing")
    if boundary.get("gold_control_complete") is not (gold_count == 8):
        raise ValueError("gold-control completion drift")
    for key in ("real_model_oracle_complete", "task_pack_ready", "product_truth_proven", "product_failure_proven"):
        if boundary.get(key) is not False:
            raise ValueError(f"gold control overclaims {key}")
    if boundary.get("product_maturity") != "Beta":
        raise ValueError("gold control cannot promote product maturity")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    report = build_report(load_json(manifest_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "Real-task gold control: "
        f"{report['summary']['gold_reproducible_tasks']}/8 reproducible; "
        "oracle=0/8; valid=0/8"
    )
    if report["summary"]["gold_reproducible_tasks"] != 8:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
