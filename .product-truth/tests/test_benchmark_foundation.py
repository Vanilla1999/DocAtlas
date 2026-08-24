from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load(ROOT / ".product-truth" / "real_task_pack.py", "product_truth_real_task_pack")
workspace = _load(ROOT / ".product-truth" / "model_workspace.py", "product_truth_model_workspace")
MANIFEST = json.loads((ROOT / ".product-truth" / "real-task-pack.json").read_text(encoding="utf-8"))


def _attempt(number: int) -> dict:
    return {
        "attempt": number,
        "public_base": {"returncode": 0},
        "hidden_base": {
            "returncode": 1,
            "junit_parsed": True,
            "testcases": 1,
            "test_failures": 1,
            "test_errors": 0,
        },
        "patch_applied": True,
        "gold_surface_exact": True,
        "public_gold": {"returncode": 0},
        "hidden_gold": {"returncode": 0},
        "passed": True,
    }


def _report() -> dict:
    rows = []
    for task in MANIFEST["tasks"]:
        rows.append(
            {
                "id": task["id"],
                "fix_commit": task["fix_commit"],
                "base_commit": "0" * 40,
                "issue_sha256": "1" * 64,
                "hidden_test_path": task["hidden_test_path"],
                "hidden_test_sha256": "2" * 64,
                "production_paths": ["src/example.py"],
                "gold_patch_sha256": "3" * 64,
                "attempts": [_attempt(1), _attempt(2)],
                "gold_reproducible": True,
                "real_model_oracle_executed": False,
                "real_model_oracle_passed": False,
                "valid": False,
            }
        )
    return {
        "schema_version": 1,
        "protocol": runner.REPORT_PROTOCOL,
        "repository": MANIFEST["repository"],
        "frozen_inventory_head": MANIFEST["frozen_inventory_head"],
        "manifest_sha256": runner.manifest_sha256(MANIFEST),
        "tasks": rows,
        "summary": {
            "task_count": 8,
            "gold_reproducible_tasks": 8,
            "real_model_oracle_tasks": 0,
            "valid_tasks": 0,
        },
        "claim_boundary": {
            "gold_control_complete": True,
            "real_model_oracle_complete": False,
            "task_pack_ready": False,
            "product_truth_proven": False,
            "product_failure_proven": False,
            "product_maturity": "Beta",
        },
    }


def _semantic_verifier(report: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "verify_task_provenance", lambda *_args, **_kwargs: None)
    runner.verify_report(report, MANIFEST)


def test_attempt_requires_assertion_red_exactly() -> None:
    item = _attempt(1)
    assert runner.attempt_stage_valid(item) is True
    for code in (2, 3, 4, 5):
        mutated = copy.deepcopy(item)
        mutated["hidden_base"]["returncode"] = code
        assert runner.attempt_stage_valid(mutated) is False


def test_setup_error_is_not_hidden_red() -> None:
    item = _attempt(1)
    item["hidden_base"].update(test_failures=0, test_errors=1)
    assert runner.attempt_stage_valid(item) is False
    item = _attempt(1)
    item["hidden_base"]["junit_parsed"] = False
    assert runner.attempt_stage_valid(item) is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["tasks"][0]["attempts"][0]["public_base"].update(returncode=1),
        lambda r: r["tasks"][0]["attempts"][0]["hidden_base"].update(returncode=2),
        lambda r: r["tasks"][0]["attempts"][0]["hidden_base"].update(test_failures=0, test_errors=1),
        lambda r: r["tasks"][0]["attempts"][0].update(patch_applied=False),
        lambda r: r["tasks"][0]["attempts"][0].update(gold_surface_exact=False),
        lambda r: r["tasks"][0]["attempts"][0]["public_gold"].update(returncode=1),
        lambda r: r["tasks"][0]["attempts"][0]["hidden_gold"].update(returncode=1),
        lambda r: r["tasks"][0].update(gold_reproducible=False),
        lambda r: r["tasks"][0].update(real_model_oracle_executed=True),
        lambda r: r["tasks"][0].update(real_model_oracle_passed=True),
        lambda r: r["tasks"][0].update(valid=True),
        lambda r: r["summary"].update(gold_reproducible_tasks=9),
        lambda r: r["claim_boundary"].update(product_truth_proven=True),
        lambda r: r["claim_boundary"].update(product_maturity="Stable"),
    ],
)
def test_report_mutations_fail_closed(mutate, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report()
    mutate(report)
    with pytest.raises(ValueError):
        _semantic_verifier(report, monkeypatch)


def test_report_rejects_pass_claim_that_disagrees_with_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _report()
    report["tasks"][0]["attempts"][0]["passed"] = False
    with pytest.raises(ValueError, match="attempt pass claim drift"):
        _semantic_verifier(report, monkeypatch)


def test_provenance_fields_are_authoritative(monkeypatch: pytest.MonkeyPatch) -> None:
    task = MANIFEST["tasks"][0]
    expected = {
        "id": task["id"],
        "fix_commit": task["fix_commit"],
        "base_commit": "a" * 40,
        "issue_sha256": "b" * 64,
        "hidden_test_path": task["hidden_test_path"],
        "hidden_test_sha256": "c" * 64,
        "production_paths": ["src/a.py", "src/b.py"],
        "gold_patch_sha256": "d" * 64,
        "gold_patch": b"patch",
    }
    monkeypatch.setattr(runner, "task_provenance", lambda *_args, **_kwargs: copy.deepcopy(expected))
    row = {key: value for key, value in expected.items() if key != "gold_patch"}
    runner.verify_task_provenance(MANIFEST, task, row)
    for field in (
        "id",
        "fix_commit",
        "base_commit",
        "issue_sha256",
        "hidden_test_path",
        "hidden_test_sha256",
        "production_paths",
        "gold_patch_sha256",
    ):
        mutated = copy.deepcopy(row)
        mutated[field] = ["other.py"] if field == "production_paths" else "forged"
        with pytest.raises(ValueError):
            runner.verify_task_provenance(MANIFEST, task, mutated)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_changed_surface_includes_untracked_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "benchmark@example.invalid")
    _git(repo, "config", "user.name", "Benchmark Test")
    (repo / "tracked.py").write_text("old\n", encoding="utf-8")
    _git(repo, "add", "tracked.py")
    _git(repo, "commit", "-qm", "base")
    (repo / "tracked.py").write_text("new\n", encoding="utf-8")
    (repo / "new.py").write_text("new\n", encoding="utf-8")
    assert runner.changed_worktree_paths(repo) == ["new.py", "tracked.py"]


def test_model_workspace_materializes_base_without_evaluator_metadata(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "benchmark@example.invalid")
    _git(repo, "config", "user.name", "Benchmark Test")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / ".product-truth").mkdir()
    (repo / ".product-truth" / "gold.txt").write_text("secret\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "broken base")
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

    output = tmp_path / "model"
    attestation = tmp_path / "attestation.json"
    payload = workspace.materialize(repo, base, output, attestation)
    assert (output / "src" / "app.py").is_file()
    assert not (output / ".git").exists()
    assert not (output / ".product-truth").exists()
    assert payload["git_metadata_absent"] is True
    assert payload["benchmark_metadata_absent"] is True
    assert payload["claim_boundary"]["network_isolated"] is False
    assert attestation.is_file()
    assert not str(attestation).startswith(str(output) + "/")
