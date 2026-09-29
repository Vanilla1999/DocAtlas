"""M2 — cross-lingual relevance experiment: compare lexical (A) vs encoder (B) signals.

Runs on the frozen pool from pool.json (built from M1.5 manifest).
Variant A: lexical overlap ratio (same formula as evidence_qualification).
Variant B: multilingual encoder cosine similarity (paraphrase-multilingual-MiniLM-L12-v2).

Records raw scores, model identity, runtime params, and per-task rankings.
Does NOT modify production code or indices.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
POOL = HERE / "pool.json"
RESULTS = HERE / "results.json"
EVIDENCE = HERE / "evidence"


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE.parents[1], text=True).strip()


def lexical_ratio(question: str, block_text: str) -> float:
    """Replicate the lexical overlap ratio from evidence_qualification.

    terms = casefold tokens >= 4 chars from the question (with Cyrillic fallback).
    matched = terms present in the block text (casefolded).
    ratio = len(matched) / len(terms).
    """
    terms = tuple(dict.fromkeys(
        token.casefold()
        for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9_.-]{4,}", question)
    ))
    if not terms:
        return 0.0
    body = block_text.casefold()
    matched = tuple(t for t in terms if t in body)
    return len(matched) / len(terms)


def encoder_scores(questions: list[str], blocks: list[str], model_name: str) -> list[list[float]]:
    """Compute cosine similarity matrix [question_i][block_j] via fastembed."""
    import numpy as np
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=model_name)
    q_vecs = list(model.embed(questions))
    b_vecs = list(model.embed(blocks))
    q_arr = np.array(q_vecs, dtype=np.float32)
    b_arr = np.array(b_vecs, dtype=np.float32)
    # Normalise
    q_norm = q_arr / (np.linalg.norm(q_arr, axis=1, keepdims=True) + 1e-9)
    b_norm = b_arr / (np.linalg.norm(b_arr, axis=1, keepdims=True) + 1e-9)
    return (q_norm @ b_norm.T).tolist()


def mrr_at_k(ranked_relevance: list[bool], k: int = 5) -> float:
    """MRR@K: 1/rank of first relevant in top-K, 0 if none."""
    for i, rel in enumerate(ranked_relevance[:k], start=1):
        if rel:
            return 1.0 / i
    return 0.0


def recall_at_k(ranked_relevance: list[bool], k: int = 5) -> float:
    """Recall@K: 1 if any relevant in top-K, 0 otherwise."""
    return 1.0 if any(ranked_relevance[:k]) else 0.0


def run() -> dict:
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    blocks = pool["blocks"]
    tasks = pool["tasks"]
    block_texts = [b["text"] for b in blocks]
    questions = [t["question"] for t in tasks]

    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "git_head": _git_head(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Variant A: lexical
    t0 = time.perf_counter()
    a_scores = []
    for q in questions:
        row = [lexical_ratio(q, bt) for bt in block_texts]
        a_scores.append(row)
    a_time = time.perf_counter() - t0

    # Variant B: encoder
    model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
    t0 = time.perf_counter()
    try:
        b_scores = encoder_scores(questions, block_texts, model_name)
        b_time = time.perf_counter() - t0
        b_status = "OK"
        # Model identity
        model_hash = hashlib.sha256(
            json.dumps({"model": model_name, "dim": len(b_scores[0])}).encode()
        ).hexdigest()[:16]
    except Exception as exc:
        b_scores = None
        b_time = 0.0
        b_status = f"BLOCKED: {type(exc).__name__}: {exc}"
        model_hash = None

    # Build per-task results
    task_results = []
    for ti, task in enumerate(tasks):
        block_ids = [b["block_id"] for b in task["blocks"]]
        # Relevance labels for this task's blocks only
        relevance = {b["block_id"]: b["relevant_to_question"] for b in task["blocks"]}
        source_ok = {b["block_id"]: b["source_allowed"] for b in task["blocks"]}
        covered = {b["block_id"]: b["covered_fact_ids"] for b in task["blocks"]}

        for variant_name, scores in (("A_lexical", a_scores), ("B_encoder", b_scores)):
            if scores is None:
                task_results.append({
                    "task_id": task["task_id"],
                    "split": task["split"],
                    "question": task["question"],
                    "formulation": task["formulation"],
                    "variant": variant_name,
                    "status": "BLOCKED",
                    "block_scores": [],
                    "mrr_at_5": None,
                    "recall_at_5": None,
                })
                continue

            # Rank this task's blocks by score
            scored = [
                (bid, scores[ti][blocks.index(next(b for b in blocks if b["block_id"] == bid))],
                 relevance[bid], source_ok[bid], covered[bid])
                for bid in block_ids
            ]
            ranked = sorted(scored, key=lambda x: -x[1])
            ranked_relevance = [r[2] for r in ranked]

            task_results.append({
                "task_id": task["task_id"],
                "split": task["split"],
                "question": task["question"],
                "formulation": task["formulation"],
                "variant": variant_name,
                "status": "OK",
                "block_scores": [
                    {
                        "block_id": r[0],
                        "score": r[1],
                        "relevant": r[2],
                        "source_allowed": r[3],
                        "covered_fact_ids": r[4],
                        "rank": i + 1,
                    }
                    for i, r in enumerate(ranked)
                ],
                "mrr_at_5": mrr_at_k(ranked_relevance, 5),
                "recall_at_5": recall_at_k(ranked_relevance, 5),
            })

    # Aggregate metrics per variant per split
    summary = {}
    for variant in ("A_lexical", "B_encoder"):
        v_results = [r for r in task_results if r["variant"] == variant and r["status"] == "OK"]
        if not v_results:
            summary[variant] = {"status": "BLOCKED", "n": 0}
            continue
        for split in ("development", "calibration", "holdout"):
            s_results = [r for r in v_results if r["split"] == split]
            if not s_results:
                continue
            key = f"{variant}/{split}"
            summary[key] = {
                "n": len(s_results),
                "mrr_at_5": sum(r["mrr_at_5"] for r in s_results) / len(s_results),
                "recall_at_5": sum(r["recall_at_5"] for r in s_results) / len(s_results),
            }

    result = {
        "schema_version": 1,
        "environment": environment,
        "model_b": {
            "name": model_name,
            "status": b_status,
            "model_hash": model_hash,
            "inference_seconds": b_time,
        },
        "lexical_a": {"inference_seconds": a_time},
        "pool_blocks": len(blocks),
        "pool_tasks": len(tasks),
        "task_results": task_results,
        "summary": summary,
    }

    RESULTS.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    r = run()
    print(json.dumps(r["summary"], ensure_ascii=False, indent=2))
