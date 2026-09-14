"""Run preregistered selection policies over the unchanged four retrieval lanes.

No inference, network calls, hidden questions, or production-file changes.
The existing evaluator rebuilds the exact source-bound inputs. Instrumentation
observes qualified variants, then restores every patched function in finally.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import sys
import time
from unittest.mock import patch

from selection_policy import make_item, prefer_signature, retain_extend, signature_subjects
from docmancer.docs.application import docs_context_projection as projection
from docmancer.docs.application.context_selection import context_selection_decision
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens, _snapshot_entry
from eval.evidence_quality_v2.run import load_protocol, registry_for, audit_payload
from eval.evidence_quality_v2.semantic import assess_context

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def spans(payload):
    return [(s["path_or_url"], s["snippet"]) for s in payload.get("sources", [])]


def retention(before, after):
    return all(any(path == other_path and text in other_text
                   for other_path, other_text in spans(after)) for path, text in spans(before))


def execute_lane(evaluator, output, use_signature):
    original_project = projection.project_docs_context
    original_fragments = projection._qualified_fragments
    original_ranking = projection._facet_aware_candidates
    original_payload = projection._payload
    captured = []

    def observe(*, retrieval, **kwargs):
        if not retrieval.get("context_pack"):
            return original_project(retrieval=retrieval, **kwargs)
        untouched = deepcopy(retrieval)
        plan = retrieval.get("documentation_query_plan") or {}
        question = str(plan.get("original_question") or retrieval.get("question") or next(
            (q.get("text", "") for q in plan.get("queries", []) if q.get("query_id") == "query-original"), ""))
        candidates, final = [], {}
        rank_counter = 0

        def fragments(source, **parameters):
            nonlocal rank_counter
            values = original_fragments(source, **parameters)
            origin = source.get("_qualification_candidate", {})
            for value in values:
                bound = make_item(value, origin, rank=rank_counter)
                if bound is not None:
                    candidates.append(bound)
            rank_counter += 1
            return values

        def ranking(values, **parameters):
            ranked = original_ranking(values, **parameters)
            return prefer_signature(ranked, question) if use_signature else ranked

        def payload(sources, **parameters):
            result = original_payload(sources, **parameters)
            if sources:
                final["sources"] = deepcopy(sources)
                final["plan"] = deepcopy(parameters.get("query_plan") or {})
            return result

        # Restore the public function inside the observation: recursive fallback
        # remains part of the same case, not an extra observation or a new lane.
        with patch.object(projection, "project_docs_context", original_project), \
             patch.object(projection, "_qualified_fragments", fragments), \
             patch.object(projection, "_facet_aware_candidates", ranking), \
             patch.object(projection, "_payload", payload):
            base, snapshot = original_project(retrieval=retrieval, **kwargs)

        extra, extra_snapshot = deepcopy(base), deepcopy(snapshot)
        reason = None
        bound_baseline = []
        if base.get("sources"):
            internals = {s["evidence_id"]: s for s in final.get("sources", [])}
            for source in base["sources"]:
                internal = internals.get(source["evidence_id"])
                origin = snapshot.get(source["evidence_id"], {}).get("source", {})
                bound = make_item(internal, origin, rank=-1) if internal else None
                if bound is None:
                    reason = "baseline_quote_not_unambiguously_bound"
                    break
                bound_baseline.append(bound)
            if reason is None:
                final_plan = final["plan"]
                public_ids = projection._public_query_ids(final_plan)
                packets = {}

                def build(items):
                    key = tuple((x["source"]["evidence_id"], x["source"]["snippet"]) for x in items)
                    if key not in packets:
                        sources = [x["source"] for x in items]
                        result = original_payload(sources, decision=context_selection_decision(sources, public_ids), query_plan=final_plan)
                        snap = {s["evidence_id"]: _snapshot_entry(x["origin"], s)
                                for x, s in zip(items, result["sources"])}
                        if root := retrieval.get("_source_continuation_project_root"):
                            projection.attach_source_continuation_locators(result, snap, root=root, max_tokens=800)
                        packets[key] = result, snap
                    return packets[key]

                rebuilt, _ = build(bound_baseline)
                if rebuilt != base:
                    reason = "baseline_full_payload_reconstruction_differs"
                else:
                    chosen = retain_extend(
                        bound_baseline, candidates, question=question,
                        lookup_texts=tuple(str(q.get("text") or "") for q in final_plan.get("queries", [])),
                        tokens=lambda xs: docs_context_budget_tokens(build(xs)[0]),
                    )
                    extra, extra_snapshot = deepcopy(build(chosen))
        else:
            reason = "empty_baseline_unchanged"
        assert retention(base, extra), "Retention invariant violated"
        assert docs_context_budget_tokens(extra) <= 800
        captured.append({"input": untouched, "input_sha256": digest(untouched), "question": question,
                         "base": deepcopy(base), "base_snapshot": deepcopy(snapshot),
                         "extension": extra, "extension_snapshot": extra_snapshot,
                         "qualified_variants": len(candidates), "extension_noop_reason": reason,
                         "projection_diagnostics": deepcopy(retrieval.get("retrieval_diagnostics", {}))})
        return base, snapshot

    argv = [str(HERE.parent / "research-suite/evaluate.py"),
            "--input", "/tmp/docatlas-research-input", "--output", str(output),
            "--embeddings", "/tmp/docatlas-embedding-output-v2/rankings.json",
            "--contexts", "/tmp/docatlas-contextual-final/contexts.json", "--hybrid-factorial-only"]
    with patch.object(sys, "argv", argv), patch.object(projection, "project_docs_context", observe):
        evaluator.main()
    rows = json.loads((output / "rows.json").read_text())
    assert len(rows) == len(captured) == 320, (len(rows), len(captured))
    for row, observation in zip(rows, captured):
        assert row["replay"] == observation["base"], row["id"]
    return rows, captured


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    _, cases, manifest = load_protocol()
    case_map = {c["id"]: c for c in cases}
    spec = importlib.util.spec_from_file_location("selection_factorial_evaluator", HERE.parent / "research-suite/evaluate.py")
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    all_rows, raw_observations, current = [], [], {}
    historical = {(r["id"], r["variant"]): r for r in json.loads(lzma.decompress((HERE / "results/raw-results.json.xz").read_bytes()))}
    for use_signature in (False, True):
        policy = "signature_first" if use_signature else "current"
        rows, observations = execute_lane(evaluator, args.output / policy, use_signature)
        raw_observations.append({"policy": policy, "observations": observations})
        for row, observation in zip(rows, observations):
            case = case_map[row["id"]]
            key = row["id"], row["variant"]
            if not use_signature:
                prior = historical[key]
                assert row["selected_keys"] == prior["selected_keys"], key
                assert spans(row["replay"]) == spans(prior["replay"]), key
                assert row["replay_assessment"] == prior["replay_assessment"], key
                current[key] = observation
            else:
                assert observation["input_sha256"] == current[key]["input_sha256"], key
                if not signature_subjects(observation["question"]):
                    assert row["replay"] == current[key]["base"], ("non-signature changed", key)
            for suffix, payload, snapshot in (
                (policy, row["replay"], row["replay_snapshot"]),
                ("signature_first_retain_extend" if use_signature else "retain_extend",
                 observation["extension"], observation["extension_snapshot"]),
            ):
                corpus = Path("/tmp/docatlas-continued-systemic/acceptance/full80_current/corpus") / case["project_group"]
                errors = audit_payload(payload, snapshot, corpus)
                for source in payload.get("sources", []):
                    if not any(source["path_or_url"] == c.get("path")
                               and source["snippet"] in str(c.get("content") or "")
                               for c in observation["input"]["context_pack"]):
                        errors.append("snippet escaped unchanged candidate pool")
                if payload.get("answer_supported") is not False or payload.get("answer_available") is not False or payload.get("edit_ready") is not False:
                    errors.append("retrieval-only answer/edit policy changed")
                if len(payload.get("sources", [])) > 3 or docs_context_budget_tokens(payload) > 800:
                    errors.append("full DTO or source budget violation")
                all_rows.append({"id": row["id"], "project_group": case["project_group"],
                    "question": case["question"], "retrieval": row["variant"], "selection": suffix,
                    "answerability": case["answerability"], "payload": payload, "snapshot": snapshot,
                    "assessment": assess_context(case, payload, registry_for(case["project_group"], manifest)),
                    "audit_errors": errors, "tokens": docs_context_budget_tokens(payload),
                    "retains_same_retrieval_current": retention(current[key]["base"], payload),
                    "qualified_variants": observation["qualified_variants"],
                    "extension_noop_reason": observation["extension_noop_reason"],
                    "input_sha256": observation["input_sha256"]})
    assert len(all_rows) == 1280
    ok = lambda row: row["assessment"]["context_sufficiency"] == "sufficient"
    reference = {r["id"]: r for r in all_rows if r["retrieval"] == "hybrid_plain" and r["selection"] == "current"}
    reference_ok = {cid for cid, r in reference.items() if r["answerability"] == "within_budget" and ok(r)}
    assert len(reference_ok) == 34
    summary = {}
    for name in sorted({r["retrieval"] + "/" + r["selection"] for r in all_rows}):
        lane = [r for r in all_rows if r["retrieval"] + "/" + r["selection"] == name]
        success = {r["id"] for r in lane if r["answerability"] == "within_budget" and ok(r)}
        wins, losses = sorted(success - reference_ok), sorted(reference_ok - success)
        controls = [r["id"] for r in lane if r["answerability"] != "within_budget" and ok(r)]
        lost_quotes = [r["id"] for r in lane if not retention(reference[r["id"]]["payload"], r["payload"])]
        error_count = sum(len(r["audit_errors"]) for r in lane)
        projects_won = sorted({case_map[cid]["project_group"] for cid in wins})
        summary[name] = {"sufficient": len(success), "wins_vs_hybrid_current": wins,
            "losses_vs_hybrid_current": losses, "winning_project_groups": projects_won,
            "sufficient_controls": controls, "audit_errors": error_count,
            "literal_losses_vs_hybrid_current": lost_quotes,
            "retention_losses_same_retrieval": [r["id"] for r in lane if not r["retains_same_retrieval_current"]],
            "changed_vs_hybrid_current": [r["id"] for r in lane if spans(r["payload"]) != spans(reference[r["id"]]["payload"])],
            "max_tokens": max(r["tokens"] for r in lane),
            "mean_tokens": sum(r["tokens"] for r in lane) / len(lane),
            "positive_assessments": dict(Counter(r["assessment"]["context_sufficiency"] for r in lane if r["answerability"] == "within_budget")),
            "screening_passed": len(success) >= 36 and len(projects_won) >= 2 and not losses and not controls and not error_count and not lost_quotes}
    validation = {"rows": len(all_rows), "historical_controls_reproduced": 320,
                  "audit_errors": sum(len(r["audit_errors"]) for r in all_rows),
                  "max_tokens": max(r["tokens"] for r in all_rows),
                  "holdout_opened": False, "answer_model_run": False, "production_changed": False,
                  "elapsed_seconds": time.monotonic() - started,
                  "policy_sha256": hashlib.sha256((HERE / "selection_policy.py").read_bytes()).hexdigest(),
                  "noop_reasons": dict(Counter(r["extension_noop_reason"] for r in all_rows if r["selection"] in {"retain_extend", "signature_first_retain_extend"}))}
    save(args.output / "summary.json", summary)
    save(args.output / "validation.json", validation)
    save(args.output / "questions.json", all_rows)
    (args.output / "raw-observations.json.xz").write_bytes(lzma.compress(json.dumps(raw_observations, ensure_ascii=False, default=str).encode()))
    (args.output / "raw-results.json.xz").write_bytes(lzma.compress(json.dumps(all_rows, ensure_ascii=False, default=str).encode()))
    print("SELECTION_SUMMARY_BEGIN", flush=True)
    print(json.dumps({"summary": summary, "validation": validation}, ensure_ascii=False, indent=2), flush=True)
    print("SELECTION_SUMMARY_END", flush=True)
    assert validation["audit_errors"] == 0, "Artifacts saved, but integrity validation failed"
    assert all(not r["retention_losses_same_retrieval"] for name, r in summary.items() if name.endswith("/retain_extend"))


if __name__ == "__main__":
    main()
