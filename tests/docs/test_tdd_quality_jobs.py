"""Workflow DAG, unchanged gate commands, and actual fail-closed aggregate shell."""
from pathlib import Path
import os
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
OLD_REQUIRED = {"docs-contract", "installer-smoke", "platform-smoke", "test", "advanced-contract",
                "installed-mcp-harness", "static-contract", "retrieval-evidence"}
NEW_REQUIRED = {"legacy-quality", "v2-quality"}
ALL_REQUIRED = OLD_REQUIRED | NEW_REQUIRED


def _workflow():
    return yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))


def _aggregate():
    job = _workflow()["jobs"]["required-ci"]
    step, = [s for s in job["steps"] if s.get("name") == "Enforce required CI jobs"]
    mapping = {name: expression.removeprefix("${{ needs.").removesuffix(".result }}")
               for name, expression in step["env"].items()}
    assert set(mapping.values()) == ALL_REQUIRED
    return step["run"], mapping


def test_quality_jobs_are_independent_and_required():
    jobs = _workflow()["jobs"]
    assert NEW_REQUIRED <= set(jobs), "Legacy and V2 must be separate jobs"
    for name in NEW_REQUIRED:
        job = jobs[name]
        assert not job.get("needs"), f"{name} must not be gated by another job"
        assert not job.get("if"), f"{name} must run for every CI event"
        assert not job.get("continue-on-error", False)
        assert all(not s.get("continue-on-error", False) for s in job["steps"])
    aggregate = jobs["required-ci"]
    assert set(aggregate["needs"]) == ALL_REQUIRED
    assert aggregate["if"] in ("always()", "${{ always() }}")


def test_quality_gate_commands_are_preserved_once_and_reports_uploaded():
    jobs = _workflow()["jobs"]
    commands = {
        "legacy-quality": [
            'python eval/project_context_quality_protocol.py --live --report-only --output "$RUNNER_TEMP/project-context-quality-legacy-live.json"',
            'python scripts/check_legacy_project_context_lineage.py "$RUNNER_TEMP/project-context-quality-legacy-live.json"',
        ],
        "v2-quality": [
            'python scripts/run_project_context_quality_v2_gate.py --output "$RUNNER_TEMP/project-context-quality-v2-live.json"',
        ],
    }
    assert NEW_REQUIRED <= set(jobs)
    all_runs = "\n".join(s.get("run", "") for j in jobs.values() for s in j.get("steps", []))
    for name, required in commands.items():
        steps = jobs[name]["steps"]
        runs = "\n".join(s.get("run", "") for s in steps)
        for command in required:
            assert runs.count(command) == 1
            assert all_runs.count(command) == 1
        uploads = [s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@")]
        assert uploads and all(s.get("if") in ("always()", "${{ always() }}") for s in uploads)
        assert all(s["with"]["if-no-files-found"] == "error" for s in uploads)
    assert 'python eval/project_context_quality_protocol.py > "$RUNNER_TEMP/project-context-quality-hermetic.json"' in all_runs


def test_required_ci_accepts_only_success():
    script, mapping = _aggregate()
    env = {**os.environ, **{name: "success" for name in mapping}}
    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", script], env=env, capture_output=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("job", sorted(ALL_REQUIRED))
@pytest.mark.parametrize("status", ["failure", "cancelled", "skipped", ""])
def test_required_ci_rejects_every_non_success(job, status):
    script, mapping = _aggregate()
    env = {**os.environ, **{name: "success" for name in mapping}}
    env[next(name for name, mapped in mapping.items() if mapped == job)] = status
    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", script], env=env, capture_output=True)
    assert result.returncode != 0, f"Required job {job} with status {status!r} was ignored"
