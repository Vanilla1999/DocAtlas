"""Read-only arithmetic audit of the completed saved experiment; stdlib only.

No product imports, model execution, retrieval, oracle or question loading.
Outputs belong to this report; original run artifacts are never rewritten.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
RUN = ROOT / "attempt-01"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def stats(values):
    values = list(values)
    if not values:
        return {"count": 0, "sum": 0, "median": None, "mean": None, "min": None, "max": None}
    return {"count": len(values), "sum": sum(values), "median": statistics.median(values),
            "mean": statistics.mean(values), "min": min(values), "max": max(values)}


def diagnostic_values(value, name):
    result = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == name:
                result.append(item)
            result.extend(diagnostic_values(item, name))
    elif isinstance(value, list):
        for item in value:
            result.extend(diagnostic_values(item, name))
    return result


def main():
    summary = load(RUN / "raw-run-summary.json")
    if summary["status"] != "completed":
        raise RuntimeError("Cost audit requires a completed frozen run")
    consumed = {RUN / "raw-run-summary.json", RUN / "RUN_MANIFEST.json", Path(__file__).resolve()}
    errors, rows, inputs = [], {}, []
    for directory in sorted((RUN / "calls").glob("*/*")):
        meta_path, selection_path = directory / "metadata.json", directory / "selection.json"
        wire_path, trace_path = directory / "public-payload.json", directory / "trace.jsonl"
        consumed.update((meta_path, selection_path, wire_path, trace_path))
        meta, selections = load(meta_path), load(selection_path)
        key = meta["case_id"], meta["mode"]
        wire = wire_path.read_bytes()
        payload = json.loads(wire)
        # Supplementary post-run diagnostic requested by the coordinator.
        # Preserve every product field except opaque capability URI and its
        # dependent size estimate; raw wire costs and primary gold are intact.
        stable_payload = deepcopy(payload)
        stable_payload.pop("estimated_tokens", None)
        for collection in ("sources", "read_next"):
            for item in stable_payload.get(collection) or []:
                if isinstance(item, dict):
                    item.pop("source_uri", None)
        quarter = (len(wire) + 3) // 4
        if (meta["wire_sha256"] != hashlib.sha256(wire).hexdigest()
                or meta["wire_utf8_bytes"] != len(wire) or meta["utf8_quarter_proxy"] != quarter):
            errors.append([*key, "wire_accounting_mismatch"])
        if len(selections) != 1 or meta["observation_calls"] != 1 or meta["observation_errors"]:
            raise RuntimeError("This completed run was expected to have exactly one successful selection receipt per call")
        receipt = selections[0]
        selection = receipt["selection"]
        events = []
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        terminal = diagnostic_values(events, "experimental_budget")
        prepared = diagnostic_values(events, "prepared_parents")
        if len(terminal) != 1 or len(prepared) != 1:
            errors.append([*key, "trace_diagnostic_cardinality"])
        if selection["candidate_count"] != len(receipt["pool"]):
            errors.append([*key, "candidate_count_mismatch"])
        if selection["model_forwards"] != sum(row.get("score") is not None for row in selection["rows"]):
            errors.append([*key, "forward_count_mismatch"])
        if selection["model_input_tokens"] != sum(row["tokens"] for row in selection["rows"] if row.get("score") is not None):
            errors.append([*key, "forward_token_count_mismatch"])
        source_text_bytes = sum(len(s.get("snippet", "").encode("utf-8")) for s in payload.get("sources", []))
        native_text_bytes = sum(len(s["text"].encode("utf-8")) for s in receipt["pool"])
        selected = selection["selected_indices"]
        row = {
            "case_id": key[0], "mode": key[1], "status": meta["status"],
            "elapsed_seconds": meta["elapsed_seconds"], "process_cpu_seconds": meta["process_cpu_seconds"],
            "wire_utf8_bytes": len(wire), "utf8_quarter_proxy": quarter,
            "codec_o200k_base_recorded": meta["codec_o200k_base"],
            "budget_measure": max(quarter, meta["codec_o200k_base"]),
            "public_source_count": len(payload.get("sources", [])), "source_snippet_utf8_bytes": source_text_bytes,
            "pool_count": len(receipt["pool"]), "native_pool_text_utf8_bytes": native_text_bytes,
            "selected_count": len(selected), "selected_indices": selected,
            "selected_ids": [receipt["pool"][i]["id"] for i in selected],
            "selection_status": selection["status"],
            "model_forward_attempts": selection["model_forward_attempts"], "model_forwards": selection["model_forwards"],
            "model_input_tokens": selection["model_input_tokens"], "tokenized_input_tokens": selection["tokenized_input_tokens"],
            "selection_total_seconds": selection["total_seconds"],
            "tokenization_seconds": selection["tokenization_seconds"], "inference_seconds": selection["inference_seconds"],
            "model_loads": selection["model_loads"], "model_load_seconds": selection["model_load_seconds"],
            "trace_bytes": trace_path.stat().st_size, "selection_artifact_bytes": selection_path.stat().st_size,
            "terminal_budget": terminal[0] if terminal else None,
            "prepared_parent_reader": prepared[0] if prepared else None,
            "input_digest": digest({name: receipt[name] for name in ("question", "pool", "complete_candidates", "excluded")}),
            "wire_digest": hashlib.sha256(wire).hexdigest(),
            "stable_public_dto_digest": digest(stable_payload),
            "started_at_utc": meta["started_at_utc"],
            "database_unchanged": meta["database_unchanged"], "project_files_unchanged": meta["project_files_unchanged"],
        }
        rows[key] = row
    cases = sorted({key[0] for key in rows})
    if len(cases) != 40 or len(rows) != 80:
        errors.append(["workload", len(cases), len(rows)])
    pairs = []
    for case in cases:
        budget, mini = rows[case, "budget"], rows[case, "mini"]
        pair_path = RUN / "pairs" / (case + ".json")
        consumed.add(pair_path)
        saved = load(pair_path)
        same_input = budget["input_digest"] == mini["input_digest"]
        changed_set = set(budget["selected_ids"]) != set(mini["selected_ids"])
        changed_order = budget["selected_ids"] != mini["selected_ids"]
        changed_wire = budget["wire_digest"] != mini["wire_digest"]
        changed_stable = budget["stable_public_dto_digest"] != mini["stable_public_dto_digest"]
        if not same_input or saved["same_preselection_inputs"] != same_input:
            errors.append([case, "unequal_preselection_inputs"])
        pairs.append({
            "case_id": case, "same_complete_input": same_input,
            "pool_count": budget["pool_count"], "pool_over_k": budget["pool_count"] > 2,
            "mini_status": mini["selection_status"], "selected_membership_changed": changed_set,
            "selected_order_changed": changed_order, "public_wire_changed": changed_wire,
            "stable_public_dto_changed": changed_stable,
            "first_mode": "budget" if budget["started_at_utc"] < mini["started_at_utc"] else "mini",
            "delta_seconds_mini_minus_budget": mini["elapsed_seconds"] - budget["elapsed_seconds"],
            "delta_wire_bytes_mini_minus_budget": mini["wire_utf8_bytes"] - budget["wire_utf8_bytes"],
            "delta_utf8_quarter_mini_minus_budget": mini["utf8_quarter_proxy"] - budget["utf8_quarter_proxy"],
        })
    fields = ("elapsed_seconds", "process_cpu_seconds", "wire_utf8_bytes", "utf8_quarter_proxy",
              "codec_o200k_base_recorded", "budget_measure", "public_source_count", "source_snippet_utf8_bytes",
              "pool_count", "native_pool_text_utf8_bytes", "model_forward_attempts", "model_forwards",
              "model_input_tokens", "tokenized_input_tokens", "selection_total_seconds", "tokenization_seconds",
              "inference_seconds", "model_loads", "model_load_seconds", "trace_bytes", "selection_artifact_bytes")
    arms = {mode: {field: stats(row[field] for (case, arm), row in rows.items() if arm == mode)
                   for field in fields} for mode in ("budget", "mini")}
    subgroups = {}
    for name, chosen in {
        "all_40": pairs, "pool_over_k": [p for p in pairs if p["pool_over_k"]],
        "actually_ranked": [p for p in pairs if p["mini_status"] == "ranked"],
        "not_needed": [p for p in pairs if p["mini_status"] == "not_needed"],
        "membership_changed": [p for p in pairs if p["selected_membership_changed"]],
        "public_wire_changed": [p for p in pairs if p["public_wire_changed"]],
        "stable_public_dto_changed": [p for p in pairs if p["stable_public_dto_changed"]],
    }.items():
        subgroups[name] = {
            "count": len(chosen), "case_ids": [p["case_id"] for p in chosen],
            "paired_duration_delta_seconds": stats(p["delta_seconds_mini_minus_budget"] for p in chosen),
            "paired_wire_delta_bytes": stats(p["delta_wire_bytes_mini_minus_budget"] for p in chosen),
            "paired_utf8_quarter_delta": stats(p["delta_utf8_quarter_mini_minus_budget"] for p in chosen),
            "arms": {mode: {field: stats(rows[p["case_id"], mode][field] for p in chosen)
                             for field in ("elapsed_seconds", "wire_utf8_bytes", "utf8_quarter_proxy", "codec_o200k_base_recorded")}
                     for mode in ("budget", "mini")},
        }
    preparation = []
    for path in sorted((RUN / "preparation").glob("*.json")):
        consumed.add(path)
        p = load(path)
        preparation.append({"family": p["family"], "seconds": p["inventory"]["seconds"],
                            "documents": len(p["snapshot_sources"]), "prepared_manifest": bool(p["prepared_manifest"])})
    for path in (RUN / "model-load.json", RUN / "ledger.jsonl", ROOT / "model-assets.json",
                 ROOT / "runtime-install-receipt.json", ROOT / "model-download-receipt.json", ROOT / "model-download-02-receipt.json"):
        consumed.add(path)
    cold = load(RUN / "model-load.json")
    install = load(ROOT / "runtime-install-receipt.json")
    downloads = [load(ROOT / n) for n in ("model-download-receipt.json", "model-download-02-receipt.json")]
    assets = load(ROOT / "model-assets.json")
    extra_attempts_path = ROOT / "observer-integration-attempts.json"
    extra_attempts = load(extra_attempts_path)
    extra_junit_path = ROOT / "observer-integration-attempt-02.junit.xml"
    extra_suite = ET.parse(extra_junit_path).getroot().find("testsuite")
    extra_properties = {p.attrib["name"]: p.attrib["value"] for p in extra_suite.findall(".//property")}
    extra_payloads = sorted((ROOT / "observer-integration").glob("context-*.json"))
    consumed.update((extra_attempts_path, extra_junit_path, ROOT / "observer-integration-attempt-01.junit.xml", *extra_payloads))
    if (extra_suite.attrib["tests"] != "1" or extra_suite.attrib["errors"] != "0"
            or extra_suite.attrib["failures"] != "0" or len(extra_payloads) != int(extra_properties["public_context_calls"])):
        errors.append(["supplementary_integration", "artifact_count_or_status_mismatch"])
    ledger = [json.loads(line) for line in (RUN / "ledger.jsonl").read_text().splitlines()]
    ledger_counts = dict(Counter(row["operation"] + ":" + row["status"] for row in ledger))
    for field in ("model_forward_attempts", "model_forwards"):
        if summary[field] != sum(row[field] for row in rows.values()):
            errors.append([field, "raw_summary_mismatch"])
    traced_seconds = sum(row["elapsed_seconds"] for row in rows.values())
    prep_seconds = sum(p["seconds"] for p in preparation)
    result = {
        "schema_version": 1, "audit": "completed_saved_run_cost_and_pair_arithmetic",
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "consistent" if not errors else "discrepancies", "errors": errors,
        "auditor_role": "model provider author; arithmetic audit, not independent quality review",
        "product_calls_by_auditor": 0, "model_forwards_by_auditor": 0,
        "raw_summary": {k: v for k, v in summary.items() if k != "pairs"},
        "ledger_counts": ledger_counts, "arms": arms, "subgroups": subgroups,
        "pair_summary": {
            "same_complete_input": sum(p["same_complete_input"] for p in pairs),
            "pool_over_k": sum(p["pool_over_k"] for p in pairs),
            "statuses": dict(Counter(p["mini_status"] for p in pairs)),
            "selected_membership_changed": sum(p["selected_membership_changed"] for p in pairs),
            "selected_order_changed": sum(p["selected_order_changed"] for p in pairs),
            "public_wire_changed": sum(p["public_wire_changed"] for p in pairs),
            "stable_public_dto_changed": sum(p["stable_public_dto_changed"] for p in pairs),
            "not_needed_stable_public_dto_changed": sum(p["stable_public_dto_changed"] for p in pairs if p["mini_status"] == "not_needed"),
            "first_mode_counts": dict(Counter(p["first_mode"] for p in pairs)),
        },
        "preparations": preparation,
        "terminal_budget_diagnostic": {
            "records": sum(row["terminal_budget"] is not None for row in rows.values()),
            "selection_attempts": sum((row["terminal_budget"] or {}).get("attempts", 0) for row in rows.values()),
            "native_fallbacks": sum((row["terminal_budget"] or {}).get("native_fallbacks", 0) for row in rows.values()),
            "input_equals_output_all": all(row["terminal_budget"] is not None and row["terminal_budget"]["input_cost"] == row["terminal_budget"]["output_cost"] for row in rows.values()),
        },
        "prepared_parent_reader_diagnostic": {
            "records": sum(row["prepared_parent_reader"] is not None for row in rows.values()),
            "prepared_hits": sum((row["prepared_parent_reader"] or {}).get("prepared_hits", 0) for row in rows.values()),
            "parser_calls": sum((row["prepared_parent_reader"] or {}).get("parser_calls", 0) for row in rows.values()),
            "scope": "Only SourceReferenceContext reader; other structure parsers are not counted by this diagnostic",
        },
        "supplementary_integration": {
            "separate_from_40_paired_timing": True, "attempts": extra_attempts["attempts"],
            "junit_tests": int(extra_suite.attrib["tests"]), "junit_seconds": float(extra_suite.attrib["time"]),
            "prepare_calls": int(extra_properties["public_prepare_calls"]),
            "context_calls": int(extra_properties["public_context_calls"]),
            "model_forwards": int(extra_properties["model_forwards"]),
            "source_continuation_calls": int(extra_properties["source_continuation_calls"]),
            "optional_model_modules_before_after": json.loads(extra_properties["optional_model_modules_before_after"]),
        },
        "complete_task_operations": {
            "prepare_calls": summary["preparations_attempted"] + int(extra_properties["public_prepare_calls"]),
            "context_calls": summary["context_calls_attempted"] + int(extra_properties["public_context_calls"]),
            "model_forwards": summary["model_forwards"] + int(extra_properties["model_forwards"]),
            "answer_generator_calls": 0,
            "scope": "Main frozen 40x2 plus separate standalone budget/observer integration; setup collection error added no product calls",
        },
        "timing_partition_seconds": {
            "whole_driver_elapsed": summary["elapsed_seconds"], "all_80_traced_public_calls": traced_seconds,
            "all_5_prepare_docs_inventory": prep_seconds,
            "host_model_preparation_including_external_torch_import": cold["full_host_preparation_seconds"],
            "remaining_driver_work": summary["elapsed_seconds"] - traced_seconds - prep_seconds - cold["full_host_preparation_seconds"],
        },
        "model_cold_receipt": cold,
        "setup": {
            "runtime_install_steps": [{"exit_code": s["exit_code"], "wall_seconds": s["wall_seconds"]} for s in install["steps"]],
            "runtime_install_recorded_command_seconds": sum(s["wall_seconds"] for s in install["steps"]),
            "download_attempts": [{"status": d["status"], "exit_code": d["exit_code"], "wall_seconds": d["wall_seconds"]} for d in downloads],
            "download_recorded_command_seconds": sum(d["wall_seconds"] for d in downloads),
            "socksio_repair_wall_seconds": "NOT_MEASURED",
            "downloaded_asset_file_bytes": sum(a["bytes"] for a in assets["files"].values()),
            "weights_bytes": assets["files"]["model.safetensors"]["bytes"],
            "timing_caution": "Initial install/download overlap; command durations are cumulative measured work, not time-to-ready. Repair wall is absent.",
        },
        "memory": {"whole_process_peak_rss_kib": summary["process_peak_rss_kib"],
                   "whole_process_peak_rss_bytes": summary["process_peak_rss_kib"] * 1024,
                   "comparison": "NOT_MEASURED: both arms share one process with resident Mini"},
        "cpu_infrastructure_dollars": "NOT_MEASURED", "answer_generator_calls": 0,
        "generator_tokens_and_latency": "NOT_MEASURED",
        "codec_verification": "Named codec counts copied from immutable call metadata; wire bytes/UTF8 quarter independently recomputed without product imports.",
        "stable_dto_diagnostic": "Supplementary after-run comparison: deepcopy full payload, remove root estimated_tokens and source_uri only from sources/read_next. Raw pairs/wire measures and primary oracle unchanged; not a model quality score.",
        "latency_caution": "One traced call per arm per question; includes observer/trace overhead. No repeated sampling, standalone service memory comparison, p95 or speedup proof.",
        "old_v2_comparability": "Same pinned Mini weights, FP32 raw scoring and k=2; different corpus/upstream path. V2 used capture+rescore/reacquire orchestration plus generator; do not compare its times as matched workloads.",
        "pairs": pairs, "calls": list(rows.values()),
        "inputs": {p.relative_to(ROOT).as_posix(): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
                   for p in sorted(consumed)},
    }
    (ROOT / "cost-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "pair_summary": result["pair_summary"],
                      "timing_partition_seconds": result["timing_partition_seconds"],
                      "arms": {mode: {key: arms[mode][key] for key in ("elapsed_seconds", "wire_utf8_bytes", "utf8_quarter_proxy", "codec_o200k_base_recorded", "model_forwards", "model_input_tokens", "inference_seconds", "tokenization_seconds")}
                               for mode in arms},
                      "subgroups": {name: {"count": row["count"], "paired_duration_delta_seconds": row["paired_duration_delta_seconds"]} for name, row in subgroups.items()},
                      "setup": result["setup"], "memory": result["memory"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
