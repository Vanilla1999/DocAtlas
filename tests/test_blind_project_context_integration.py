"""Opt-in integration gate: sealed blind questions through the real stdio MCP.

    DOCATLAS_BLIND_EVAL=1 python -m pytest tests/test_blind_project_context_integration.py

Optional: DOCATLAS_BLIND_JOBS (parallel fresh servers, default 2) and
DOCATLAS_BLIND_OUT (keep run directories). Needs the full git history because
the frozen corpora are rebuilt from git objects. Nothing is mocked: every case
starts from an unprepared isolated store, prepares through ``prepare_docs`` and
asks ``get_docs_context`` over stdio (see eval/blind_project_context).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "eval" / "blind_project_context"

pytestmark = [
    pytest.mark.advanced,
    pytest.mark.skipif(os.environ.get("DOCATLAS_BLIND_EVAL") != "1",
                       reason="set DOCATLAS_BLIND_EVAL=1 to run the blind project-context gate"),
]


def _python(*args: str, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def _rows(run: Path, corpus: str, case_id: str) -> list[dict]:
    sys.path.insert(0, str(EVAL))
    try:
        from score import rows_of
    finally:
        sys.path.remove(str(EVAL))
    return rows_of(json.loads((run / "payloads" / corpus / f"{case_id}.json").read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def out_dir(tmp_path_factory) -> Path:
    configured = os.environ.get("DOCATLAS_BLIND_OUT")
    if configured:
        path = Path(configured)
        path.mkdir(parents=True, exist_ok=True)
        return path
    return tmp_path_factory.mktemp("blind-project-context")


@pytest.fixture(scope="module", autouse=True)
def sealed_inputs():
    """Questions still match the seal; gold quotes sit in their drawn sections."""
    result = _python(str(EVAL / "audit.py"), "--check", timeout=600)
    assert result.returncode == 0, result.stderr[-3000:]


def test_observer_does_not_change_delivered_context(out_dir):
    """The observer is passive: same prepared store, same answer bytes with and without it.

    The first run prepares and keeps its store; the second asks the same cases
    against that store without the observer. Within one prepared generation the
    refs are equal, so every payload must match byte for byte.
    """
    cases = ("T03-ru", "T03-en")
    runs = {"observed": out_dir / "passive-observed", "plain": out_dir / "passive-plain"}
    work = out_dir / "passive-work"
    for name, extra in (("observed", ("--keep-work", "--env", "BLIND_OBSERVER_SELECTION=1")),
                        ("plain", ("--reuse-work", "--no-observer"))):
        arguments = [str(EVAL / "run.py"), str(runs[name]), "--corpus", "L0",
                     "--work-root", str(work), "--portions", "3", *extra]
        for case in cases:
            arguments += ["--case", case]
        result = _python(*arguments, timeout=1800)
        assert result.returncode == 0, result.stderr[-3000:]
    observed_files = sorted((runs["observed"] / "payloads" / "L0").glob("*.json"))
    plain_files = sorted((runs["plain"] / "payloads" / "L0").glob("*.json"))
    assert [path.name for path in observed_files] == [path.name for path in plain_files]
    assert len(observed_files) > len(cases), "fixture must exercise continuation"
    for observed, plain in zip(observed_files, plain_files):
        assert observed.read_bytes() == plain.read_bytes(), observed.name
    scored = _python(str(EVAL / "score.py"), str(runs["observed"]), timeout=900)
    assert scored.returncode == 0, scored.stdout[-3000:] + scored.stderr[-3000:]
    for case in cases:
        assert _rows(runs["observed"], "L0", case), case


def test_no_slice_is_worse_than_the_committed_baseline(out_dir):
    run = out_dir / "full"
    result = _python(str(EVAL / "run.py"), str(run), "--jobs", os.environ.get("DOCATLAS_BLIND_JOBS", "2"),
                     "--work-root", str(out_dir / "full-work"), "--portions", "3",
                     "--env", "BLIND_OBSERVER_SELECTION=1",
                     timeout=4 * 3600)
    assert result.returncode == 0, result.stderr[-3000:]
    scored = _python(str(EVAL / "score.py"), str(run), timeout=900)
    assert scored.returncode == 0, scored.stdout[-3000:] + scored.stderr[-3000:]
    gate = _python(str(EVAL / "gate.py"), str(EVAL / "baseline" / "score.json"), str(run / "score.json"),
                   "--details", str(run / "gate.json"), timeout=300)
    assert gate.returncode == 0, gate.stdout[-4000:] + gate.stderr[-2000:]
    result = json.loads((run / "score.json").read_text(encoding="utf-8"))
    previous = result["slices"]
    for portion in ("2", "3"):
        cumulative = result["cumulative_portions"][portion]
        assert not cumulative["anomalies"]
        for key, value in cumulative["slices"].items():
            assert value["facts_found"] >= previous[key]["facts_found"], (portion, key)
            assert value["all_found"] >= previous[key]["all_found"], (portion, key)
        previous = cumulative["slices"]
