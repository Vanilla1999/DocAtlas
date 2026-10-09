#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET_TESTS = (
    "tests/docs/test_normative_language.py::test_normative_modality_is_deterministic_and_preserves_legacy_cases",
    "tests/task_level/test_actionability.py::test_active_task33_protocol_has_public_actionability_contract",
    "tests/task_level/test_github_models_adapter.py::test_github_models_runner_stops_at_host_owned_turn_limit",
)
TARGET_CASE_COUNTS = (26, 1, 1)
TARGET_MODULES = (
    "docmancer.docs.domain.normative_language",
    "docmancer.docs.application.action_packet",
    "docmancer.docs.application._action_packet_shared",
    "docmancer.docs.application._action_packet_part01",
    "docmancer.docs.application._action_packet_part03",
    "docmancer.docs.application._action_packet_part04",
    "docmancer.docs.application.evidence_selection",
    "docmancer.docs.application._evidence_selection_part01",
    "docmancer.docs.application._evidence_selection_part03",
    "docmancer.docs.application.evidence_candidates",
    "docmancer.docs.application.evidence_requirements",
    "eval.task_level.evaluators.actionability",
    "eval.task_level.github_models",
    "eval.task_level._github_models_part02",
)


@dataclass(frozen=True)
class Mutant:
    name: str
    path: str
    old: str
    new: str
    killer: str
    expected_failures: int = 1
    failure_guard: str | None = None


MUTANTS = (
    Mutant(
        "normative_python_declaration_recognition",
        "docmancer/docs/domain/normative_language.py",
        "declaration_lines.update(range(line_index, end_index + 1))",
        "declaration_lines.update(())",
        TARGET_TESTS[0],
        15,
        "critical_python_declaration_grammar",
    ),
    Mutant(
        "normative_no_implicit_authority",
        "docmancer/docs/domain/normative_language.py",
        'def classify_normative_modality(value: str) -> NormativeModality | None:\n'
        '    """Compatibility adapter: source prose does not establish policy modality."""\n'
        '    return None',
        'def classify_normative_modality(value: str) -> NormativeModality | None:\n'
        '    """Compatibility adapter: source prose does not establish policy modality."""\n'
        '    return "required"',
        TARGET_TESTS[0],
        26,
        "critical_normative_no_authority",
    ),
    Mutant(
        "normative_whole_source_delivery",
        "docmancer/docs/application/_action_packet_part03.py",
        '"text": candidate.display_text,',
        '"text": candidate.display_text[:-1],',
        TARGET_TESTS[0],
        9,
        "critical_source_delivery_fidelity",
    ),
    Mutant(
        "normative_bound_source_fidelity",
        "docmancer/docs/application/_action_packet_part04.py",
        "if candidate is None or source != _candidate_source(candidate):",
        "if False:  # mutation: disable bound source fidelity",
        TARGET_TESTS[0],
        9,
        "critical_bound_source_fidelity",
    ),
    Mutant(
        "active_task33_actionability_contract",
        "eval/task_level/evaluators/actionability.py",
        "if task_id == TASK33C_PILOT_TASK_ID:",
        "if False:  # mutation: disable active Task33 contract",
        TARGET_TESTS[1],
    ),
    Mutant(
        "github_models_host_turn_limit",
        "eval/task_level/_github_models_part02.py",
        "for turn in range(1, request.max_turns + 1):",
        "for turn in range(1, request.max_turns + 2):",
        TARGET_TESTS[2],
    ),
)


def _ignore(directory: str, names: list[str]) -> set[str]:
    path = Path(directory)
    ignored = {
        name
        for name in names
        if name in {".git", ".venv", ".pytest_cache", "__pycache__"}
        or name.endswith((".pyc", ".pyo"))
    }
    relative = path.relative_to(ROOT) if path != ROOT else Path()
    if relative == Path("eval/task_level"):
        ignored.update({"results", "runtime", "workspaces", "oracles", "hidden_tests"})
    return ignored


def _copy_source(destination: Path) -> None:
    for directory in ("docmancer", "eval", "tests"):
        shutil.copytree(ROOT / directory, destination / directory, ignore=_ignore)
    for filename in ("pyproject.toml", "pytest.ini"):
        shutil.copy2(ROOT / filename, destination / filename)


def _environment(copy_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(copy_root) + (os.pathsep + existing if existing else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["DOCATLAS_OFFLINE"] = "1"
    env.pop("PYTEST_ADDOPTS", None)
    return env


def _run(copy_root: Path, args: list[str], name: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=copy_root,
        env=_environment(copy_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    (copy_root / f"{name}.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (copy_root / f"{name}.stderr.log").write_text(completed.stderr, encoding="utf-8")
    return completed


def _assert_import_origins(copy_root: Path) -> None:
    expression = (
        "from pathlib import Path\n"
        "import hashlib, importlib, json\n"
        f"root = Path({str(copy_root)!r}).resolve()\n"
        f"mods = {TARGET_MODULES!r}\n"
        "rows = []\n"
        "for name in mods:\n"
        "    path = Path(importlib.import_module(name).__file__).resolve()\n"
        "    assert path.is_relative_to(root), (name, str(path))\n"
        "    rows.append({'module': name, 'path': str(path),\n"
        "                 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})\n"
        "print(json.dumps(rows, sort_keys=True))\n"
    )
    completed = _run(copy_root, ["-c", expression], "import-origin")
    if completed.returncode != 0:
        raise RuntimeError("import-origin probe failed")


def _apply_mutant(copy_root: Path, mutant: Mutant) -> dict[str, object]:
    path = copy_root / mutant.path
    source = path.read_text(encoding="utf-8")
    if source.count(mutant.old) != 1:
        raise RuntimeError(
            f"{mutant.name}: exact mutation anchor count is {source.count(mutant.old)}, expected 1"
        )
    before = hashlib.sha256(source.encode()).hexdigest()
    mutated = source.replace(mutant.old, mutant.new, 1)
    after = hashlib.sha256(mutated.encode()).hexdigest()
    if before == after:
        raise RuntimeError(f"{mutant.name}: mutation did not change source hash")
    path.write_text(mutated, encoding="utf-8")
    if hashlib.sha256(path.read_bytes()).hexdigest() != after:
        raise RuntimeError(f"{mutant.name}: written source hash differs from mutation")
    return {
        "name": mutant.name, "path": mutant.path, "anchor_count": 1,
        "before_sha256": before, "after_sha256": after,
        "old": mutant.old, "new": mutant.new, "killer": mutant.killer,
        "expected_failures": mutant.expected_failures,
        "failure_guard": mutant.failure_guard,
    }


def _new_copy() -> Path:
    temp_base = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    copy_root = Path(tempfile.mkdtemp(prefix="docmancer-mutation-", dir=temp_base))
    _copy_source(copy_root)
    return copy_root


def _junit_report(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    suites = list(root.iter("testsuite"))
    if not suites:
        raise RuntimeError(f"JUnit report contains no testsuite: {path}")
    counts = {
        key: sum(int(suite.attrib.get(key, "0")) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    cases = []
    for case in root.iter("testcase"):
        outcomes = [child for child in case if child.tag in {"failure", "error", "skipped"}]
        if len(outcomes) > 1:
            raise RuntimeError("JUnit testcase contains multiple outcomes")
        cases.append({
            "classname": case.get("classname", ""), "name": case.get("name", ""),
            "outcome": outcomes[0].tag if outcomes else "passed",
            "message": outcomes[0].get("message", "") if outcomes else "",
        })
    observed = {
        "tests": len(cases),
        **{key: sum(case["outcome"] == outcome for case in cases)
           for key, outcome in (("failures", "failure"), ("errors", "error"), ("skipped", "skipped"))},
    }
    if counts != observed:
        raise RuntimeError(f"JUnit summary differs from testcase outcomes: {counts} != {observed}")
    roster = sorted((case["classname"], case["name"]) for case in cases)
    if len(set(roster)) != len(roster) or any(not all(identity) for identity in roster):
        raise RuntimeError("JUnit contains duplicate or empty testcase identities")
    return {
        **counts, "cases": cases,
        "roster_sha256": hashlib.sha256(json.dumps(roster, ensure_ascii=False).encode()).hexdigest(),
    }


def _target_cases(report: dict[str, Any], target: str) -> list[dict[str, str]]:
    path, name = target.split("::", 1)
    classname = path.removesuffix(".py").replace("/", ".")
    return [case for case in report["cases"]
            if case["classname"] == classname
            and (case["name"] == name or case["name"].startswith(name + "["))]


def _validate_baseline(report: dict[str, Any]) -> None:
    actual = tuple(len(_target_cases(report, target)) for target in TARGET_TESTS)
    if (actual != TARGET_CASE_COUNTS or report["tests"] != sum(TARGET_CASE_COUNTS)
            or any(report[key] != 0 for key in ("failures", "errors", "skipped"))):
        raise RuntimeError(f"invalid baseline: expected 26+1+1 passing cases, got {actual}; {report}")


def _validate_kill(report: dict[str, Any], baseline: dict[str, Any], mutant: Mutant) -> None:
    expected = {(case["classname"], case["name"])
                for case in _target_cases(baseline, mutant.killer)}
    observed = {(case["classname"], case["name"]) for case in report["cases"]}
    if (not expected or observed != expected or report["failures"] != mutant.expected_failures
            or report["errors"] != 0 or report["skipped"] != 0):
        raise RuntimeError(f"{mutant.name}: invalid mutant roster/outcomes: {report}")
    for case in report["cases"]:
        if case["outcome"] != "failure":
            continue
        message = case["message"]
        if not message.startswith(("AssertionError", "assert ")):
            raise RuntimeError(f"{mutant.name}: killer failed without an assertion: {message}")
        # A traceback can print other, unexecuted assertions from the same test.
        # Only the failure message itself can establish the intended guard.
        if mutant.failure_guard is not None and message.splitlines()[0] != (
            "AssertionError: " + mutant.failure_guard
        ):
            raise RuntimeError(f"{mutant.name}: wrong assertion guard: {message}")


def _save_evidence(
    copy_root: Path, evidence_root: Path, name: str,
    report: dict[str, Any], returncode: int, mutation: dict[str, object] | None = None,
) -> None:
    destination = evidence_root / name
    destination.mkdir()
    for pattern in ("*.junit.xml", "*.stdout.log", "*.stderr.log"):
        for path in copy_root.glob(pattern):
            shutil.copy2(path, destination / path.name)
    evidence = {"run": name, "validated": True, "returncode": returncode,
                "junit": report, "mutation": mutation}
    (destination / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    summary = {key: value for key, value in report.items() if key != "cases"}
    print("EVIDENCE: " + json.dumps(
        {"run": name, "returncode": returncode, **summary, "mutation": mutation}, sort_keys=True,
    ))


def main() -> int:
    retained: list[Path] = []
    temp_base = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    evidence_root = Path(tempfile.mkdtemp(prefix="docmancer-mutation-evidence-", dir=temp_base))
    baseline_root = _new_copy()
    try:
        _assert_import_origins(baseline_root)
        baseline_report = baseline_root / "baseline.junit.xml"
        baseline = _run(
            baseline_root,
            ["-m", "pytest", *TARGET_TESTS, "-q", f"--junitxml={baseline_report}"],
            "baseline",
        )
        if baseline.returncode != 0:
            retained.append(baseline_root)
            print(f"BASELINE FAILED; artifacts retained at {baseline_root}", file=sys.stderr)
            return 1
        baseline_evidence = _junit_report(baseline_report)
        _validate_baseline(baseline_evidence)
        _save_evidence(baseline_root, evidence_root, "baseline", baseline_evidence, baseline.returncode)
        shutil.rmtree(baseline_root)

        for mutant in MUTANTS:
            copy_root = _new_copy()
            try:
                mutation = _apply_mutant(copy_root, mutant)
                _assert_import_origins(copy_root)
                mutant_report = copy_root / f"{mutant.name}.junit.xml"
                completed = _run(
                    copy_root,
                    [
                        "-m",
                        "pytest",
                        mutant.killer,
                        "-q",
                        f"--junitxml={mutant_report}",
                    ],
                    mutant.name,
                )
                if completed.returncode == 0:
                    retained.append(copy_root)
                    print(
                        f"SURVIVED: {mutant.name}; artifacts retained at {copy_root}",
                        file=sys.stderr,
                    )
                    return 1
                report = _junit_report(mutant_report)
                if completed.returncode != 1:
                    retained.append(copy_root)
                    print(
                        f"INVALID MUTANT RUN: {mutant.name} exited {completed.returncode}; "
                        f"artifacts retained at {copy_root}",
                        file=sys.stderr,
                    )
                    return 1
                _validate_kill(report, baseline_evidence, mutant)
                _save_evidence(copy_root, evidence_root, mutant.name, report, completed.returncode, mutation)
                print(f"KILLED: {mutant.name}")
            except Exception:
                retained.append(copy_root)
                raise
            if copy_root not in retained:
                shutil.rmtree(copy_root)
    except Exception as exc:
        if baseline_root.exists() and baseline_root not in retained:
            retained.append(baseline_root)
        print(f"MUTATION GATE ERROR: {exc}", file=sys.stderr)
        for path in retained:
            print(f"artifacts retained at {path}", file=sys.stderr)
        return 1

    print(f"PASS: baseline green; {len(MUTANTS)} critical mutants killed; evidence at {evidence_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
