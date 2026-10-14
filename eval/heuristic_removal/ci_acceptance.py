"""Exact-wheel, forty-question public MCP acceptance with unchanged source oracles.

The existing installed runner produces contexts; the existing offline evaluator
scores them. This adapter adds a fail-closed CI exit code, JUnit, whole-DTO budget
checks, immutable inputs, and explicit execution counts. No model answers, query
rewrites, retries, baseline aggregation, or changed oracle are introduced.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
CAP = 12000
EXPECTED_CASES = 40


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def execute(args: argparse.Namespace) -> int:
    import tiktoken

    output = args.output.resolve()
    if output.exists():
        raise ValueError("Use a fresh output directory; never overwrite execution receipts")
    output.mkdir(parents=True)
    wheel, interpreter = args.wheel.resolve(), args.python.absolute()
    dataset = REPO / "eval/prepared_model_comparison40"
    cases = json.loads((dataset / "questions.json").read_bytes())["cases"]
    if len(cases) != EXPECTED_CASES or len({row["id"] for row in cases}) != EXPECTED_CASES:
        raise ValueError("The frozen V40 input has changed shape")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    cache = Path(os.environ["TIKTOKEN_CACHE_DIR"]).resolve()
    codec = tiktoken.get_encoding("o200k_base")
    assets = [path for path in cache.rglob("*") if path.is_file()]
    if not assets:
        raise ValueError("Tokenizer assets must be prepared before the frozen product run")
    specification = {"path": str(dataset), "count": EXPECTED_CASES, "arms": ["V0"]}
    config = {
        "runtime_authorized": True,
        "authorization_reference": "Owner request 2026-10-14: consolidate PR211; integration and above only",
        "baseline_python": str(interpreter), "candidate_python": str(interpreter),
        "baseline_wheel": str(wheel), "candidate_wheel": str(wheel),
        "datasets": [specification], "common": {}, "trace": False,
        "packing_tokens": CAP, "tokenizer_cache_dir": str(cache),
        "limits": {"context_calls": EXPECTED_CASES, "call_seconds": 60,
                   "prepare_seconds": 180, "wall_seconds": 1800},
    }
    inputs = [wheel, *assets, REPO / "pyproject.toml", REPO / "uv.lock",
              REPO / "eval/evidence_quality_v2/runtime.py"]
    for directory in (REPO / "docmancer", REPO / "eval/heuristic_removal", dataset):
        inputs.extend(path for path in directory.rglob("*") if path.is_file()
                      and "__pycache__" not in path.parts and path.suffix != ".pyc")
    manifest = {
        "schema_version": 1, "base_commit": head, "config": config,
        "inputs_sha256": {str(path): digest(path) for path in sorted(set(inputs))},
        "planned_context_calls": EXPECTED_CASES,
        "boundary": "installed wheel, public in-process MCP, real SQLite; NOT stdio or generated answers",
        "baseline": "V0 is a compatibility lane label for this exact current head, NOT historical baseline",
        "generator_status": "NOT MEASURED",
    }
    manifest_path, worker_path = output / "FROZEN_RUN.json", output / "WORKER.json"
    save(manifest_path, manifest)
    save(worker_path, {"python": str(interpreter), "wall_seconds": 1800,
                       "datasets": [{**specification, "index": 0}]})
    (output / "head.txt").write_text(head + "\n", encoding="utf-8")
    execution_errors = []
    try:
        with tempfile.TemporaryDirectory(prefix=".docatlas-ci-v40-", dir=Path.home()) as raw:
            command = [str(interpreter), "-I", str(REPO / "eval/heuristic_removal/run.py"),
                       "--manifest", str(manifest_path), "--worker", str(worker_path),
                       "--output", str(output / "run/V0"), "--work", str(Path(raw) / "work")]
            with (output / "runtime.log").open("w", encoding="utf-8") as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                        cwd=Path(raw), timeout=1900, check=False)
            if result.returncode:
                execution_errors.append(f"installed runner exited {result.returncode}")
        command = [str(interpreter), "-I", str(REPO / "eval/heuristic_removal/assess.py"),
                   "--manifest", str(manifest_path), "--run-dir", str(output / "run"),
                   "--output", str(output / "assessment")]
        with (output / "assessment.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    cwd=output, timeout=180, check=False)
        if result.returncode:
            execution_errors.append(f"unchanged evaluator exited {result.returncode}")
    except Exception:
        execution_errors.append(traceback.format_exc())
    changed = [name for name, expected in manifest["inputs_sha256"].items()
               if not Path(name).is_file() or digest(Path(name)) != expected]
    if changed:
        execution_errors.append("frozen inputs changed: " + repr(changed))
    source_summary_path = output / "run/V0/SUMMARY.json"
    source_summary = json.loads(source_summary_path.read_bytes()) if source_summary_path.exists() else {}
    for key, expected in (("contexts", 40), ("preparations", 5), ("models", 0), ("resources", 0)):
        actual = source_summary.get("model_calls") if key == "models" else source_summary.get(key)
        if actual != expected:
            execution_errors.append(f"execution count {key}: {actual!r} != {expected}")
    scored_path = output / "assessment/CASE_RESULTS.json"
    records = json.loads(scored_path.read_bytes())["cases"] if scored_path.exists() else []
    keyed = {row["case_id"]: row for row in records}
    if len(records) != 40 or set(keyed) != {row["id"] for row in cases}:
        execution_errors.append("missing, duplicate or foreign V40 assessment cases")
    totals, results = Counter(), []
    suite = ET.Element("testsuite", name="source-native-installed-v40")
    for case in cases:
        row = keyed.get(case["id"], {})
        reasons = []
        checks = row.get("native", {})
        criterion = {"within_budget": "strict_positive_pass", "partial": "strict_partial_documented_pass",
                     "unanswerable": "strict_negative_empty_source_pass"}[case["answerability"]]
        if checks.get(criterion) is not True:
            reasons.append(criterion)
        if not row.get("read_only_pass") or row.get("runtime_integrity_errors") or checks.get("integrity_errors"):
            reasons.append("source_integrity_or_read_only")
        payload_path = output / "run/V0/calls/0" / case["id"] / "V0/public-payload.json"
        cost = None
        if payload_path.exists():
            payload = json.loads(payload_path.read_bytes())
            wire = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            cost = max(math.ceil(len(wire) / 4), len(codec.encode(wire.decode(), disallowed_special=())))
            if cost > CAP:
                reasons.append("whole_native_dto_over_budget")
            if any(payload.get(key) is True for key in ("answer_supported", "answer_available", "edit_ready")):
                reasons.append("retrieval_only_authority_escalation")
        else:
            reasons.append("public_payload_not_returned")
        item = {"id": case["id"], "answerability": case["answerability"],
                "passed": not reasons, "failures": reasons, "native_dto_cost": cost}
        results.append(item)
        totals[case["answerability"] + ("_passed" if not reasons else "_failed")] += 1
        node = ET.SubElement(suite, "testcase", classname="installed.public_mcp.V40", name=case["id"],
                             time=str(row.get("seconds", 0)))
        if reasons:
            ET.SubElement(node, "failure", message="; ".join(reasons)).text = json.dumps(item, ensure_ascii=False)
    if execution_errors:
        node = ET.SubElement(suite, "testcase", classname="installed.public_mcp.V40", name="execution_integrity")
        ET.SubElement(node, "error", message="execution incomplete or inputs changed").text = "\n".join(execution_errors)
    failures = sum(not row["passed"] for row in results)
    suite.set("tests", str(len(results) + bool(execution_errors)))
    suite.set("failures", str(failures))
    suite.set("errors", str(int(bool(execution_errors))))
    suite.set("skipped", "0")
    ET.ElementTree(suite).write(output / "integration.xml", encoding="utf-8", xml_declaration=True)
    summary = {"head": head, "wheel_sha256": digest(wheel), "passed": not failures and not execution_errors,
               "totals": dict(totals), "results": results, "execution_errors": execution_errors,
               "execution": {key: source_summary.get(key) for key in
                             ("status", "contexts", "preparations", "resources", "model_calls")},
               "frozen_inputs_unchanged": not changed, "budget": CAP,
               "oracle": "unchanged V40 source spans and strict-empty negative criteria",
               "generated_answers": "NOT MEASURED", "stdio": "NOT MEASURED by this lane"}
    save(output / "SUMMARY.json", summary)
    print(json.dumps({key: summary[key] for key in ("head", "passed", "totals", "execution", "execution_errors")}, indent=2))
    return 0 if summary["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True, help="Isolated installed-wheel interpreter")
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return execute(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
