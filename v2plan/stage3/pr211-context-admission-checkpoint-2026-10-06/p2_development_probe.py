"""First P2 development-only experiment; never executes frozen holdout."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from collections import defaultdict

from p1_contract_corpus import BASE
from p2_retrieval_prototype import Index, project


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    freeze_path = BASE / "archives/p1-approved-freeze-manifest.json"
    freeze = json.loads(freeze_path.read_text())
    assert freeze["p1_done"] and freeze["approved_freeze"]
    entry = next(e for e in freeze["files"] if "development" in e["path"])
    path = BASE / entry["path"]
    assert sha(path) == entry["sha256"]
    cases = json.loads(path.read_text())["cases"]
    assert len(cases) == 88
    # Same multilingual source pool for both algorithms, without case IDs/gold.
    sources = {}
    for case in cases:
        meta = case["source_metadata"]
        identity = meta["source_id"]
        row = dict(id=identity, text=case["source"], metadata=meta)
        assert identity not in sources or sources[identity] == row
        sources[identity] = row
    pool = list(sources.values())
    pool_hash = hashlib.sha256(json.dumps(pool, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    records = []
    for mode in ("lexical", "char-tfidf"):
        started = time.perf_counter()
        index = Index(pool, mode)
        initialization_seconds = time.perf_counter() - started
        for case in cases:
            started = time.perf_counter()
            queries = [case["question"], *case["lookup_queries"]]
            stages = index.search(queries, case["request_scope"], top_k=5)
            output = project(stages["prefit"], max_bytes=8192)
            def delivered(rows):
                return [w["fact_id"] for w in case["required_witnesses"] if any(
                    row["source"]["id"] == case["source_metadata"]["source_id"] and
                    w["text"] in row["source"]["text"] for row in rows)]
            final_facts = [w["fact_id"] for w in case["required_witnesses"] if any(
                s["source_id"] == case["source_metadata"]["source_id"] and w["text"] in s["text"] for s in output["sources"])]
            stages_facts = dict(retrieved=delivered(stages["retrieved"]), qualified=delivered(stages["qualified"]),
                                prefit=delivered(stages["prefit"]), final=final_facts)
            first_loss = {}
            for w in case["required_witnesses"]:
                first_loss[w["fact_id"]] = next((stage for stage, facts in stages_facts.items() if w["fact_id"] not in facts), None)
            records.append(dict(case_id=case["id"], mode=mode, lane=[case["question_language"], case["source_language"], bool(case["lookup_queries"])],
                original=case["question"], explicit_queries=queries, stage_fact_ids=stages_facts, first_loss=first_loss,
                elapsed_seconds=time.perf_counter() - started, initialization_seconds=initialization_seconds,
                output=output, serialized_bytes=len(json.dumps(output, ensure_ascii=False).encode()),
                status=stages["status"], rejections=stages["rejections"]))
    summaries = defaultdict(lambda: dict(cases=0, required_witnesses=0, delivered_witnesses=0))
    for record, case in zip(records, cases * 2):
        key = record["mode"] + ":" + ":".join(map(str, record["lane"]))
        summaries[key]["cases"] += 1
        summaries[key]["required_witnesses"] += len(case["required_witnesses"])
        summaries[key]["delivered_witnesses"] += len(record["stage_fact_ids"]["final"])
    report = dict(schema="p2-development-probe-v1", status="P2_ACTIVE_NOT_ACCEPTED",
        head=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        product_diff_sha256=hashlib.sha256(subprocess.check_output(["git", "diff", "--", "docmancer"])).hexdigest(),
        python=platform.python_version(), freeze_sha256=sha(freeze_path), development_sha256=sha(path),
        prototype_sha256=sha(BASE / "p2_retrieval_prototype.py"), runner_sha256=sha(BASE / "p2_development_probe.py"),
        source_pool_sha256=pool_hash, sources=len(pool), records=records, lane_summaries=dict(summaries),
        model_calls=0, network_calls=0, model_artifact=None, holdout_executed=False,
        experimental_budget=dict(top_k=5, final_serialized_bytes=8192),
        limitations=["Not product baseline: both algorithms are isolated prototype scorers",
            "Experimental byte/top-k caps are not actual production token/search budget binding",
            "Character TF-IDF is orthographic, not a bilingual semantic replacement",
            "Source metadata guards are fixture-level, not actual SQLite generation qualification",
            "No proof/topical/original coverage claims; negative cases are not certified passed",
            "Timings exploratory, not approved paired p95 cold/warm SLA",
            "Frozen holdout, required real controls, and same-snapshot product baseline/ablation remain pending"])
    out = BASE / "archives/p2-development-probe-v1.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(status=report["status"], cases=len(cases), sources=len(pool), lanes=dict(summaries))))


if __name__ == "__main__":
    main()
