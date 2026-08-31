#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Mutant:
    name: str
    path: str
    old: str
    new: str
    command: tuple[str, ...]


SELF_TEST = ("scripts/run_agent_developer_adversarial_gate.py", "--self-test")
FULL_GATE = ("scripts/run_agent_developer_adversarial_gate.py",)

MUTANTS = (
    Mutant(
        "agent_projection_budget_guard",
        "scripts/run_agent_developer_adversarial_gate.py",
        "def _budget_exceeded(tokens: int, ceiling: int) -> bool:\n    return tokens > ceiling",
        "def _budget_exceeded(tokens: int, ceiling: int) -> bool:\n    return False  # mutation: disable per-call token budget",
        SELF_TEST,
    ),
    Mutant(
        "agent_trajectory_budget_guard",
        "scripts/run_agent_developer_adversarial_gate.py",
        "def _trajectory_budget_exceeded(tokens: int, ceiling: int) -> bool:\n    return tokens > ceiling",
        "def _trajectory_budget_exceeded(tokens: int, ceiling: int) -> bool:\n    return False  # mutation: disable trajectory token budget",
        SELF_TEST,
    ),
    Mutant(
        "agent_forbidden_source_guard",
        "scripts/run_agent_developer_adversarial_gate.py",
        "return tuple(sorted(source for source in actual if source in forbidden))",
        "return ()  # mutation: disable forbidden-source contamination detection",
        SELF_TEST,
    ),
    Mutant(
        "agent_exact_scope_guard",
        "scripts/run_agent_developer_adversarial_gate.py",
        "def _scope_matches(expected: dict[str, str], actual: dict[str, str]) -> bool:\n    return expected == actual",
        "def _scope_matches(expected: dict[str, str], actual: dict[str, str]) -> bool:\n    return True  # mutation: accept scope drift",
        SELF_TEST,
    ),
    Mutant(
        "agent_retry_candidate_guard",
        "scripts/run_agent_developer_adversarial_gate.py",
        "def _retry_candidate_valid(module_path: str, candidates: tuple[str, ...]) -> bool:\n    return module_path in candidates",
        "def _retry_candidate_valid(module_path: str, candidates: tuple[str, ...]) -> bool:\n    return True  # mutation: allow unreturned retry path",
        SELF_TEST,
    ),
    Mutant(
        "agent_edit_readiness_guard",
        "scripts/run_agent_developer_adversarial_gate.py",
        "def _edit_safe(payload: dict[str, Any] | None) -> bool:\n    return not base._authorizes_edit(payload)",
        "def _edit_safe(payload: dict[str, Any] | None) -> bool:\n    return True  # mutation: allow edit authorization on insufficient evidence",
        SELF_TEST,
    ),
    Mutant(
        "project_module_ambiguity_guard",
        "docmancer/docs/application/_project_docs_service_part01.py",
        "        if len(paths) > 1:\n            return None, {",
        "        if False and len(paths) > 1:  # mutation: silently select ambiguous module\n            return None, {",
        FULL_GATE,
    ),
    Mutant(
        "project_status_module_projection_guard",
        "docmancer/docs/interfaces/mcp/prefetch_tools.py",
        "_DOCS_STATUS_MODULE_LIMIT = 8",
        "_DOCS_STATUS_MODULE_LIMIT = 0  # mutation: hide module recovery inventory",
        FULL_GATE,
    ),
    Mutant(
        "module_recovery_reason_projection_guard",
        "docmancer/docs/interfaces/mcp/recovery_projection.py",
        "_MODULE_RECOVERY_REASON_CODES = frozenset({\n    \"module_ambiguous\", \"module_not_found\", \"no_module_docs\",\n})",
        "_MODULE_RECOVERY_REASON_CODES = frozenset({\n    \"module_not_found\", \"no_module_docs\",\n})  # mutation: hide ambiguous-module recovery metadata",
        FULL_GATE,
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
    for directory in ("docmancer", "eval", "scripts", "tests"):
        shutil.copytree(ROOT / directory, destination / directory, ignore=_ignore)
    for filename in ("pyproject.toml", "pytest.ini"):
        shutil.copy2(ROOT / filename, destination / filename)


def _environment(copy_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(copy_root) + (os.pathsep + existing if existing else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["DOCATLAS_OFFLINE"] = "1"
    return env


def _run(copy_root: Path, command: tuple[str, ...], name: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, *command],
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


def _apply_mutant(copy_root: Path, mutant: Mutant) -> None:
    path = copy_root / mutant.path
    source = path.read_text(encoding="utf-8")
    count = source.count(mutant.old)
    if count != 1:
        raise RuntimeError(
            f"{mutant.name}: exact mutation anchor count is {count}, expected 1"
        )
    path.write_text(source.replace(mutant.old, mutant.new, 1), encoding="utf-8")


def _new_copy() -> Path:
    temp_base = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    return Path(tempfile.mkdtemp(prefix="docatlas-agent-v2-mutant-", dir=temp_base))


def main() -> int:
    baseline_root = _new_copy()
    try:
        _copy_source(baseline_root)
        baseline = _run(baseline_root, SELF_TEST, "baseline-self-test")
        if baseline.returncode != 0:
            print(
                f"Agent Developer adversarial mutation gate: BASELINE FAIL; "
                f"artifacts={baseline_root}",
                file=sys.stderr,
            )
            return 1
        shutil.rmtree(baseline_root)

        for mutant in MUTANTS:
            copy_root = _new_copy()
            try:
                _copy_source(copy_root)
                _apply_mutant(copy_root, mutant)
                completed = _run(copy_root, mutant.command, mutant.name)
                if completed.returncode == 0:
                    print(
                        f"SURVIVED: {mutant.name}; artifacts={copy_root}",
                        file=sys.stderr,
                    )
                    return 1
                print(f"KILLED: {mutant.name}")
            except Exception as exc:
                print(
                    f"MUTATION ERROR: {mutant.name}: {exc}; artifacts={copy_root}",
                    file=sys.stderr,
                )
                return 1
            shutil.rmtree(copy_root)
    except Exception as exc:
        print(f"Agent Developer adversarial mutation gate error: {exc}", file=sys.stderr)
        return 1

    print(
        f"PASS: Agent Developer adversarial baseline green; "
        f"{len(MUTANTS)} critical mutants killed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
