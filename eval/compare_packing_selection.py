"""Compare same-commit selectors and exact-packet host formats; no nonce gains."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

SUITES = {"v40": 40, "new16": 16, "fresh8": 8, "semantic12": 12, "preservation8": 8}
MODES = ("paths-v1", "sections-v1", "adaptive-v1")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--artifacts", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    arms = {}; missing = []
    for suite in SUITES:
        for policy in ("fixed", "facet-guarded-v1"):
            found = list(args.artifacts.glob(f"**/{suite}/{policy}/SUMMARY.json"))
            if len(found) != 1:
                missing.append([suite, policy]); continue
            root = found[0].parent
            arms[(suite, policy)] = {
                "summary": json.loads(found[0].read_text()),
                "rows": json.loads((root / "ASSESSMENTS.json").read_text()),
                "freeze": json.loads((root / "FREEZE.json").read_text()),
                "packing": json.loads((root / "PACKING.json").read_text()),
            }
    report = {"missing_arms": missing, "provider_usage": None, "answer_model_calls": 0,
        "semantic_sufficiency_certified": False, "known_regression_questions": sum(SUITES.values()),
        "measurement_boundary": "actual public MCP; same-packet installed host packing; no generated answer comparison"}
    (args.out / "PAIRED.json").write_text(json.dumps(report, indent=2) + "\n")
    assert not missing, "incomplete paired execution"
    heads = {arm["freeze"]["head"] for arm in arms.values()}
    assert len(heads) == 1, "mixed product revisions"
    totals = {p: {"documented": 0, "complete": 0, "required": 0, "covered": 0,
                  "negative": 0, "negative_passed": 0, "tokens": 0, "seconds": 0.0}
              for p in ("fixed", "facet-guarded-v1")}
    losses = []; details = {}; controls = 0
    formats = {m: {"baseline_tokens": 0, "tokens": 0, "baseline_bytes": 0, "bytes": 0,
                   "questions": 0, "grew": 0, "shrunk": 0, "host_seconds": 0.0,
                   "unchanged_evidence_cases": 0, "fallback_cases": 0} for m in MODES}
    for suite, n in SUITES.items():
        reference = arms[(suite, "fixed")]
        candidate = arms[(suite, "facet-guarded-v1")]
        assert reference["freeze"]["files"] == candidate["freeze"]["files"]
        before = {r["case_id"]: r for r in reference["rows"]}
        after = {r["case_id"]: r for r in candidate["rows"]}
        assert len(before) == len(after) == n and before.keys() == after.keys()
        for cid, a in before.items():
            b = after[cid]
            assert a["question"] == b["question"] and a["search_question"] == b["search_question"]
            assert a["candidate_fingerprint"] == b["candidate_fingerprint"]
            ac, bc = {x["id"]: x["covered"] for x in a["claims"]}, {x["id"]: x["covered"] for x in b["claims"]}
            assert ac.keys() == bc.keys()
            losses.extend({"suite": suite, "case": cid, "claim": key} for key in ac if ac[key] and not bc[key])
        for policy in ("fixed", "facet-guarded-v1"):
            arm = arms[(suite, policy)]
            summary = arm["summary"]
            assert summary["runtime_errors"] == summary["integrity_errors"] == 0
            assert summary["cases"] == n
            for row in arm["rows"]:
                assert not row["runtime_error"] and row["integrity"]
                t = totals[policy]
                t["required"] += len(row["claims"])
                t["covered"] += sum(x["covered"] for x in row["claims"])
                t["tokens"] += row["tokens"]; t["seconds"] += row["seconds"]
                if row["answerability"] == "unanswerable":
                    t["negative"] += 1; t["negative_passed"] += bool(row["passed"])
                else:
                    t["documented"] += 1; t["complete"] += bool(row["passed"])
            pack = arm["packing"]
            assert pack["additional_model_calls"] == pack["additional_retrieval_calls"] == 0
            assert len(pack["records"]) == 3 * n
            assert all(x["rejected"] for x in pack["controls"])
            controls += len(pack["controls"])
            assert len({(x["case_id"], x["packing"]) for x in pack["records"]}) == 3 * n
            for x in pack["records"]:
                assert x["same_response_packet"] and x["same_full_citation_refs"] and x["visible_fields_identical_after_expansion"]
                if x["packing"] == "adaptive-v1":
                    assert x["tokens"] <= x["baseline_tokens"] and x["bytes"] <= x["baseline_bytes"]
                if policy != "facet-guarded-v1":
                    continue
                t = formats[x["packing"]]
                for key in ("tokens", "baseline_tokens", "bytes", "baseline_bytes", "host_seconds"):
                    t[key] += x[key]
                t["questions"] += 1
                t["grew"] += x["tokens"] > x["baseline_tokens"]
                t["shrunk"] += x["tokens"] < x["baseline_tokens"]
                t["fallback_cases"] += x["actual_policy"] == "original-v1"
                t["unchanged_evidence_cases"] += 1
        details[suite] = {"fixed": reference["summary"], "facet": candidate["summary"],
            "packing_tokens": {m: sum(x["tokens"] for x in candidate["packing"]["records"] if x["packing"] == m) for m in MODES}}
    for item in formats.values():
        item["saved_tokens"] = item["baseline_tokens"] - item["tokens"]
    report.update(head=next(iter(heads)), arms=len(arms), selection=totals,
        lost_control_witnesses=losses, packing=formats, by_suite=details,
        rejected_tamper_cases=controls,
        stdio_search_calls=2 * sum(SUITES.values()),
        public_baseline_calls=2 * sum(SUITES.values()),
        language_preflights=sum(len({r["family"] for r in a["rows"]}) for a in arms.values()),
        quality_gate_passed=not losses and totals["facet-guarded-v1"]["complete"] == totals["facet-guarded-v1"]["documented"],
        packing_gate_passed=formats["adaptive-v1"]["grew"] == 0 and formats["adaptive-v1"]["saved_tokens"] > 0)
    (args.out / "PAIRED.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    assert report["quality_gate_passed"], "current facet selection lost required evidence"
    assert report["packing_gate_passed"], "no verified same-packet packing benefit"


if __name__ == "__main__":
    main()
