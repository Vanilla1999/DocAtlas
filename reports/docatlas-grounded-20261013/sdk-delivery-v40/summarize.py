"""Offline summary of immutable V40 judgments; no product imports/calls."""
from collections import Counter
import json
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
DATASET = REPO / "eval/prepared_model_comparison40"


def main():
    assessment = json.loads((ROOT / "assessment/CASE_RESULTS.json").read_text())
    workload = json.loads((ROOT / "run/V0/SUMMARY.json").read_text())
    questions = {row["id"]: row for row in json.loads((DATASET / "questions.json").read_text())["cases"]}
    cases = assessment["cases"]
    result = {
        "commit": json.loads((ROOT / "FROZEN_RUN.json").read_text())["base_commit"],
        "arm": "current-default (historical runner label V0)",
        "boundary": "installed wheel, public in-process MCP, prepared real SQLite; not stdio/generation",
        "planned": 40, "returned": sum(row["status"] == "returned" for row in cases),
        "workload_status": workload["status"],
        "prepare_attempts": workload["preparations"], "context_attempts": workload["contexts"],
        "model_calls": workload["model_calls"], "workload_seconds": workload["seconds"],
        "judgments": {}, "by_family": {}, "failures": [], "facts": [],
        "answer_quality": "NOT MEASURED", "generated_hallucinations": "NOT MEASURED",
    }
    for name in ("native", "packed"):
        result["judgments"][name] = {}
        for kind, metric in (("within_budget", "strict_positive_pass"),
                             ("partial", "strict_partial_documented_pass"),
                             ("unanswerable", "strict_negative_empty_source_pass")):
            selected = [row for row in cases if questions[row["case_id"]]["answerability"] == kind]
            result["judgments"][name][kind] = dict(
                total=len(selected), passed=sum(row.get(name, {}).get(metric) is True for row in selected),
                failed=sum(row.get(name, {}).get(metric) is False for row in selected),
                not_measured=sum(row.get(name, {}).get(metric) is None for row in selected))
    returned = [row for row in cases if row["status"] == "returned"]
    times = [row["seconds"] for row in returned]
    result.update(context_seconds_sum=sum(times), context_seconds_median=statistics.median(times) if times else None,
                  context_seconds_max=max(times) if times else None,
                  read_only_failures=[row["case_id"] for row in returned if not row["read_only_pass"]],
                  runtime_integrity_failures=[row["case_id"] for row in returned if row["runtime_integrity_errors"]],
                  assessor_integrity_failures=[row["case_id"] for row in returned if any(row[n]["integrity_errors"] for n in ("native", "packed"))])
    costs = []
    for row in cases:
        question = questions[row["case_id"]]
        family = result["by_family"].setdefault(question["project_group"], Counter(total=0, positive_pass=0, partial_pass=0, negative_pass=0))
        family["total"] += 1
        if row["status"] != "returned":
            result["failures"].append(dict(case_id=row["case_id"], question=question["question"], reason="NOT_RETURNED"))
            continue
        directory = ROOT / "run/V0/calls/0" / row["case_id"] / "V0"
        metadata = json.loads((directory / "metadata.json").read_text())
        packed = json.loads((directory / "packed.json").read_text())
        costs.append(dict(case_id=row["case_id"], native_saved_json_tokens=metadata["tokens"],
                          native_saved_json_bytes=metadata["utf8_bytes"], packed_source_tokens=packed["tokens"],
                          packed_source_bytes=packed["utf8_bytes"]))
        for metric, count in (("strict_positive_pass", "positive_pass"),
                              ("strict_partial_documented_pass", "partial_pass"),
                              ("strict_negative_empty_source_pass", "negative_pass")):
            if row["packed"].get(metric) is True:
                family[count] += 1
            elif row["packed"].get(metric) is False:
                result["failures"].append(dict(case_id=row["case_id"], question=question["question"],
                    answerability=question["answerability"], metric=metric,
                    missing_claim_ids=row["packed"]["exact_frozen_coverage"]["missing_documented_claim_ids"],
                    sources=row["packed"]["source_count"],
                    interpretation="nonempty evidence is not generated unsupported answer" if question["answerability"] == "unanswerable" else "fixed witness delivery failed"))
        native_claims = {claim["claim_id"]: claim for claim in row["native"]["exact_frozen_coverage"]["claims"]}
        for claim in row["packed"]["exact_frozen_coverage"]["claims"]:
            native = native_claims[claim["claim_id"]]
            fact = dict(case_id=row["case_id"], question=question["question"], claim_id=claim["claim_id"],
                        documented=claim["documented"], in_acquisition="UNKNOWN", after_admission="UNKNOWN",
                        after_selection="UNKNOWN", in_public_native=native["covered"], in_packed=claim["covered"],
                        first_proven_loss=("external_whole_source_pack" if native["covered"] and not claim["covered"]
                                           else "UNKNOWN_BEFORE_PUBLIC_NATIVE" if claim["documented"] and not native["covered"] else None),
                        witness_sets=[])
            for alternative in claim["witness_sets"]:
                parts = []
                for part in alternative["parts"]:
                    source = DATASET / "sources" / question["project_group"] / part["path"]
                    raw = source.read_text()
                    lines = raw.splitlines(keepends=True)
                    parts.append({**part, "independent_original_quote": "".join(lines[part["line_start"]-1:part["line_end"]])})
                fact["witness_sets"].append({**alternative, "parts": parts})
            result["facts"].append(fact)
    result["costs"] = costs
    result["cost_totals"] = {key: sum(row[key] for row in costs) for key in
                             ("native_saved_json_tokens", "native_saved_json_bytes", "packed_source_tokens", "packed_source_bytes")}
    result["cost_maxima"] = {key: max((row[key] for row in costs), default=0) for key in
                             ("native_saved_json_tokens", "packed_source_tokens")}
    result["claim_totals"] = {name: dict(documented=sum(row[name]["exact_frozen_coverage"]["documented_claim_count"] for row in returned),
                                         covered=sum(row[name]["exact_frozen_coverage"]["covered_documented_claim_count"] for row in returned))
                              for name in ("native", "packed")}
    (ROOT / "SUMMARY.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key not in ("facts", "costs")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
