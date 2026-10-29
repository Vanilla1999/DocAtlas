"""Analyze all frozen arm receipts, offline and without product/model imports.

Exit success means a complete source-faithful experiment, NOT a quality win.
The historical labels/criteria remain unchanged, including strict negatives.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ARMS, DATASETS, dataset, documents, read, rows_from_wire, save,
                    sha, source_intervals, verify_freeze)
from gold import Oracle, retrieval_coverage
from report_metrics import acquisition, aggregate, paired
from receipt_flush import verify_ack


def assert_preparation(preparation: dict, docs: dict[str, str], expected_root: str) -> None:
    hashes = {path: sha(text.encode("utf-8")) for path, text in docs.items()}
    if preparation["root"] != expected_root or preparation["source_sha256"] != hashes:
        raise ValueError("prepared path or frozen source bytes changed")
    inventory = preparation["inventory"]
    declared = {row["path"]: row["content_sha256"].removeprefix("sha256:")
                for row in inventory["documents"]}
    snapshots = {row["path"]: row["content_sha256"] for row in preparation["snapshot_sources"]}
    if (len(inventory["documents"]) != len(hashes) or len(preparation["snapshot_sources"]) != len(hashes)
            or declared != hashes or snapshots != hashes) or not all(
            row["matches_pinned_source"] is True for row in preparation["snapshot_sources"]):
        raise ValueError("committed raw source hash/membership mismatch")
    if (not inventory["generation_id"] or inventory["excluded_or_failed_paths"]
            or inventory["unexpected_paths"]):
        raise ValueError("incomplete source preparation")
    installed = preparation["installed"]
    if (not installed["checked_files"] or not installed["wheel_sha256"]
            or not Path(installed["origin"]).is_relative_to(Path(installed["prefix"]))):
        raise ValueError("missing installed-wheel origin proof")


def minilm(receipts: list[dict], case: dict) -> dict:
    selected = [r for r in receipts if r["scoring_question_sha256"] == sha(case["question"].encode("utf-8"))]
    if len(selected) > 1:
        raise ValueError("ambiguous MiniLM completion receipts")
    for receipt in selected:
        if (receipt["model_revision"] != "233902d25c440f23af6f7d6e94d2946bac0bee0a"
                or receipt["selection_policy"] != "facet-guarded-lexical-v2"
                or receipt["units"] != "markdown-owner-v1"):
            raise ValueError("frozen MiniLM model/selection/units changed")
        if (type(receipt["forward_passes"]) is not int or receipt["forward_passes"] < 0
                or type(receipt["input_pair_tokens"]) is not int or receipt["input_pair_tokens"] < 0):
            raise ValueError("invalid MiniLM work receipt")
    return {"receipt_count": len(selected),
            "forward_passes": sum(r["forward_passes"] for r in selected) if selected else None,
            "input_pair_tokens": sum(r["input_pair_tokens"] for r in selected) if selected else None,
            "candidate_rows": sum(r["candidate_rows"] for r in selected) if selected else None,
            "candidate_sections": sum(r["candidate_sections"] for r in selected) if selected else None,
            "selected_rows": sum(r["selected_rows"] for r in selected) if selected else None,
            "selected_sections": sum(r["selected_sections"] for r in selected) if selected else None,
            "scoring_seconds": sum(r["scoring_seconds"] for r in selected) if selected else None,
            "completed_receipts": selected,
            "missing_receipt_meaning": "stage not completed or not reached; work unknown, never assumed zero"}


def sql_for_call(sql: dict, record: dict) -> list[int]:
    start, end = record["call_started_monotonic"], record["call_finished_monotonic"]
    if not start < end or abs(record["seconds"] - (end - start)) > .001:
        raise ValueError("invalid public-call measurement interval")
    return [index for index, row in enumerate(sql["statements"]) if start <= row["at_monotonic"] <= end]


def analyze_case(case, name, arm, folder, docs, preparation, native, mini, sql, oracle):
    record = read(folder / (case["id"] + "-record.json"))
    payload = read(folder / (case["id"] + "-payload.json"))
    reply = read(folder / (case["id"] + "-reply.json"))
    if (record["id"] != case["id"] or record["question"] != case["question"]
            or record["answerability"] != case["answerability"] or record["dataset"] != name
            or record["family"] != case["project_group"] or record["root"] != preparation["root"]):
        raise ValueError("saved case identity/question/label/path changed")
    content = reply["content"]
    if len(content) != 1 or content[0]["type"] != "text" or reply.get("structuredContent") is not None:
        raise ValueError("saved OpenCode text transport changed")
    text = content[0]["text"]
    if json.loads(text) != payload or len(text.encode("utf-8")) != record["utf8_bytes"]:
        raise ValueError("saved packet differs from actual wire")
    if bool(reply.get("isError")) != record["is_error"] or record["source_errors"]:
        raise ValueError("unacknowledged public delivery/source failure")
    rows = rows_from_wire(payload)
    _, errors = source_intervals(rows, docs, record["root"])
    if errors or len(rows) != record["rows"]:
        raise ValueError("delivered source fidelity failed: " + repr(errors))
    if any(payload.get(key) is True for key in ("answer_supported", "answer_available", "edit_ready")):
        raise ValueError("retrieval packet acquired answer/edit authority")
    final_coverage = oracle.coverage(case, rows, docs, record["root"])
    selection = [r for r in native if r["question"] == case["question"]]
    if len(selection) > 1:
        raise ValueError("ambiguous source-checked native-pool receipts")
    retrieval, acquired = None, None
    rejected_unbound = None
    if selection:
        receipt = selection[0]
        pool = receipt["pool"]
        order = receipt["selection"]
        if (order["mode"] != "native_acquisition_rank"
                or order["selected_indices"] != list(range(len(pool)))):
            raise ValueError("unexpected pre-MiniLM selector or reordered observer input")
        retrieval = retrieval_coverage(oracle, case, pool, docs, record["root"],
                                       preparation["inventory"]["generation_id"])
        acquired = acquisition(pool, arm)
        rejected_unbound = sum(not r["candidate"].get("binding") for r in receipt["excluded"])
        acquired.update(complete_candidate_rows=len(receipt["complete_candidates"]),
                        excluded_candidate_rows=len(receipt["excluded"]),
                        exclusions_by_reason=dict(Counter(r["reason"] for r in receipt["excluded"])))
    typed_error = bool(record["is_error"] or record["error"] or record["kind"] == "error"
                       or record["status"] in {"failed", "error"})
    negative = case["answerability"] in {"unanswerable", "negative"}
    # Retain the actual original negative predicates. V40 also requires the
    # explicit lack of context; NEW20's independent contract requires emptiness.
    negative_pass = not rows and (name != "v40" or payload.get("context_available") is False)
    source_fact_pass = not typed_error and (negative_pass if negative else final_coverage["all_documented_facts_covered"])
    indices = sql_for_call(sql, record)
    return {
        "id": case["id"], "dataset": name, "arm": arm, "family": case["project_group"],
        "question": case["question"], "answerability": case["answerability"], "root": record["root"],
        "seconds": record["seconds"], "first_call_in_server": record["first_call_in_server"],
        "delivery_error": typed_error, "source_fact_contract_pass": source_fact_pass,
        "retrieval_observer_receipts": len(selection), "retrieval": retrieval,
        "rejected_unbound_not_scored": rejected_unbound, "acquisition": acquired,
        "actual_fts_statements": len(indices), "sql_statement_indices": indices,
        "minilm": minilm(mini, case),
        "final": {"coverage": final_coverage, "source_bodies": len(rows),
                  "source_text_utf8_bytes": sum(len(r["snippet"].encode("utf-8")) for r in rows),
                  "o200k_tokens": record["o200k_tokens"], "utf8_bytes": record["utf8_bytes"],
                  "format": record["format"], "status": record["status"], "error": record["error"]},
    }


def analyze(args) -> dict:
    summaries = {arm: read(args.runs / arm / "SUMMARY.json") for arm in ARMS}
    datasets = summaries["main"]["datasets"]
    frozen = verify_freeze(args.repo, args.freeze, holdout="new20" in datasets)
    expected = sum(DATASETS[name][1] for name in datasets)
    for arm, summary in summaries.items():
        if (summary["status"] != "completed" or summary["invariant_errors"] or summary["arm"] != arm
                or summary["datasets"] != datasets or summary["context_calls"] != expected
                or summary["safety_calls"] != 1 or summary["paid_model_calls"] != 0
                or summary["baseline_sha"] != frozen["baseline_sha"]
                or summary["candidate_sha"] != frozen["candidate_sha"]):
            raise ValueError("incomplete or unpaired arm: " + arm)
    # Opening oracles happens only AFTER code/source hashes and all arm-complete
    # receipts have passed. run.py never imports this module or these helpers.
    result = {
        "schema_version": 1, "execution_integrity_pass": True,
        "quality_is_not_a_ci_gate": True, "baseline_sha": frozen["baseline_sha"],
        "candidate_sha": frozen["candidate_sha"], "freeze_sha256": sha(args.freeze.read_bytes()),
        "datasets": datasets, "arms": {}, "comparisons": {}, "cases": [],
        "limits": {"model": "fixed CPU ONNX MiniLM", "acquisition_rows_per_lane": 256,
                   "rrf_raw_row_allocation": [128, 128], "rrf_k": 60, "section_packet_token_cap": 12000},
        "measurement_notes": [
            "V40 is historically exposed, not a blind holdout; NEW20 opened only after the recorded code/config freeze.",
            "A green execution result proves completeness and source/state invariants, never a quality win.",
            "V40 retains its original coordinate-union oracle; NEW20 retains original literal byte witnesses.",
            "Source/fact scoring preserves original witness and negative predicates, not the old full budget/answer acceptance: V40 negatives require empty sources AND context_available false; NEW20 requires empty sources.",
            "Pool rank is the source-checked native order before MiniLM, not an invented graded relevance ranking.",
            "Acquisition descriptors survive only on observed nonempty source-checked lanes; never sum them as total SQL work.",
            "Actual FTS work is counted by SQLite trace on real unchanged connections, including empty lanes.",
            "MiniLM receipts are completed-work observations; a missing receipt means unknown work, not zero cost.",
            "Wire o200k counts are actual packets, not paid API usage. Session capability randomness can cause small differences.",
            "All-packet token totals include explicit errors; nonerror paired totals are reported separately.",
            "Single sequential runs include observer overhead and model startup; timings are not a statistically controlled speed claim.",
            "Diagnostic receipts are streamed and hash-acknowledged before SDK teardown; SIGUSR1 wakes the worker without polling during public calls. Client ACK polling happens only after the final measured call.",
            "The evaluation fixture's private directory survives worker exit solely for parent read-only database/file verification; isolated container disposal is its explicit cleanup boundary.",
            "No paid model, answer generator, semantic sufficiency judgment or autonomous OpenCode-agent test is included.",
        ],
    }
    all_preparations = 0
    all_safety_sql = 0
    canonical_environment = None
    expected_wheels = {}
    for name in datasets:
        cases, families = dataset(args.repo, name)
        oracle = Oracle(args.repo, name)
        if set(oracle.cases) != {c["id"] for c in cases}:
            raise ValueError("question/oracle membership differs")
        by_arm = {}
        for arm in ARMS:
            arm_cases, preparation_count, safety_count = [], 0, 0
            for family, paths in families.items():
                selected = [case for case in cases if case["project_group"] == family]
                if not selected:
                    continue
                if len({c["question"] for c in selected}) != len(selected):
                    raise ValueError("observer attribution requires unique family questions")
                folder = args.runs / arm / name / family
                docs = documents(args.repo, name, family, paths)
                preparation = read(folder / "PREPARE.json")
                expected_root = "/work/" + name + "/" + family + "/project"
                assert_preparation(preparation, docs, expected_root)
                env = dict(preparation["environment"])
                policy = env.pop("DOCATLAS_ACQUISITION_POLICY", "main")
                if policy != arm or any(k.startswith("DOCATLAS_EXPERIMENT_") for k in env):
                    raise ValueError("unexpected experiment/legacy selector settings")
                if canonical_environment is None:
                    canonical_environment = env
                if env != canonical_environment:
                    raise ValueError("downstream model/policy/assembly environment differs")
                wheel = preparation["installed"]["wheel_sha256"]
                if arm in expected_wheels and expected_wheels[arm] != wheel:
                    raise ValueError("installed wheel changed within an arm")
                expected_wheels[arm] = wheel
                ack = verify_ack(folder)
                state, sql = read(folder / "STATE.json"), read(folder / "SQL.json")
                post_exit = read(folder / "POST_EXIT_STATE.json")
                native, mini = read(folder / "NATIVE.json"), read(folder / "MINILM.json")
                if (state["native_observer_errors"] or state["native_observer_calls"] != len(native)
                        or not state["database_unchanged"] or not state["files_unchanged"]
                        or sql["errors"] or sql["connections"] != sql["attached_connections"]
                        or sql["active"] is not False):
                    raise ValueError("observer/source/state integrity failed")
                if (not post_exit["database_unchanged"] or not post_exit["files_unchanged"]
                        or post_exit.get("error")
                        or post_exit["started_monotonic"] < ack["checkpoint_finished_monotonic"]
                        or post_exit["finished_monotonic"] < post_exit["started_monotonic"]
                        or post_exit["fixture_cleanup"] != "container_disposal_after_parent_verification"
                        or state["fixture_cleanup"] != post_exit["fixture_cleanup"]
                        or preparation["fixture_cleanup"] != post_exit["fixture_cleanup"]):
                    raise ValueError("post-exit source/state invariant failed")
                if any(r["question"] not in {c["question"] for c in selected} for r in native):
                    raise ValueError("unexpected native observer query")
                if any(r["scoring_question_sha256"] not in {sha(c["question"].encode()) for c in selected} for r in mini):
                    raise ValueError("unexpected MiniLM observer query")
                accounted = []
                for case in selected:
                    row = analyze_case(case, name, arm, folder, docs, preparation, native, mini, sql, oracle)
                    accounted += row["sql_statement_indices"]
                    arm_cases.append(row)
                if (folder / "SCOPE_DENIAL_RECORD.json").exists():
                    safety_count += 1
                    safety = read(folder / "SCOPE_DENIAL_RECORD.json")
                    safety_reply = read(folder / "SCOPE_DENIAL.json")
                    packet = json.loads(safety_reply["content"][0]["text"])
                    if rows_from_wire(packet) or packet.get("status") not in {"failed", "insufficient_evidence"}:
                        raise ValueError("scope-denial control delivered evidence")
                    safety_indices = sql_for_call(sql, safety)
                    all_safety_sql += len(safety_indices)
                    accounted += safety_indices
                if sorted(accounted) != list(range(len(sql["statements"]))):
                    raise ValueError("unattributed or multiply-counted real FTS statements")
                preparation_count += 1
            all_preparations += preparation_count
            by_arm[arm] = arm_cases
            result["cases"].extend(arm_cases)
            result["arms"].setdefault(arm, {})[name] = {**aggregate(arm_cases),
                                                       "preparations": preparation_count,
                                                       "scope_controls": safety_count}
        result["comparisons"][name] = {arm: paired(by_arm["main"], by_arm[arm]) for arm in ARMS if arm != "main"}
    for arm in ARMS:
        measured = result["arms"][arm]
        if (sum(r["preparations"] for r in measured.values()) != summaries[arm]["preparations"]
                or summaries[arm]["diagnostic_checkpoints"] != summaries[arm]["preparations"]
                or summaries[arm]["post_exit_state_verifications"] != summaries[arm]["preparations"]
                or sum(r["scope_controls"] for r in measured.values()) != 1
                or sum(r["actual_fts_statements"] for r in measured.values()) == 0):
            raise ValueError("operation ledger or SQL observer coverage incomplete")
    if expected_wheels["retrieval_text"] != expected_wheels["rrf"]:
        raise ValueError("experimental policies must use the same candidate wheel")
    result["installed_wheel_sha256"] = expected_wheels
    result["frozen_environment"] = canonical_environment
    result["operation_accounting"] = {
        "benchmark_context_calls": len(result["cases"]), "scope_controls": 3,
        "total_context_calls": len(result["cases"]) + 3, "public_preparations": all_preparations,
        "diagnostic_checkpoints": all_preparations, "post_exit_state_verifications": all_preparations,
        "actual_benchmark_fts_statements": sum(c["actual_fts_statements"] for c in result["cases"]),
        "actual_scope_control_fts_statements": all_safety_sql, "paid_model_calls": 0,
        "source_continuation_calls": 0, "automatic_retries": 0,
    }
    for key, actual in (("expected_context_calls", len(result["cases"])),
                        ("expected_benchmark_context_calls", len(result["cases"])),
                        ("expected_scope_controls", 3),
                        ("expected_preparations", all_preparations),
                        ("expected_total_context_calls", len(result["cases"]) + 3)):
        if key in frozen and frozen[key] != actual:
            raise ValueError("frozen operation count mismatch: " + key)
    verify_freeze(args.repo, args.freeze, holdout="new20" in datasets)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "runs", "out", "freeze"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    for name in ("repo", "runs", "out", "freeze"):
        setattr(args, name, getattr(args, name).resolve())
    if args.out.exists():
        raise ValueError("fresh comparison output required; preserve earlier attempts")
    try:
        result = analyze(args)
    except Exception as exc:
        save(args.out, {"execution_integrity_pass": False, "quality_not_assessable": True,
                        "error": str(exc), "traceback": traceback.format_exc()})
        raise
    save(args.out, result)
    # One compact line per arm/dataset remains usable even when downloading the
    # large exact-source artifacts is inconvenient. Full cases remain saved.
    keys = ("cases", "historic_labels", "delivery_errors", "documented_facts", "final_covered_facts",
            "final_fact_coverage", "pool_observed_cases", "pool_unobserved_cases", "pool_covered_facts",
            "pool_fact_coverage_observed_cases", "pool_prefix_coverage", "pool_rows", "known_markdown_owners",
            "observed_lane_saturation_cases", "actual_fts_statements", "minilm_missing_completion_receipts",
            "minilm_completed_forward_passes", "minilm_completed_input_pair_tokens", "final_source_bodies",
            "wire_o200k_tokens_all", "wire_o200k_tokens_nonerror", "wire_utf8_bytes", "context_seconds")
    for arm, datasets in result["arms"].items():
        for name, summary in datasets.items():
            print(json.dumps({"arm": arm, "dataset": name,
                              **{key: summary[key] for key in keys}}, ensure_ascii=False))
    for name, comparisons in result["comparisons"].items():
        for arm, row in comparisons.items():
            print(json.dumps({"comparison": arm + " vs main", "dataset": name,
                              **row["summary"]}, ensure_ascii=False))
    print(json.dumps({"execution_integrity_pass": True, "quality_is_not_a_ci_gate": True,
                      "operation_accounting": result["operation_accounting"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
