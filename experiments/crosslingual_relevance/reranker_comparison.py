"""Compare MPNet bi-encoder vs BGE-reranker-v2-m3 cross-encoder on the same fixed pool.

Both scorers evaluate the same (question, block) pairs from pool.json.
Metrics: first complete witness rank, MRR, known-positive Recall@K,
hard-negative inversions, latency, scorer failures.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
POOL = HERE / "pool.json"


def run_comparison() -> dict:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    blocks = pool["blocks"]
    tasks = pool["tasks"]
    block_texts = [b["text"] for b in blocks]

    # MPNet scores (from run.py encoder_scores)
    from .run import encoder_scores
    from .mpnet_scorer import model_identity as mpnet_identity
    model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

    t0 = time.perf_counter()
    questions = [t["question"] for t in tasks]
    mpnet_matrix = encoder_scores(questions, block_texts, model_name)
    mpnet_time = time.perf_counter() - t0

    # BGE reranker scores
    from .bge_reranker_scorer import reranker_scorer, reranker_identity
    reranker_matrix = []
    t0 = time.perf_counter()
    for q in questions:
        row = [reranker_scorer(q, bt) for bt in block_texts]
        reranker_matrix.append(row)
    reranker_time = time.perf_counter() - t0

    # Build per-task results
    task_results = []
    for ti, task in enumerate(tasks):
        judged = {b["block_id"]: b for b in task["blocks"]}
        known_positives = {bid for bid, l in judged.items()
                           if l["relevant_to_question"] and l["source_allowed"]}

        for variant_name, scores in (("MPNet", mpnet_matrix[ti]), ("BGE_reranker", reranker_matrix[ti])):
            # Rank blocks by score descending
            ranked = sorted(zip(blocks, scores), key=lambda x: (-x[1], x[0]["block_id"]))
            ranks = []
            for rank, (b, s) in enumerate(ranked, 1):
                label = judged.get(b["block_id"])
                rel = None if label is None else label["relevant_to_question"]
                allowed = None if label is None else label["source_allowed"]
                ranks.append({"block_id": b["block_id"], "score": float(s), "rank": rank,
                              "relevant": rel, "source_allowed": allowed,
                              "judged": label is not None})

            # Metrics
            first_pos_rank = None
            for r in ranks:
                if r["relevant"] is True and r["source_allowed"] is True:
                    first_pos_rank = r["rank"]
                    break
            mrr = 1.0 / first_pos_rank if first_pos_rank else 0.0

            # Known-positive Recall@5
            top5_ids = {r["block_id"] for r in ranks[:5]}
            recall5 = len(top5_ids & known_positives) / len(known_positives) if known_positives else None

            # Hard-negative inversions: allowed negatives ranked above known positives
            inversions = []
            for r in ranks:
                if r["relevant"] is False and r["source_allowed"] is True:
                    for r2 in ranks:
                        if r2["relevant"] is True and r2["source_allowed"] is True:
                            if r["rank"] < r2["rank"]:
                                inversions.append({
                                    "negative": r["block_id"], "negative_score": r["score"],
                                    "positive": r2["block_id"], "positive_score": r2["score"],
                                    "gap": r["score"] - r2["score"],
                                })

            # Allowed irrelevant ranked above first complete witness
            allowed_irr_above = []
            if first_pos_rank:
                for r in ranks[:first_pos_rank - 1]:
                    if r["source_allowed"] is True and r["relevant"] is not True:
                        allowed_irr_above.append(r["block_id"])

            task_results.append({
                "task_id": task["task_id"],
                "split": task["split"],
                "formulation": task["formulation"],
                "variant": variant_name,
                "first_positive_rank": first_pos_rank,
                "mrr": mrr,
                "known_positive_recall_at_5": recall5,
                "inversions": inversions,
                "allowed_irrelevant_above_first_positive": allowed_irr_above,
                "top_5": [{"block_id": r["block_id"], "score": r["score"],
                           "rel": r["relevant"], "allowed": r["source_allowed"]}
                          for r in ranks[:5]],
            })

    # Aggregate
    summary = {}
    for variant in ("MPNet", "BGE_reranker"):
        v_results = [r for r in task_results if r["variant"] == variant]
        mrrs = [r["mrr"] for r in v_results if r["first_positive_rank"] is not None]
        recalls = [r["known_positive_recall_at_5"] for r in v_results
                   if r["known_positive_recall_at_5"] is not None]
        total_inv = sum(len(r["inversions"]) for r in v_results)
        summary[variant] = {
            "mean_mrr": sum(mrrs) / len(mrrs) if mrrs else None,
            "mean_recall_at_5": sum(recalls) / len(recalls) if recalls else None,
            "total_inversions": total_inv,
            "tasks_with_first_positive": sum(1 for r in v_results if r["first_positive_rank"] is not None),
        }
        if variant == "MPNet":
            summary[variant]["latency_seconds"] = mpnet_time
            summary[variant]["identity"] = mpnet_identity()
        else:
            summary[variant]["latency_seconds"] = reranker_time
            summary[variant]["identity"] = reranker_identity()

    result = {
        "schema_version": 1,
        "comparison": "MPNet_bi-encoder_vs_BGE_reranker_v2_m3",
        "pool_blocks": len(blocks),
        "pool_tasks": len(tasks),
        "summary": summary,
        "task_results": task_results,
    }

    from .evaluation_v2 import save_new_report
    import uuid
    out_path = HERE / "review_runs" / f"reranker-comparison-{uuid.uuid4().hex}.json"
    save_new_report(out_path, result)
    return result


if __name__ == "__main__":
    import os
    # Set env if not set
    os.environ.setdefault("DOCATLAS_RERANKER_MODEL_DIR", "/tmp/opencode/bge-reranker-export")
    os.environ.setdefault("DOCATLAS_RERANKER_MODEL_MANIFEST", "/tmp/opencode/locks/bge_reranker.json")
    os.environ.setdefault("DOCATLAS_RELEVANCE_MODEL_DIR", "/tmp/opencode/mpnet-export")
    os.environ.setdefault("DOCATLAS_RELEVANCE_MODEL_MANIFEST", "/tmp/opencode/locks/mpnet.json")
    os.environ.setdefault("DOCATLAS_FASTEMBED_CACHE_DIR", "/tmp/fastembed_cache")

    r = run_comparison()
    print(json.dumps(r["summary"], ensure_ascii=False, indent=2, default=str))

    # Print per-task inversions
    for tr in r["task_results"]:
        if tr["inversions"]:
            print(f"\n{tr['task_id']} ({tr['variant']}): {len(tr['inversions'])} inversions")
            for inv in tr["inversions"]:
                print(f"  neg={inv['negative']} ({inv['negative_score']:.4f}) > "
                      f"pos={inv['positive']} ({inv['positive_score']:.4f}) gap={inv['gap']:.4f}")
