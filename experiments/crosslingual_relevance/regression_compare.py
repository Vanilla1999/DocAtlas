"""Compare paired JUnit outcomes without calling missing/skipped tests GREEN.

A manifest equality check is necessary, not sufficient, for causal attribution.
A changed failure in an already failing test is not called a new regression.
Full-suite acceptance is deliberately not computed by this comparison utility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

COMPARABILITY_FIELDS = ("python_version", "dependencies_sha256", "command",
    "corpus_sha256", "retrieval_profile_sha256", "model_manifests_sha256", "environment_sha256")
FAILURES = {"failure", "error"}


def read_junit(path: Path) -> dict[str, dict]:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    result = {}
    for case in root.iter("testcase"):
        name = case.get("name")
        if not name:
            raise ValueError("JUnit testcase has no name")
        key = case.get("classname", "") + "::" + name
        if key in result:
            raise ValueError("duplicate JUnit identity; do not collapse reruns")
        failures = [element for element in case if element.tag in FAILURES]
        skipped = [element for element in case if element.tag == "skipped"]
        if failures and skipped:
            raise ValueError("ambiguous failed-and-skipped JUnit case")
        if failures:
            status = "error" if any(e.tag == "error" for e in failures) else "failure"
            signature = hashlib.sha256(json.dumps([
                [e.tag, e.get("type"), e.get("message"), e.text] for e in failures
            ], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        else:
            status, signature = ("skipped" if skipped else "passed"), None
        result[key] = {"status": status, "failure_signature": signature,
                       "skip_reason": skipped[0].get("message") if skipped else None}
    if not result:
        raise ValueError("empty JUnit report; no executed test evidence")
    # Some runners report a session failure outside testcase nodes.
    attributed = {e for case in root.iter("testcase") for e in case if e.tag in FAILURES}
    if any(e not in attributed for tag in FAILURES for e in root.iter(tag)):
        raise ValueError("unattributed session/collection error in JUnit")
    return result


def compare(baseline: dict, candidate: dict, baseline_manifest: dict, candidate_manifest: dict) -> dict:
    differences = [key for key in COMPARABILITY_FIELDS
        if key not in baseline_manifest or key not in candidate_manifest
        or baseline_manifest[key] != candidate_manifest[key]]
    if differences:
        return {"status": "BLOCKED_INCOMPARABLE", "different_or_missing_fields": differences,
                "full_regression_gate": "NOT_ESTABLISHED"}
    groups = {key: [] for key in ("new_failures_on_previously_passed_tests", "existing_identical_failures",
        "existing_tests_with_changed_failure", "fixed_failures", "still_passed", "candidate_skipped",
        "baseline_skipped", "candidate_missing", "new_tests_passed", "new_tests_failing",
        "new_tests_skipped", "inconclusive_transitions")}
    for key in sorted(set(baseline) | set(candidate)):
        old, new = baseline.get(key), candidate.get(key)
        if new is None: category = "candidate_missing"
        elif old is None:
            category = ("new_tests_passed" if new["status"] == "passed" else
                        "new_tests_skipped" if new["status"] == "skipped" else "new_tests_failing")
        elif new["status"] == "skipped": category = "candidate_skipped"
        elif old["status"] == "skipped": category = "baseline_skipped"
        elif old["status"] == "passed" and new["status"] in FAILURES:
            category = "new_failures_on_previously_passed_tests"
        elif old["status"] in FAILURES and new["status"] in FAILURES:
            category = ("existing_identical_failures" if old == new else "existing_tests_with_changed_failure")
        elif old["status"] in FAILURES and new["status"] == "passed": category = "fixed_failures"
        elif old["status"] == new["status"] == "passed": category = "still_passed"
        else: category = "inconclusive_transitions"
        groups[category].append(key)
    return {"status": "PAIRED_OUTCOMES_COMPARED", "counts": {k: len(v) for k, v in groups.items()},
            "groups": groups, "full_regression_gate": "NOT_ESTABLISHED",
            "causality": "paired outcomes only; classify collection and environment causes from logs"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("baseline", "candidate", "baseline_manifest", "candidate_manifest", "output"):
        parser.add_argument("--" + key.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = compare(read_junit(args.baseline), read_junit(args.candidate),
            json.loads(args.baseline_manifest.read_text()), json.loads(args.candidate_manifest.read_text()))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    except (OSError, ValueError, ET.ParseError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(result["status"])
    return 2 if result["status"] == "BLOCKED_INCOMPARABLE" else 0


if __name__ == "__main__":
    raise SystemExit(main())
