"""Publish aggregate evidence without exposing held-out questions or quotes.

python eval/blind_project_context/summarize_study.py OUT.json --run baseline=DIR --run portions=DIR
Only previously scored outputs are read. The original single-call gate is
unchanged. Union comparisons are descriptive unions of already credited facts,
not a new runtime policy or a test of the answering agent.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from statistics import mean, median


def aggregate(cases: list[dict]) -> dict:
    if any("o200k_tokens" not in case for case in cases):
        raise ValueError("re-score this run with the current score.py to measure output tokens")
    costs = [case["o200k_tokens"] for case in cases]
    return {
        "cases": len(cases), "facts_found": sum(case["facts_found"] for case in cases),
        "facts_total": sum(case["facts_total"] for case in cases),
        "all_found": sum(case["all_found"] for case in cases),
        "mean_output_tokens": round(mean(costs), 1) if costs else 0,
        "median_output_tokens": median(costs) if costs else 0,
        "total_output_tokens": sum(costs),
        "mean_output_bytes": round(mean(case.get("utf8_bytes", 0) for case in cases), 1) if cases else 0,
        "calls": sum(case.get("calls", 1) for case in cases),
        "delivery_budget_cases": sum(bool((case.get("limits", {}).get("delivery") or {}).get("budget_limited"))
                                     for case in cases),
        "reference_limit_cases": sum(bool((case.get("limits", {}).get("delivery") or {}).get("reference_limited"))
                                     for case in cases),
    }


def loss_stages(score: dict, run: dict) -> dict:
    """A cause is assigned only when every observed copy has that same fate."""
    records = {(record["corpus"], record["case_id"]): record for record in run["records"]}
    counts = defaultdict(Counter)
    for case in score["cases"]:
        if case["split"] != "dev":
            continue
        record = records[(case["corpus"], case["case_id"])]
        selections = [event for event in record.get("observer_events", ()) if event.get("event") == "joint_selection"]
        stages = selections[-1].get("fact_stages", {}) if selections else {}
        key = f"dev/{case['corpus']}/{case['lang']}"
        for fact in case["facts"]:
            if fact["found"]:
                label = "delivered"
            elif fact.get("in_candidates") is False:
                label = "not_acquired"
            elif fact["fact_id"] not in stages:
                label = "not_observed"
            else:
                stage = stages[fact["fact_id"]]
                reasons = stage["stages"]
                label = ("before_checked_pool" if not stage["checked_rows"] else
                         reasons[0] if len(reasons) == 1 else "multiple_stages:" + "+".join(reasons))
            counts[key][label] += 1
    total = sum(counts.values(), Counter())
    return {"dev_total": dict(sorted(total.items())),
            "slices": {key: dict(sorted(value.items())) for key, value in sorted(counts.items())}}


def union_credited(left: dict, right: dict) -> dict:
    """Combine only facts independently credited by each original scorer."""
    left_cases = {(case["corpus"], case["case_id"]): case for case in left["cases"]}
    right_cases = {(case["corpus"], case["case_id"]): case for case in right["cases"]}
    if left_cases.keys() != right_cases.keys():
        raise ValueError("union needs identical cases")
    slices = defaultdict(lambda: Counter(facts_found=0, facts_total=0, all_found=0, cases=0))
    for key, first in left_cases.items():
        second = right_cases[key]
        if {fact["fact_id"] for fact in first["facts"]} != {fact["fact_id"] for fact in second["facts"]}:
            raise ValueError("union needs identical facts")
        found = {fact["fact_id"] for case in (first, second) for fact in case["facts"] if fact["found"]}
        group = slices[f"{first['split']}/{first['corpus']}/{first['lang']}"]
        group.update(facts_found=len(found), facts_total=first["facts_total"],
                     all_found=int(len(found) == first["facts_total"]), cases=1)
    return {"total": dict(sum(slices.values(), Counter())),
            "slices": {key: dict(value) for key, value in sorted(slices.items())},
            "interpretation": "offline union of credited facts from separate responses; no agent-policy claim"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--run", action="append", required=True, help="label=run directory")
    parser.add_argument("--union", action="append", default=[], help="left-label+right-label")
    args = parser.parse_args()
    outputs, scores = {}, {}
    for value in args.run:
        label, directory = value.split("=", 1)
        path = Path(directory)
        raw = (path / "score.json").read_bytes()
        score = json.loads(raw)
        run = json.loads((path / "run.json").read_text(encoding="utf-8"))
        if score["anomalies"]:
            raise ValueError(f"{label}: anomalous first-portion run")
        outputs[label] = {
            "score_sha256": hashlib.sha256(raw).hexdigest(), "source_tree": score["source_tree"],
            "questions_sha256": score["questions_sha256"], "oracle_sha256": score["oracle_sha256"],
            "run": score.get("run"), "server_environment": score["server_environment"],
            "first_portion": aggregate(score["cases"]), "slices": score["slices"],
            "dev_loss_stages": loss_stages(score, run), "cumulative_portions": {},
        }
        scores[label] = score
        for number, cumulative in score.get("cumulative_portions", {}).items():
            if cumulative["anomalies"]:
                raise ValueError(f"{label}: anomalous cumulative portion {number}")
            outputs[label]["cumulative_portions"][number] = {
                "aggregate": aggregate(cumulative["cases"]), "slices": cumulative["slices"],
                "limit_counters_scope": "first portion; facts, calls and output sizes are cumulative",
            }
            scores[f"{label}:{number}"] = {**score, "cases": cumulative["cases"]}
    if len({(score["questions_sha256"], score["oracle_sha256"]) for score in scores.values()}) != 1:
        raise ValueError("studies used different sealed inputs")
    unions = {}
    for value in args.union:
        left, right = value.split("+", 1)
        unions[value] = union_credited(scores[left], scores[right])
    result = {"schema_version": 1, "studies": outputs, "unions": unions,
              "limitations": ["65 distinct reference facts tested in four language/corpus conditions, total 260",
                              "measures evidence delivery, not final answer correctness",
                              "latency is not compared under concurrent CPU load"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for label, output in outputs.items():
        print(label, json.dumps(output["first_portion"], ensure_ascii=False))
    for label, output in unions.items():
        print(label, json.dumps(output["total"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
