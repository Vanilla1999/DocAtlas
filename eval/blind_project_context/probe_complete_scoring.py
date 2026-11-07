"""Installed real-model diagnostic, not a public-pipeline calibration gate.

Run from outside the checkout. Only calibration rows of the frozen review
export are evaluated; no holdout labels are loaded. No deployable threshold
artifact is emitted: these older labels do not exhaustively label structural
usefulness and this probe does not establish source admission or delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import time

from docmancer.core.structured_chunking import parse_markdown_parents
from docmancer.docs.application.complete_context_scoring import ScoringUnit, score_complete_units
from docmancer.docs.application.experimental_selection_modes import preload_mini_runtime
import docmancer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inputs = {name: (args.review / name).read_bytes()
              for name in ("corpus.json", "cases.json", "calibration_labels.json")}
    documents = [d for d in json.loads(inputs["corpus.json"])["documents"]
                 if d.get("split") == "calibration"]
    cases = [c for c in json.loads(inputs["cases.json"])["cases"]
             if c.get("split") == "calibration"]
    labels = json.loads(inputs["calibration_labels.json"])
    labels_by_id = {c["id"]: c for c in labels["cases"]}
    document_by_path = {d["path"]: d for d in documents}
    for witness in labels["witnesses"].values():
        assert witness["quote"] in document_by_path[witness["source_path"]]["content"]
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()}
    started, cpu = time.perf_counter(), time.process_time()
    preload = preload_mini_runtime(str(args.model.resolve()))
    records = []
    positive_scores = []
    for case in cases:
        units, unit_sources = [], {}
        for document in documents:
            if document["document_group"] != case["document_group"]:
                continue
            parents = parse_markdown_parents(document["content"], document["path"])
            # The frozen calibration documents each have one own body, no
            # ancestors/closure. Do not pretend they test the structural recipe.
            assert len(parents) == 1
            parent = parents[0]
            units.append(ScoringUnit(parent.logical_id, parent.display_text))
            unit_sources[parent.logical_id] = document["path"]
        scores, receipt = score_complete_units([case["question"]], units, str(args.model))
        useful_paths = {
            labels["witnesses"][witness]["source_path"]
            for fact in labels_by_id[case["id"]]["required_facts"]
            for witness in fact["source_witnesses"]
        }
        for score in scores:
            score["source_path"] = unit_sources[score["identity"]]
            score["witness_positive"] = score["source_path"] in useful_paths
            if score["witness_positive"]:
                positive_scores.append(score["score"])
        records.append({"id": case["id"], "scores": scores, "receipt": receipt,
                        "all_irrelevant": labels_by_id[case["id"]]["label"] == "all_irrelevant"})
    diagnostic_tau = min(positive_scores)
    for record in records:
        record["diagnostic_selected"] = [s["source_path"] for s in record["scores"]
                                         if s["score"] >= diagnostic_tau]
    # Independent long-body / long-question coverage exercise. This is a model
    # boundary probe, not evidence that a final answer delivered these facts.
    prefix = "The visitor catalogue lists painted pottery, woven baskets and carved bowls. " * 90
    tail = "Cryogenic storage is prohibited until the signed viability certificate arrives."
    long_query = "Describe the collection catalogue and its handling requirements. " * 55 + tail
    long_scores, long_receipt = score_complete_units(
        [long_query], [ScoringUnit("long-body-tail", prefix + tail)], str(args.model),
    )
    report = {
        "boundary": "installed_scorer_only_not_get_docs_context",
        "package_path": docmancer.__file__, "inputs_sha256": manifest,
        "preload": preload, "cases": records, "diagnostic_tau": diagnostic_tau,
        "deployable_policy": False,
        "limitations": ["No exhaustive usefulness labels", "No independent validation",
                        "No source admission/delivery/closure/client measurement"],
        "long_input": {"scores": long_scores, "receipt": long_receipt,
                       "body_sha256": hashlib.sha256((prefix + tail).encode()).hexdigest()},
        "seconds": time.perf_counter() - started, "cpu_seconds": time.process_time() - cpu,
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("boundary", "diagnostic_tau", "seconds", "cpu_seconds", "max_rss_kib")}))


if __name__ == "__main__":
    main()
