"""Accept a change only when no slice got worse.

    python eval/blind_project_context/gate.py BASE/score.json CANDIDATE/score.json [--details FILE]

Both runs must use the sealed questions and oracle, cover the same cases on
both corpora and have no anomalies (otherwise exit 2: not comparable). For each
split (dev, holdout) and each slice corpus x question language (L0/L2 x RU/EN)
the candidate must deliver at least as many gold facts and at least as many
fully answered cases as the baseline (otherwise exit 1: rejected). Exit 0
means accepted. Per-case dev changes are printed; holdout changes are only
counted here (the list goes to --details), so nobody tunes on them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SPLITS = ("dev", "holdout")
SLICES = tuple(f"{corpus}/{lang}" for corpus in ("L0", "L2") for lang in ("ru", "en"))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def comparable(base: dict, candidate: dict) -> list[str]:
    problems = []
    for key in ("schema_version", "questions_sha256", "oracle_sha256"):
        if base[key] != candidate[key]:
            problems.append(f"different {key}")
    keys = lambda score: sorted((case["corpus"], case["case_id"]) for case in score["cases"])
    if keys(base) != keys(candidate):
        problems.append("different case sets")
    expected = {f"{split}/{name}" for split in SPLITS for name in SLICES}
    for label, score in (("baseline", base), ("candidate", candidate)):
        if set(score["slices"]) != expected:
            problems.append(f"{label} does not cover every slice")
        problems.extend(f"{label} anomaly {item}" for item in score["anomalies"])
    return problems


def compare(base: dict, candidate: dict) -> dict:
    slices = {}
    for split in SPLITS:
        for name in SLICES:
            key = f"{split}/{name}"
            old, new = base["slices"][key], candidate["slices"][key]
            slices[key] = {metric: {"baseline": old[metric], "candidate": new[metric],
                                    "delta": new[metric] - old[metric]}
                           for metric in ("facts_found", "all_found", "limit_reached", "seconds")}
            slices[key]["worse"] = (new["facts_found"] < old["facts_found"]) or (new["all_found"] < old["all_found"])
    old_cases = {(case["corpus"], case["case_id"]): case for case in base["cases"]}
    flips = []
    for case in candidate["cases"]:
        old = old_cases[(case["corpus"], case["case_id"])]
        before = {fact["fact_id"] for fact in old["facts"] if fact["found"]}
        after = {fact["fact_id"] for fact in case["facts"] if fact["found"]}
        if before != after:
            flips.append({"split": case["split"], "corpus": case["corpus"], "case_id": case["case_id"],
                          "lost": sorted(before - after), "gained": sorted(after - before)})
    rows_changed = sorted(f"{case['corpus']}/{case['case_id']}" for case in candidate["cases"]
                          if case.get("rows_sha256") and old_cases[(case["corpus"], case["case_id"])].get("rows_sha256")
                          and case["rows_sha256"] != old_cases[(case["corpus"], case["case_id"])]["rows_sha256"])
    return {"accepted": not any(item["worse"] for item in slices.values()), "slices": slices, "flips": flips,
            "rows_changed": rows_changed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--details", type=Path)
    args = parser.parse_args()
    base, candidate = load(args.baseline), load(args.candidate)
    problems = comparable(base, candidate)
    if problems:
        print("NOT COMPARABLE:", *problems, sep="\n  ")
        return 2
    result = compare(base, candidate)
    print(f"{'slice':<18} {'facts':>12} {'all facts':>12} {'limit reached':>14}")
    for key, value in result["slices"].items():
        cell = lambda metric: f"{value[metric]['baseline']}->{value[metric]['candidate']}"
        print(f"{key:<18} {cell('facts_found'):>12} {cell('all_found'):>12} {cell('limit_reached'):>14}"
              + ("  WORSE" if value["worse"] else ""))
    for flip in result["flips"]:
        if flip["split"] == "dev":
            print(f"dev {flip['corpus']} {flip['case_id']}: lost {flip['lost'] or '-'} gained {flip['gained'] or '-'}")
    holdout = [flip for flip in result["flips"] if flip["split"] == "holdout"]
    print(f"holdout cases changed: {len(holdout)} (lost facts in {sum(bool(f['lost']) for f in holdout)})")
    # Border rows of the token budget vary between runs of one tree (see PROTOCOL_RU.md).
    print(f"cases with another delivered row set: {len(result['rows_changed'])}")
    if args.details:
        args.details.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ACCEPTED" if result["accepted"] else "REJECTED: a slice got worse")
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
