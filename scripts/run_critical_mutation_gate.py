#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_TESTS = (
    "tests/docs/test_normative_language.py::test_normative_modality_is_deterministic_and_preserves_legacy_cases",
    "tests/task_level/test_actionability.py::test_active_task33_protocol_has_public_actionability_contract",
    "tests/task_level/test_github_models_adapter.py::test_github_models_runner_stops_at_host_owned_turn_limit",
)
TARGET_MODULES = (
    "docmancer.docs.domain.normative_language",
    "eval.task_level.evaluators.actionability",
    "eval.task_level.github_models",
)


@dataclass(frozen=True)
class Mutant:
    name: str
    path: str
    old: str
    new: str
    killer: str


MUTANTS = (
    Mutant(
        "normative_code_declaration_guard",
        "docmancer/docs/domain/normative_language.py",
        "if _CODE_DECLARATION_RE.search(text):",
        "if False:  # mutation: disable code declaration guard",
        TARGET_TESTS[0],
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
        "eval/task_level/github_models.py",
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
    env["DOCMANCER_OFFLINE"] = "1"
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
        "from pathlib import Path; "
        f"root=Path({str(copy_root)!r}).resolve(); "
        f"mods={TARGET_MODULES!r}; "
        "import importlib; "
        "paths=[Path(importlib.import_module(name).__file__).resolve() for name in mods]; "
        "assert all(path.is_relative_to(root) for path in paths), paths; "
        "print('\\n'.join(str(path) for path in paths))"
    )
    completed = _run(copy_root, ["-c", expression], "import-origin")
    if completed.returncode != 0:
        raise RuntimeError("import-origin probe failed")


def _apply_mutant(copy_root: Path, mutant: Mutant) -> None:
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


def _new_copy() -> Path:
    temp_base = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    copy_root = Path(tempfile.mkdtemp(prefix="docmancer-mutation-", dir=temp_base))
    _copy_source(copy_root)
    return copy_root


def _junit_counts(path: Path) -> tuple[int, int, int]:
    suites = ET.parse(path).getroot().iter("testsuite")
    counts = [
        (
            int(suite.attrib.get("tests", "0")),
            int(suite.attrib.get("failures", "0")),
            int(suite.attrib.get("errors", "0")),
        )
        for suite in suites
    ]
    if not counts:
        raise RuntimeError(f"JUnit report contains no testsuite: {path}")
    return (
        sum(count[0] for count in counts),
        sum(count[1] for count in counts),
        sum(count[2] for count in counts),
    )


def main() -> int:
    retained: list[Path] = []
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
        baseline_tests, baseline_failures, baseline_errors = _junit_counts(baseline_report)
        if (
            baseline_tests < len(TARGET_TESTS)
            or baseline_failures != 0
            or baseline_errors != 0
        ):
            retained.append(baseline_root)
            print(f"INVALID BASELINE JUNIT; artifacts retained at {baseline_root}", file=sys.stderr)
            return 1
        shutil.rmtree(baseline_root)

        for mutant in MUTANTS:
            copy_root = _new_copy()
            try:
                _assert_import_origins(copy_root)
                _apply_mutant(copy_root, mutant)
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
                tests, failures, errors = _junit_counts(mutant_report)
                if completed.returncode != 1 or tests < 1 or failures < 1 or errors != 0:
                    retained.append(copy_root)
                    print(
                        f"INVALID MUTANT RUN: {mutant.name} exited {completed.returncode}; "
                        f"junit tests={tests}, failures={failures}, errors={errors}; "
                        f"artifacts retained at {copy_root}",
                        file=sys.stderr,
                    )
                    return 1
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

    print(f"PASS: baseline green; {len(MUTANTS)} critical mutants killed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
