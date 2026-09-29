"""M2 — cross-lingual relevance experiment: compare lexical (A) vs encoder (B) signals.

Runs on the frozen pool from pool.json (built from M1.5 manifest).
Variant A: diagnostic lexical overlap (not production qualification).
Variant B: pinned multilingual MPNet cosine; all pool blocks ranked before judgments.

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
    """Diagnostic token overlap only; not the production qualifier.

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
    from .mpnet_scorer import _get_model
    from .model_manifest import MODEL_NAME
    if model_name != MODEL_NAME:
        raise ValueError("the artifact lock permits only its declared model")
    model = _get_model()
    q_vecs = list(model.embed(questions))
    b_vecs = list(model.embed(blocks))
    q_arr = np.array(q_vecs, dtype=np.float32)
    b_arr = np.array(b_vecs, dtype=np.float32)
    for array, count in ((q_arr, len(questions)), (b_arr, len(blocks))):
        if array.shape != (count, 768) or not np.all(np.isfinite(array)):
            raise ValueError("invalid embedding matrix")
        norms = np.linalg.norm(array, axis=1)
        if not np.all(np.isfinite(norms)) or np.any(norms <= 0):
            raise ValueError("invalid embedding norms")
    q_norm = q_arr / np.linalg.norm(q_arr, axis=1, keepdims=True)
    b_norm = b_arr / np.linalg.norm(b_arr, axis=1, keepdims=True)
    return (q_norm @ b_norm.T).tolist()


def mrr_at_k(ranked_relevance: list[bool], k: int = 5) -> float:
    """MRR@K: 1/rank of first relevant in top-K, 0 if none."""
    for i, rel in enumerate(ranked_relevance[:k], start=1):
        if rel:
            return 1.0 / i
    return 0.0


def recall_at_k(ranked_relevance: list[bool], k: int = 5) -> float:
    """Fraction of judged positives recovered; not an any-positive hit rate."""
    from .evaluation_v2 import recall_at_k as recall
    return recall(ranked_relevance, k)


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
        from .mpnet_scorer import model_identity
        model_hash = model_identity()["fingerprint"]
    except Exception as exc:
        b_scores = None
        b_time = 0.0
        b_status = f"BLOCKED: {type(exc).__name__}: {exc}"
        model_hash = None

    # Build per-task results
    task_results = []
    for ti, task in enumerate(tasks):
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
                    "known_allowed_positive_recall_at_k": None,
                })
                continue

            from .evaluation_v2 import rank_full_pool
            ranked = rank_full_pool(blocks, scores[ti], task, k=5)
            task_results.append({"task_id": task["task_id"], "split": task["split"],
                "question":task["question"], "formulation":task["formulation"],
                "variant":variant_name,"status":"OK", **ranked})

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
            measurable = [r["known_allowed_positive_recall_at_k"] for r in s_results
                          if r["known_allowed_positive_recall_at_k"] is not None]
            summary[key] = {
                "n": len(s_results),
                "mean_known_allowed_positive_recall_at_5": (
                    sum(measurable) / len(measurable) if measurable else None),
                "tasks_with_known_allowed_positive": len(measurable),
                "all_pairs_judged": all(r["fully_judged"] for r in s_results),
                "ranking_scope": "entire_fixed_pool_unjudged_labels_remain_unknown",
            }

    result = {
        "schema_version": 2,
        "lexical_baseline_kind":"diagnostic_overlap_not_production_qualification",
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

    from .evaluation_v2 import save_new_report
    import uuid
    save_new_report(HERE / "review_runs" / f"m2-{uuid.uuid4().hex}.json", result)
    return result


if __name__ == "__main__":
    r = run()
    print(json.dumps(r["summary"], ensure_ascii=False, indent=2))
