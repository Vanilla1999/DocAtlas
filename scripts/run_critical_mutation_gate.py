#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET_TESTS = (
    "tests/docs/test_normative_language.py::test_normative_modality_is_deterministic_and_preserves_legacy_cases",
    "tests/task_level/test_actionability.py::test_active_task33_protocol_has_public_actionability_contract",
    "tests/task_level/test_github_models_adapter.py::test_github_models_runner_stops_at_host_owned_turn_limit",
    "tests/docs/test_project_retrieval_alias_contract.py::test_current_alias_boundary_preserves_explicit_queries_without_inference",
    "tests/docs/test_project_query_intent_contract.py::test_current_project_intent_preserves_literals_and_never_infers_roles",
    "tests/docs/test_admission_meaning_contract.py::test_current_admission_meaning_preserves_literals_without_inferred_equivalence",
    "tests/docs/test_admission_local_binding_contract.py::test_current_default_binding_keeps_unknown_without_inherited_need_credit",
)
TARGET_CASE_COUNTS = (26, 1, 1, 1, 1, 1, 1)
TARGET_MODULES = (
    "docmancer.docs.domain.normative_language",
    "docmancer.docs.domain.project_retrieval_intent",
    "docmancer.docs.domain.project_query_intent",
    "docmancer.docs.domain.project_doc_ranking",
    "docmancer.docs.domain.query_terms",
    "docmancer.docs.domain.admission_meaning",
    "docmancer.docs.domain.admission_local_binding",
    "docmancer.docs.application.retrieval_need_support",
    "docmancer.docs.domain.admission_grammar",
    "docmancer.docs.domain.question_retrieval_needs",
    "docmancer.docs.domain.query_reference_binding",
    "docmancer.docs.domain.documentation_query_plan",
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
    compact_expected_failures: int | None = None


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
    Mutant(
        "project_retrieval_no_generated_aliases",
        "docmancer/docs/domain/project_retrieval_intent.py",
        "def build_project_retrieval_aliases(question: str) -> tuple[ProjectRetrievalAlias, ...]:\n"
        "    return ()",
        "def build_project_retrieval_aliases(question: str) -> tuple[ProjectRetrievalAlias, ...]:\n"
        '    return (ProjectRetrievalAlias("inferred_query", "invented lookup", True, "en"),)',
        TARGET_TESTS[3],
        1,
        "critical_alias_no_generated_queries",
    ),
    Mutant(
        "project_query_intent_no_inferred_roles",
        "docmancer/docs/domain/project_query_intent.py",
        "def classify_project_query_intent(question: str) -> ProjectQueryIntent:\n"
        '    return ProjectQueryIntent(name="general")',
        "def classify_project_query_intent(question: str) -> ProjectQueryIntent:\n"
        '    return ProjectQueryIntent(name="docs_mcp", wants_docs_mcp=True, wants_code_symbols=True)',
        TARGET_TESTS[4],
        1,
        "critical_project_intent_no_inferred_roles",
    ),
    Mutant(
        "admission_meaning_no_inferred_equivalence",
        "docmancer/docs/domain/admission_meaning.py",
        "def same_supported_meaning(left: AdmissionDemand, right: AdmissionDemand) -> bool:\n"
        '    """Equal supplied slots are not a witness of NL meaning equivalence."""\n'
        "    return False",
        "def same_supported_meaning(left: AdmissionDemand, right: AdmissionDemand) -> bool:\n"
        '    """Equal supplied slots are not a witness of NL meaning equivalence."""\n'
        "    return True",
        TARGET_TESTS[5],
        1,
        "critical_admission_meaning_no_inferred_equivalence",
    ),
    Mutant(
        "default_binding_unknown_not_true",
        "docmancer/docs/domain/admission_local_binding.py",
        "def default_local_witness(query: Mapping[str, Any], text: str\n"
        "                          ) -> tuple[bool | None, tuple[tuple[int, int], ...]]:\n"
        "    \"\"\"Preserve the tri-state ABI; no supported default relation is inferred.\"\"\"\n"
        "    return None, ()",
        "def default_local_witness(query: Mapping[str, Any], text: str\n"
        "                          ) -> tuple[bool | None, tuple[tuple[int, int], ...]]:\n"
        "    \"\"\"Preserve the tri-state ABI; no supported default relation is inferred.\"\"\"\n"
        "    return True, ()",
        TARGET_TESTS[6],
        1,
        "critical_default_binding_unknown_abi",
    ),
    Mutant(
        "default_binding_unknown_not_false",
        "docmancer/docs/domain/admission_local_binding.py",
        "def default_local_witness(query: Mapping[str, Any], text: str\n"
        "                          ) -> tuple[bool | None, tuple[tuple[int, int], ...]]:\n"
        "    \"\"\"Preserve the tri-state ABI; no supported default relation is inferred.\"\"\"\n"
        "    return None, ()",
        "def default_local_witness(query: Mapping[str, Any], text: str\n"
        "                          ) -> tuple[bool | None, tuple[tuple[int, int], ...]]:\n"
        "    \"\"\"Preserve the tri-state ABI; no supported default relation is inferred.\"\"\"\n"
        "    return False, ()",
        TARGET_TESTS[6],
        1,
        "critical_default_binding_unknown_abi",
    ),
    Mutant(
        "default_binding_unknown_cannot_qualify",
        "docmancer/docs/application/retrieval_need_support.py",
        "        result.update(qualified=False, qualification_reason=\"missing_need_local_witness\")",
        "        result.update(qualified=True, qualification_reason=\"missing_need_local_witness\")",
        TARGET_TESTS[6],
        1,
        "critical_default_binding_unknown_veto",
    ),
    Mutant(
        "default_binding_nonneeds_not_erased",
        "docmancer/docs/application/retrieval_need_support.py",
        "    result = dict(trace)",
        "    result = {}",
        TARGET_TESTS[6],
        1,
        "critical_default_binding_nonneeds_preserved",
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


def _environment(copy_root: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(copy_root) + (os.pathsep + existing if existing else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["DOCATLAS_OFFLINE"] = "1"
    env.pop("PYTEST_ADDOPTS", None)
    env.update(extra or {})
    return env


def _run(
    copy_root: Path, args: list[str], name: str,
    *, extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=copy_root,
        env=_environment(copy_root, extra_env),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=600,
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
    ast.parse(mutated, filename=str(path))
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
            "seconds": float(case.get("time", "0")),
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
        "testcase_seconds": sum(case["seconds"] for case in cases),
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
        raise RuntimeError(f"invalid baseline: expected {TARGET_CASE_COUNTS} passing cases, got {actual}; {report}")


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
    for pattern in ("*.junit.xml", "*.stdout.log", "*.stderr.log", "*.imports.json"):
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


_LITERAL_PLUGIN = "eval.task_level.literal_contract_reduction"
_LITERAL_HELPER = "eval/task_level/literal_contract_reduction.py"
_LITERAL_MANIFEST = "eval/task_level/literal_contract_mutations.json"


def _literal_protocol() -> tuple[dict[str, Any], tuple[Mutant, ...]]:
    protocol = json.loads((ROOT / _LITERAL_MANIFEST).read_text(encoding="utf-8"))
    if (protocol.get("schema_version") != 1
            or protocol.get("protocol") != "literal-contract-reduction-comparison-v1"
            or protocol.get("case_counts") != {"historical": [303, 399], "compact": [33, 49]}):
        raise RuntimeError("unreviewed literal comparison protocol or case counts")
    mutants = tuple(Mutant(**row["mutation"]) for row in protocol["mutations"])
    if not mutants or len({m.name for m in mutants}) != len(mutants):
        raise RuntimeError("literal comparison requires unique nonempty mutants")
    for mutant in mutants:
        if (not mutant.path.startswith("docmancer/docs/domain/") or ".." in Path(mutant.path).parts
                or mutant.killer.split("::", 1)[0] not in protocol["test_files"]
                or not mutant.failure_guard or not mutant.old or mutant.old == mutant.new
                or type(mutant.expected_failures) is not int or mutant.expected_failures < 1
                or type(mutant.compact_expected_failures) is not int or mutant.compact_expected_failures < 1):
            raise RuntimeError(f"invalid production comparison mutation: {mutant.name}")
    return protocol, mutants


def _literal_input_hashes(root: Path) -> dict[str, str]:
    # Freeze the tests, historical inputs, production source and collection
    # configuration. Only the one reviewed production mutation may differ.
    paths = [root / name for name in ("pyproject.toml", "pytest.ini", _LITERAL_HELPER, _LITERAL_MANIFEST)]
    for directory in ("docmancer", "tests"):
        paths.extend(path for path in (root / directory).rglob("*")
                     if path.is_file() and not any(part in {"__pycache__", ".pytest_cache"} for part in path.parts)
                     and path.suffix not in {".pyc", ".pyo"})
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


def _verify_literal_inputs(
    root: Path, expected: dict[str, str], mutation: dict[str, object] | None,
) -> None:
    wanted = dict(expected)
    if mutation:
        wanted[str(mutation["path"])] = str(mutation["after_sha256"])
    actual = _literal_input_hashes(root)
    if actual != wanted:
        changed = sorted(key for key in set(actual) | set(wanted) if actual.get(key) != wanted.get(key))
        raise RuntimeError(f"comparison inputs changed outside the reviewed mutation: {changed}")


def _literal_child(
    root: Path, *, mode: str, selections: tuple[str, ...], name: str,
    inputs: dict[str, str], mutation: dict[str, object] | None = None,
) -> tuple[dict[str, Any], int]:
    _verify_literal_inputs(root, inputs, mutation)
    imports = sorted({_LITERAL_HELPER, *(selection.split("::", 1)[0] for selection in selections),
                      *([str(mutation["path"])] if mutation else [])})
    import_report = root / f"{name}.imports.json"
    junit_path = root / f"{name}.junit.xml"
    started = time.monotonic()
    completed = _run(root, ["-m", "pytest", "-p", _LITERAL_PLUGIN, *selections, "-q", f"--junitxml={junit_path}"], name,
                     extra_env={"DOCATLAS_LITERAL_CONTRACT_MODE": mode, "PYTHONPATH": str(root),
                                "DOCATLAS_LITERAL_IMPORT_REPORT": str(import_report),
                                "DOCATLAS_LITERAL_IMPORT_PATHS": json.dumps(imports)})
    elapsed = time.monotonic() - started
    # A collection/setup/import failure is never an assertion kill, even if it
    # happens to leave an old-looking artifact on disk.
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"{name}: invalid child exit {completed.returncode}; no mutation credit")
    _verify_literal_inputs(root, inputs, mutation)
    identity = json.loads(import_report.read_text(encoding="utf-8"))
    if (identity.get("schema_version") != 1 or identity.get("mode") != mode
            or identity.get("exitstatus") != completed.returncode
            or set(identity.get("source_identity") or {}) != set(imports)):
        raise RuntimeError(f"{name}: missing or inconsistent same-process import evidence")
    for relative, row in identity["source_identity"].items():
        expected = root / relative
        if (row.get("expected_path") != str(expected.resolve())
                or row.get("imported_from_checkout") is not True or not row.get("imported_as")
                or row.get("sha256") != hashlib.sha256(expected.read_bytes()).hexdigest()):
            raise RuntimeError(f"{name}: pytest did not import the reviewed source: {relative}")
    report = _junit_report(junit_path)
    if completed.returncode != (1 if report["failures"] or report["errors"] else 0):
        raise RuntimeError(f"{name}: child exit contradicts JUnit outcomes")
    report.update(wall_seconds=elapsed, case_mode=mode, source_identity=identity["source_identity"],
                  input_roster_sha256=hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest())
    return report, completed.returncode


def _literal_baseline(report: dict[str, Any], mode: str, protocol: dict[str, Any]) -> None:
    classes = [name.removesuffix(".py").replace("/", ".") for name in protocol["test_files"]]
    counts = [sum(row["classname"] == name for row in report["cases"]) for name in classes]
    if (counts != protocol["case_counts"][mode] or report["tests"] != sum(counts)
            or any(report[key] for key in ("failures", "errors", "skipped"))):
        raise RuntimeError(f"{mode}: complete green literal baseline required; got {counts}")
    if mode == "historical" and report["roster_sha256"] != protocol["historical_baseline"]["roster_sha256"]:
        raise RuntimeError("historical questions, parameter identities or roster changed since the green baseline")


def _literal_evaluator_controls() -> tuple[str, ...]:
    """Known valid assertion plus invalid reports, without executing a mutant."""
    target = "tests/test_literal_control.py::test_expected"
    mutant = Mutant("control", "unused", "old", "new", target, 1, "literal_control")
    case = {"classname": "tests.test_literal_control", "name": "test_expected", "outcome": "passed", "message": ""}
    baseline = {"cases": [case]}
    valid = {"cases": [{**case, "outcome": "failure", "message": "AssertionError: literal_control"}],
             "failures": 1, "errors": 0, "skipped": 0}
    _validate_kill(valid, baseline, mutant)
    controls = ["expected_assertion_accepted"]
    invalid = {
        "missing_roster_rejected": {**valid, "cases": []},
        "skipped_case_rejected": {**valid, "skipped": 1},
        "setup_error_rejected": {**valid, "errors": 1},
        "wrong_assertion_rejected": {**valid, "cases": [{**case, "outcome": "failure", "message": "AssertionError: unrelated"}]},
        "runtime_exception_rejected": {**valid, "cases": [{**case, "outcome": "failure", "message": "KeyError: missing"}]},
        "survivor_rejected": {**valid, "failures": 0, "cases": [case]},
    }
    for name, report in invalid.items():
        try:
            _validate_kill(report, baseline, mutant)
        except RuntimeError:
            controls.append(name)
        else:
            raise RuntimeError(f"comparison evaluator accepted invalid evidence: {name}")
    return tuple(controls)


def _compare_literal_contracts(output: Path | None) -> int:
    evidence_root = output or Path(tempfile.mkdtemp(prefix="docatlas-literal-comparison-", dir=Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))))
    evidence_root.mkdir(parents=True, exist_ok=True)
    retained = []
    summary: dict[str, Any] = {"schema_version": 1, "protocol": "literal-contract-reduction-comparison-v1", "passed": False}
    try:
        protocol, mutants = _literal_protocol()
        inputs = _literal_input_hashes(ROOT)
        summary.update(historical_baseline=protocol["historical_baseline"], evaluator_controls=_literal_evaluator_controls())
        baselines = {}
        for mode in ("historical", "compact"):
            root = _new_copy()
            retained.append(root)
            name = f"baseline-{mode}"
            report, code = _literal_child(root, mode=mode, selections=tuple(protocol["test_files"]), name=name, inputs=inputs)
            _literal_baseline(report, mode, protocol)
            if code != 0:
                raise RuntimeError(f"{name}: baseline must be green")
            baselines[mode] = report
            _save_evidence(root, evidence_root, name, report, code)
            shutil.rmtree(root)
            retained.remove(root)
        historical_ids = {(row["classname"], row["name"]) for row in baselines["historical"]["cases"]}
        compact_ids = {(row["classname"], row["name"]) for row in baselines["compact"]["cases"]}
        if not compact_ids <= historical_ids:
            raise RuntimeError("compact case selection invented or changed historical input identities")
        summary["baselines"] = {mode: {key: value for key, value in report.items() if key not in {"cases", "source_identity"}}
                                for mode, report in baselines.items()}
        kills = []
        for mutant in mutants:
            comparisons = {}
            for mode in ("historical", "compact"):
                root = _new_copy()
                retained.append(root)
                mutation = _apply_mutant(root, mutant)
                name = f"{mutant.name}-{mode}"
                report, code = _literal_child(root, mode=mode, selections=(mutant.killer,), name=name, inputs=inputs, mutation=mutation)
                if code != 1:
                    raise RuntimeError(f"{name}: production mutant survived")
                expected = mutant if mode == "historical" else replace(mutant, expected_failures=mutant.compact_expected_failures)
                _validate_kill(report, baselines[mode], expected)
                _save_evidence(root, evidence_root, name, report, code, mutation)
                comparisons[mode] = {key: report[key] for key in ("tests", "failures", "roster_sha256", "wall_seconds", "testcase_seconds")}
                shutil.rmtree(root)
                retained.remove(root)
            kills.append({"name": mutant.name, "guard": mutant.failure_guard, "modes": comparisons})
            print(f"COMPARE KILLED: {mutant.name}; both case selections hit {mutant.failure_guard}")
        summary.update(passed=True, mutations=kills, activated_compact_default=False,
                       activation="Separate reviewed default change only after this exact-SHA comparison is green.")
    except Exception as exc:
        summary.update(error=str(exc), retained_workspaces=[str(path) for path in retained])
        print(f"LITERAL COMPARISON ERROR: {exc}; retained={retained}", file=sys.stderr)
    (evidence_root / "comparison.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Literal comparison {'PASS' if summary['passed'] else 'FAIL'}; evidence={evidence_root}")
    return 0 if summary["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Critical mutations or a staged literal-contract case comparison")
    parser.add_argument("--compare-literal-contracts", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.compare_literal_contracts:
        return _compare_literal_contracts(args.output_dir.resolve() if args.output_dir else None)
    if args.output_dir:
        parser.error("--output-dir is available with --compare-literal-contracts")
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
            # Read the existing JUnit only. No rerun and no traceback/body dump.
            try:
                failed_report = _junit_report(baseline_report)
            except (OSError, ValueError, RuntimeError, ET.ParseError) as exc:
                diagnostic = {"junit_status": "unreadable", "error_type": type(exc).__name__}
            else:
                failed_cases = [case for case in failed_report["cases"]
                                if case["outcome"] != "passed"]
                diagnostic = {
                    "junit_status": "readable", "returncode": baseline.returncode,
                    **{key: failed_report[key] for key in ("tests", "failures", "errors", "skipped")},
                    "first_failures": [{
                        "classname": case["classname"][:240], "name": case["name"][:240],
                        "outcome": case["outcome"],
                        "message": case["message"].split("\n", 1)[0][:320],
                    } for case in failed_cases[:3]],
                    "omitted_failures": max(0, len(failed_cases) - 3),
                }
            print("BASELINE_DIAGNOSTIC: " + json.dumps(diagnostic, sort_keys=True), file=sys.stderr)
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
