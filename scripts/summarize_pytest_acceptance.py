"""Summarize existing pytest JUnit artifacts without running project code."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET


def _module_map(root: Path) -> list[tuple[str, str]]:
    entries = [
        (".".join(path.relative_to(root).with_suffix("").parts), path.relative_to(root).as_posix())
        for path in (root / "tests").rglob("test_*.py")
    ]
    return sorted(entries, key=lambda entry: len(entry[0]), reverse=True)


def _node(case: ET.Element, modules: list[tuple[str, str]]) -> tuple[str, str]:
    classname, name = case.get("classname", ""), case.get("name", "")
    for dotted, path in modules:
        if classname == dotted or classname.startswith(dotted + "."):
            classes = classname[len(dotted):].lstrip(".").split(".")
            return "::".join([path, *(value for value in classes if value), name]), path
    path = case.get("file")
    if path:
        return "::".join([path, classname, name]), path
    return "::".join([classname, name]), classname


def _read(path: Path, modules: list[tuple[str, str]], root: Path) -> dict:
    data = path.read_bytes()
    xml = ET.fromstring(data)
    rows = []
    for case in xml.iter("testcase"):
        node, module = _node(case, modules)
        failures = list(case.findall("failure"))
        errors = list(case.findall("error"))
        skipped = list(case.findall("skipped"))
        outcome = "ERROR" if errors else "FAIL" if failures else "SKIP" if skipped else "PASS"
        reasons = [
            {"kind": element.tag, "message": element.get("message", ""), "trace": element.text or ""}
            for element in [*errors, *failures, *skipped]
        ]
        rows.append({"node": node, "module": module, "outcome": outcome, "reasons": reasons})
    counts = Counter(row["outcome"] for row in rows)
    occurrences = Counter(row["node"] for row in rows)
    duplicates = {node: count for node, count in occurrences.items() if count > 1}
    suites = list(xml.iter("testsuite"))
    declared = {
        key: sum(int(suite.get(key, "0")) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    actual = {"tests": len(rows), "failures": counts["FAIL"], "errors": counts["ERROR"], "skipped": counts["SKIP"]}
    integrity = []
    if declared != actual:
        integrity.append({"reason": "suite_counts_differ_from_testcase_counts", "declared": declared, "actual": actual})
    if duplicates:
        integrity.append({"reason": "duplicate_concrete_node_ids", "nodes": duplicates})
    return {
        "artifact_file": path.relative_to(root).as_posix(),
        "xml_sha256": hashlib.sha256(data).hexdigest(),
        "counts": {key: counts[key] for key in ("PASS", "FAIL", "ERROR", "SKIP")},
        "integrity_issues": integrity,
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args()
    modules = _module_map(args.source_root)
    files = sorted(args.input_dir.rglob("core-tests-*.xml"))
    if not files:
        raise SystemExit("No core JUnit artifacts were downloaded; acceptance is unknown.")
    reports = [_read(path, modules, args.input_dir) for path in files]
    report = {
        "schema_version": 1,
        "purpose": "diagnostics_only",
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "checkout_commit": os.environ.get("GITHUB_SHA"),
        "reports": reports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    # Bound only console transport; the artifact above retains every complete case.
    remaining_bytes = 256_000
    omitted_console_rows = 0

    def emit(prefix: str, value: dict) -> None:
        nonlocal remaining_bytes, omitted_console_rows
        line = prefix + " " + json.dumps(value, ensure_ascii=False)
        size = len(line.encode("utf-8")) + 1
        if size > remaining_bytes:
            omitted_console_rows += 1
            return
        print(line)
        remaining_bytes -= size

    # Each Python lane has its own counts. Never add matrix repetitions together.
    for lane in reports:
        emit("JUNIT_COUNTS", {key: value for key, value in lane.items() if key != "cases"})
    preferred = next((lane for lane in reports if lane["artifact_file"].endswith("core-tests-3.13.xml")), reports[0])
    by_module = defaultdict(Counter)
    first_failure = {}
    for row in preferred["cases"]:
        by_module[row["module"]][row["outcome"]] += 1
        if row["outcome"] in {"FAIL", "ERROR"}:
            first_failure.setdefault(row["module"], row)
    for module, counts in sorted(by_module.items()):
        if counts["FAIL"] or counts["ERROR"]:
            first = first_failure[module]
            message = next((reason["message"] for reason in first["reasons"] if reason["kind"] in {"failure", "error"}), "")
            emit("JUNIT_MODULE", {"module": module, "counts": dict(counts),
                                  "first_node": first["node"], "first_message": message[:500]})
    focused = {
        "tests/docs/test_docs_context_read_next.py",
        "tests/docs/test_action_packet.py",
        "tests/test_project_context_quality_v2_protocol.py",
        "tests/docs/test_discovery_independent_qualification.py",
        "tests/docs/test_source_map.py",
    }
    for row in preferred["cases"]:
        if row["outcome"] not in {"FAIL", "ERROR"}:
            continue
        if row["module"] in focused or "delivery_veto_observer" in row["node"]:
            details = [
                {**reason, "message": reason["message"][:2000], "trace": reason["trace"][-6000:]}
                for reason in row["reasons"]
            ]
            emit("JUNIT_FOCUSED", {**row, "reasons": details})
    print("JUNIT_CONSOLE " + json.dumps({"omitted_rows": omitted_console_rows, "complete_cases_in_artifact": True}))
    # This reports artifact integrity, not test acceptance; required-ci still reads test jobs.
    return 2 if any(lane["integrity_issues"] for lane in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
