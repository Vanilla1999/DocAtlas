"""Pure saved-receipt metrics; no product imports or relevance judgments."""
from __future__ import annotations

from collections import Counter
import json
import math
import statistics

from common import PREFIXES


def distribution(values) -> dict:
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"n": 0, "sum": None, "mean": None, "p50": None, "p95": None, "max": None}
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError("invalid numeric measurement")
    return {"n": len(values), "sum": sum(values), "mean": statistics.fmean(values),
            "p50": statistics.median(values), "p95": values[math.ceil(len(values) * .95) - 1],
            "max": values[-1]}


def acquisition(pool: list[dict], arm: str) -> dict:
    descriptors = {}
    owner_keys = set()
    ownerless = 0
    for row in pool:
        metadata = row.get("metadata") or {}
        item = metadata.get("acquisition")
        if item:
            descriptors[json.dumps(item, sort_keys=True, ensure_ascii=False)] = item
        owner = (metadata.get("_reference_evidence") or {}).get("owner") or {}
        if owner.get("logical_id"):
            owner_keys.add((row["path"], owner["logical_id"]))
        else:
            ownerless += 1
    items = list(descriptors.values())
    saturated = []
    for item in items:
        ceiling, raw_rows = item["candidate_ceiling"], item["sql_rows"]
        if ceiling != 256 or type(raw_rows) is not int or not 0 <= raw_rows <= ceiling:
            raise ValueError("acquisition raw-row budget changed")
        if arm == "main":
            if item["method"] != "fts5_bm25_equal_fields_or_v1" or "policy" in item:
                raise ValueError("main is not the actual unchanged acquisition")
            saturated.append(raw_rows == ceiling)
        else:
            limits = {"retrieval_text": 256} if arm == "retrieval_text" else {
                "all_fields": 128, "retrieval_text": 128}
            if (item.get("policy") != arm or item.get("per_view_limits") != limits
                    or item.get("aggregate_row_budget") != 256
                    or item.get("sql_calls_measure") != "fts_match_statements"):
                raise ValueError("experimental acquisition allocation changed")
            rows = item["per_view_rows"]
            if (set(rows) != set(limits) or any(type(rows[k]) is not int or not 0 <= rows[k] <= limits[k]
                                              for k in limits)
                    or sum(rows.values()) != item["raw_rows_sum"]
                    or item["raw_rows_sum"] != raw_rows
                    or not 0 <= item["unique_count"] <= raw_rows):
                raise ValueError("invalid measured acquisition row accounting")
            expected_saturation = {k: rows[k] == limits[k] for k in limits}
            if item["saturation"] != expected_saturation:
                raise ValueError("invalid per-view saturation receipt")
            if arm == "rrf" and item.get("rrf_k") != 60:
                raise ValueError("RRF constant changed")
            saturated.append(any(expected_saturation.values()))
    return {
        "checked_pool_rows": len(pool), "known_unique_markdown_owners": len(owner_keys),
        "rows_without_markdown_owner": ownerless,
        "checked_pool_utf8_bytes": sum(len(row["text"].encode("utf-8")) for row in pool),
        "distinct_observed_descriptors": items,
        "max_observed_lane_raw_rows": max((i["sql_rows"] for i in items), default=None),
        "any_observed_lane_saturated": any(saturated) if items else None,
        "descriptor_measure": "source-checked nonempty lane representatives; not all executions or summed SQL work",
    }


def aggregate(cases: list[dict]) -> dict:
    groups = {}
    for label in sorted({case["answerability"] for case in cases}):
        group = [case for case in cases if case["answerability"] == label]
        groups[label] = {"cases": len(group), "source_fact_contract_pass": sum(c["source_fact_contract_pass"] for c in group),
                         "delivery_errors": sum(c["delivery_error"] for c in group)}
    observed = [c for c in cases if c["retrieval"] is not None]
    required = sum(c["final"]["coverage"]["documented_facts"] for c in cases)
    final_covered = sum(c["final"]["coverage"]["covered_facts"] for c in cases)
    pool_covered = sum(c["retrieval"]["full_pool"]["covered_facts"] for c in observed)
    pool_required = sum(c["retrieval"]["full_pool"]["documented_facts"] for c in observed)
    prefixes = {}
    for size in PREFIXES:
        covered = sum(c["retrieval"]["prefixes"][str(size)]["covered_facts"] for c in observed)
        prefixes[str(size)] = {"observed_cases": len(observed), "documented_facts": pool_required,
                               "covered_facts": covered,
                               "fact_coverage_observed_cases": covered / pool_required if pool_required else None}
    return {
        "cases": len(cases), "historic_labels": groups,
        "delivery_errors": sum(c["delivery_error"] for c in cases),
        "statuses": dict(Counter(str(c["final"]["status"]) for c in cases)),
        "formats": dict(Counter(str(c["final"]["format"]) for c in cases)),
        "documented_facts": required, "final_covered_facts": final_covered,
        "final_fact_coverage": final_covered / required if required else None,
        "pool_observed_cases": len(observed), "pool_unobserved_cases": len(cases) - len(observed),
        "pool_observed_documented_facts": pool_required, "pool_covered_facts": pool_covered,
        "pool_fact_coverage_observed_cases": pool_covered / pool_required if pool_required else None,
        "pool_prefix_coverage": prefixes,
        "pool_all_documented_facts_cases": sum(c["retrieval"]["full_pool"]["all_documented_facts_covered"] for c in observed),
        "final_all_documented_facts_cases": sum(c["final"]["coverage"]["all_documented_facts_covered"] for c in cases),
        "pool_rows": distribution(c["acquisition"]["checked_pool_rows"] for c in observed),
        "known_markdown_owners": distribution(c["acquisition"]["known_unique_markdown_owners"] for c in observed),
        "observed_lane_saturation_cases": sum(c["acquisition"]["any_observed_lane_saturated"] is True for c in observed),
        "actual_fts_statements": sum(c["actual_fts_statements"] for c in cases),
        "actual_fts_statements_per_case": distribution(c["actual_fts_statements"] for c in cases),
        "minilm_missing_completion_receipts": sum(c["minilm"]["receipt_count"] == 0 for c in cases),
        "minilm_completed_forward_passes": distribution(c["minilm"]["forward_passes"] for c in cases),
        "minilm_completed_input_pair_tokens": distribution(c["minilm"]["input_pair_tokens"] for c in cases),
        "final_source_bodies": distribution(c["final"]["source_bodies"] for c in cases),
        "final_source_text_utf8_bytes": distribution(c["final"]["source_text_utf8_bytes"] for c in cases),
        "wire_o200k_tokens_all": distribution(c["final"]["o200k_tokens"] for c in cases),
        "wire_o200k_tokens_nonerror": distribution(c["final"]["o200k_tokens"] for c in cases if not c["delivery_error"]),
        "wire_utf8_bytes": distribution(c["final"]["utf8_bytes"] for c in cases),
        "context_seconds": distribution(c["seconds"] for c in cases),
        "first_context_in_server_seconds": distribution(c["seconds"] for c in cases if c["first_call_in_server"]),
        "later_context_seconds": distribution(c["seconds"] for c in cases if not c["first_call_in_server"]),
    }


def paired(main: list[dict], variant: list[dict]) -> dict:
    baseline = {c["id"]: c for c in main}
    rows = []
    for candidate in variant:
        reference = baseline[candidate["id"]]
        if (candidate["question"] != reference["question"]
                or candidate["answerability"] != reference["answerability"]
                or candidate["root"] != reference["root"]):
            raise ValueError("paired input/path/label changed")
        row = {"id": candidate["id"], "answerability": candidate["answerability"]}
        for kind in ("full_pool", "final"):
            old = reference["retrieval"] if kind == "full_pool" else reference["final"]
            new = candidate["retrieval"] if kind == "full_pool" else candidate["final"]
            if old is None or new is None:
                row[kind] = {"paired_observed": False}
                continue
            old = old["full_pool"] if kind == "full_pool" else old["coverage"]
            new = new["full_pool"] if kind == "full_pool" else new["coverage"]
            before, after = set(old["covered_fact_ids"]), set(new["covered_fact_ids"])
            row[kind] = {"paired_observed": True, "gained_fact_ids": sorted(after - before),
                         "lost_fact_ids": sorted(before - after), "net_facts": len(after) - len(before),
                         "all_documented_facts_before": old["all_documented_facts_covered"],
                         "all_documented_facts_after": new["all_documented_facts_covered"]}
        row["source_fact_contract_pass_before"] = reference["source_fact_contract_pass"]
        row["source_fact_contract_pass_after"] = candidate["source_fact_contract_pass"]
        row["delivery_error_before"] = reference["delivery_error"]
        row["delivery_error_after"] = candidate["delivery_error"]
        row["wire_token_delta"] = candidate["final"]["o200k_tokens"] - reference["final"]["o200k_tokens"]
        row["wire_byte_delta"] = candidate["final"]["utf8_bytes"] - reference["final"]["utf8_bytes"]
        row["actual_fts_statement_delta"] = candidate["actual_fts_statements"] - reference["actual_fts_statements"]
        row["prefix_fact_deltas"] = None
        if candidate["retrieval"] is not None and reference["retrieval"] is not None:
            row["prefix_fact_deltas"] = {
                str(k): candidate["retrieval"]["prefixes"][str(k)]["covered_facts"]
                - reference["retrieval"]["prefixes"][str(k)]["covered_facts"] for k in PREFIXES}
        for key in ("forward_passes", "input_pair_tokens"):
            old, new = reference["minilm"][key], candidate["minilm"][key]
            row["minilm_" + key + "_delta"] = new - old if old is not None and new is not None else None
        rows.append(row)
    summary = {}
    for stage in ("full_pool", "final"):
        group = [r[stage] for r in rows if r[stage]["paired_observed"]]
        summary[stage] = {
            "paired_cases": len(group), "cases_with_gained_facts": sum(bool(r["gained_fact_ids"]) for r in group),
            "cases_with_lost_facts": sum(bool(r["lost_fact_ids"]) for r in group),
            "gained_facts": sum(len(r["gained_fact_ids"]) for r in group),
            "lost_facts": sum(len(r["lost_fact_ids"]) for r in group),
            "net_positive_cases": sum(r["net_facts"] > 0 for r in group),
            "net_negative_cases": sum(r["net_facts"] < 0 for r in group),
            "net_tied_cases": sum(r["net_facts"] == 0 for r in group),
        }
    summary["source_fact_contract_pass_gains"] = sum(not r["source_fact_contract_pass_before"] and r["source_fact_contract_pass_after"] for r in rows)
    summary["source_fact_contract_pass_losses"] = sum(r["source_fact_contract_pass_before"] and not r["source_fact_contract_pass_after"] for r in rows)
    summary["wire_token_delta_all"] = sum(r["wire_token_delta"] for r in rows)
    summary["wire_nonerror_pair_count"] = sum(not r["delivery_error_before"] and not r["delivery_error_after"] for r in rows)
    summary["wire_token_delta_nonerror_pairs"] = sum(r["wire_token_delta"] for r in rows
                                                    if not r["delivery_error_before"] and not r["delivery_error_after"])
    summary["prefix_net_fact_deltas"] = {str(k): sum(r["prefix_fact_deltas"][str(k)] for r in rows
                                                     if r["prefix_fact_deltas"] is not None) for k in PREFIXES}
    return {"summary": summary, "per_case": rows}
