"""Replay predetermined Adaptive-k score-gap variants on REAL archived MiniLM scores.

Requires GitHub Actions artifact archives from PR #221, supplied as ZIP files
in --artifacts. This is an exploratory known-V40 regression replay, not a new
installed-MCP inference or unseen holdout. Gold is consulted only after each
policy's cutoff is computed. No model inputs, sources or production code change.

Paper: Taguchi et al, EMNLP 2025, doi:10.18653/v1/2025.emnlp-main.1017.
IMPORTANT: paper uses cosine embedding similarity and buffer B=5. Here we
test raw cross-encoder logits with B=0/1 and a cap of five, not the paper's
validated algorithm. The five-archive comparison can bound tokens for k=4.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import statistics
import zipfile
from pathlib import Path

REQUIRED = {
    1: "pr221-policy-k1-a19bb752.zip",
    2: "pr221-policy-k2-a19bb752.zip",
    3: "pr221-policy-k3-a19bb752.zip",
    5: "pr221-final-a19bb752.zip",
}
ARMS = ("full-gap-b0", "full-gap-b1", "head-gap-b0", "head-gap-b1")
FAMILIES = ("black", "poetry", "textual", "vite", "eslint")
TESTED_HEAD = "a19bb7525943bfc10da075d0ed15cb424c626bc2"

def choose(scores: list[float], arm: str) -> int:
    if len(scores) < 2:
        return 1
    if not all(math.isfinite(s) for s in scores):
        raise ValueError("nonfinite real model score")
    if scores != sorted(scores, reverse=True):
        raise ValueError("unsorted scores")
    if arm.startswith("full-gap"):
        # Exploratory adaptation of paper's first 90% gap search.
        count = max(1, min(len(scores)-1, math.ceil(0.9 * len(scores))))
    else:
        # Local top-five shortlist variant, explicitly NOT the paper's method.
        count = min(5, len(scores)-1)
    diffs = [scores[i] - scores[i+1] for i in range(count)]
    # No benchmark thresholds or question-specific rules.
    gap_position = max(range(count), key=lambda i: diffs[i]) + 1
    buffer = 1 if arm.endswith("b1") else 0
    return min(5, gap_position + buffer)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    files = {k: zipfile.ZipFile(args.artifacts/name) for k,name in REQUIRED.items()}
    try:
        assessment = {}
        for k,z in files.items():
            prefix = "v40" if k == 5 else "run"
            summary = json.loads(z.read(f"{prefix}/SUMMARY.json"))
            if summary["head"] != TESTED_HEAD or summary["top_k"] != k or summary["units"] != "legacy":
                raise ValueError(f"unexpected original installed test source {k}")
            assessment[k] = {row["case_id"]: row for row in
                json.loads(z.read(f"{prefix}/ASSESSMENTS.json"))}
            if len(assessment[k]) != 40:
                raise ValueError("unfrozen example count")
        rows = []
        for family in FAMILIES:
            ids = sorted(cid for cid,a in assessment[5].items() if a["family"] == family)
            observations = json.loads(files[5].read(f"v40/{family}/server.json"))["observations"]
            if len(ids) != len(observations) or len(ids) != 8:
                raise ValueError(f"observation count mismatch: {family}")
            for index, (cid, observation) in enumerate(zip(ids, observations)):
                ranked = observation["ranked_sections"]
                score = [row["score"] for row in ranked]
                if len(score) < 5:
                    raise ValueError("not enough original candidates")
                baseline_rows = json.loads(files[5].read(
                    f"v40/{family}/{cid}-expanded.json"))["sources"]
                if {s["evidence_id"] for s in baseline_rows} != set(observation["selected_evidence_ids"]):
                    raise ValueError("original scoring mismatch")
                for k in (1,2,3):
                    low_observation = json.loads(files[k].read(
                        f"run/{family}/server.json"))["observations"][index]
                    # IDs are response-scoped; compare exact scoring-text hashes.
                    high_hashes = [r["scoring_text_sha256"] for r in ranked[:k]]
                    low_hashes = [r["scoring_text_sha256"] for r in low_observation["ranked_sections"][:k]]
                    if high_hashes != low_hashes:
                        raise ValueError(f"ranking difference: {cid} k{k}")
                    low_rows = json.loads(files[k].read(
                        f"run/{family}/{cid}-expanded.json"))["sources"]
                    if {r["evidence_id"] for r in low_rows} != set(low_observation["selected_evidence_ids"]):
                        raise ValueError(f"selection mismatch: {cid} k{k}")
                for arm in ARMS:
                    k = choose(score, arm)
                    # k=4 is evaluated conservatively from the real k=3 result:
                    # all documented witnesses already passed there. Other
                    # exact-k decisions use that very archive.
                    reference = assessment[k if k in assessment else 3][cid]
                    category = reference["answerability"]
                    result = reference["coverage"]["all_documented_claims_covered"] \
                        if category != "unanswerable" else False
                    low = assessment[k if k in assessment else 3][cid]["tokens"]
                    high = assessment[k if k in assessment else 5][cid]["tokens"]
                    rows.append({
                        "case_id": cid, "arm": arm, "category": category, "k": k,
                        "source_rows": sum(len(section["evidence_ids"]) for section in ranked[:k]),
                        "retains_documented_witness": bool(result),
                        "token_lower_bound": low, "token_upper_bound": high,
                    })
        result = {
            "test_head": TESTED_HEAD,
            "scope": "offline replay of archived, actual installed-MCP ONNX scores on known V40",
            "not_proven": ["new inference", "unseen corpus", "generation correctness",
                "semantic refusal", "provider billing", "paper-method equivalence"],
            "policies": {},
        }
        for arm in ARMS:
            cases = [r for r in rows if r["arm"] == arm]
            pos = [r for r in cases if r["category"] == "within_budget"]
            part = [r for r in cases if r["category"] == "partial"]
            result["policies"][arm] = {
                "k_histogram": {str(k): sum(r["k"] == k for r in cases)
                    for k in range(1,6)},
                "mean_k": statistics.mean(r["k"] for r in cases),
                "positive_retained": sum(r["retains_documented_witness"] for r in pos),
                "positive_total": len(pos),
                "partial_retained": sum(r["retains_documented_witness"] for r in part),
                "partial_total": len(part),
                "mean_token_lower_bound": statistics.mean(r["token_lower_bound"] for r in cases),
                "mean_token_upper_bound": statistics.mean(r["token_upper_bound"] for r in cases),
                "failed_documented_ids": [r["case_id"] for r in cases
                    if r["category"] != "unanswerable" and not r["retains_documented_witness"]],
            }
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out/"REPLAY.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        with (args.out/"CASES.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        for z in files.values():
            z.close()

if __name__ == "__main__":
    main()
