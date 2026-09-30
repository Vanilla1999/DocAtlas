"""Fail-closed artifact checks for a NEW rescue-path calibration experiment.

No corpus, labels, scores or claims of independence are generated here. Input
records must come from a real qualification trace and separate pre-score human
review. Structural validation cannot certify honest provenance by itself.
Holdout rows are stored separately; threshold selection never receives them.
MPNet's archived threshold and the v3 protocol are not modified.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

SEEN_PROJECTS = frozenset({"typer", "httpx", "ruff", "starlette", "pydantic"})
LANGUAGES = ("EN", "RU", "mixed")
VETO_FIELDS = ("missing_exact_terms", "missing_parent_exact_terms", "missing_bound_subjects")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _hash(value: Any, length: int, field: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value):
        raise ValueError(f"missing/invalid {field}")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {field}")
    return value


def input_digest(row: dict) -> str:
    return digest({"question": row["question"], "evidence_text": row["evidence_text"],
                   "source": row["source"]})


def freeze_dataset(records: list[dict], documents: Mapping[str, str], config: dict) -> tuple[dict, list, list]:
    """Validate genuine captures and pre-score labels; return lock + separated splits.

    A 'reviewed_before_scores' flag is an attestation to audit, not cryptographic
    proof that a reviewer did not inspect scores. Preserve raw capture artifacts.
    """
    if not records:
        raise ValueError("no new rescue-path captures; calibration is BLOCKED")
    for field in ("model_revision", "capture_git_revision"):
        _hash(config.get(field), 40, field)
    for field in ("model_manifest_sha256", "runtime_sha256", "input_contract_sha256",
                  "retrieval_profile_sha256"):
        _hash(config.get(field), 64, field)
    for field in ("model_id", "score_kind", "reviewer_id"):
        _text(config.get(field), field)
    if config.get("score_direction") != "higher_is_better":
        raise ValueError("score direction must be frozen")
    for field in ("max_evaluations", "max_final_windows", "max_length"):
        if type(config.get(field)) is not int or config[field] < 1:
            raise ValueError(f"invalid {field}")
    timeout = config.get("timeout_seconds")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("invalid timeout_seconds")
    if config.get("truncation") not in ("reject", "record_exact_scored_span"):
        raise ValueError("truncation contract must be explicit")
    if config.get("reviewed_before_scores") is not True:
        raise ValueError("independent pre-score label review is required")
    split_groups, doc_splits, content_splits, task_splits, languages = {}, {}, {}, {}, defaultdict(set)
    unique, splits = set(), {"calibration": [], "holdout": []}
    for raw_row in records:
        row = deepcopy(raw_row)
        if any(field in row for field in ("score", "scores", "logit", "rank_by_model")):
            raise ValueError("scores cannot enter a pre-score dataset freeze")
        split = row.get("split")
        if split not in splits or row.get("language") not in LANGUAGES:
            raise ValueError("invalid split/language")
        task = _text(row.get("task_id"), "task_id")
        family = _text(row.get("fact_family"), "fact_family")
        if task.casefold().startswith(("m15-", "typer")):
            raise ValueError("reviewed tasks cannot be relabelled as independent")
        source = row.get("source", {})
        project = _text(source.get("project"), "source.project").casefold()
        if project in SEEN_PROJECTS:
            raise ValueError("viewed Typer/M1.5 projects cannot supply this new dataset")
        doc_key = _text(source.get("document_key"), "source.document_key")
        body = documents.get(doc_key)
        if not isinstance(body, str):
            raise ValueError("canonical document is missing")
        if source.get("document_sha256") != text_digest(body):
            raise ValueError("canonical document hash mismatch")
        _text(source.get("identity"), "source.identity")
        start, end = source.get("line_start"), source.get("line_end")
        lines = body.splitlines(keepends=True)
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            raise ValueError("invalid scored source range")
        text = _text(row.get("evidence_text"), "evidence_text")
        _text(row.get("question"), "question")
        if text not in "".join(lines[start-1:end]):
            raise ValueError("scored bytes are not in the canonical range")
        qualification = row.get("qualification", {})
        if (qualification.get("qualified") is not False
                or qualification.get("reason") != "insufficient_visible_match"
                or any(qualification.get(field) for field in VETO_FIELDS)):
            raise ValueError("candidate is not an eligible insufficient_visible_match capture")
        _hash(row.get("capture_trace_sha256"), 64, "capture_trace_sha256")
        labels = row.get("labels", {})
        if labels.get("source_allowed") is not True or type(labels.get("relevant_to_question")) is not bool:
            raise ValueError("source-allowed calibration requires independent relevance labels")
        _text(labels.get("reason"), "label reason")
        _text(labels.get("reviewer_id"), "label reviewer")
        if not isinstance(labels.get("covered_fact_ids"), list) or not all(
            isinstance(f, str) and f for f in labels["covered_fact_ids"]):
            raise ValueError("covered_fact_ids must be explicit, including an empty list")
        for key, seen in ((family, split_groups), (doc_key, doc_splits),
                          (source["document_sha256"], content_splits), (task, task_splits)):
            if key in seen and seen[key] != split:
                raise ValueError("fact/translation/document leakage between splits")
            seen[key] = split
        # This new experiment uses document-disjoint splits, a deliberately
        # stricter contract than historical M1.5; no old manifest is rewritten.
        languages[task].add(row["language"])
        pair_id = input_digest(row)
        if pair_id in unique:
            raise ValueError("duplicate captured question/source/text pair")
        unique.add(pair_id)
        row["pair_id"] = pair_id
        row["input_sha256"] = pair_id
        splits[split].append(row)
    if any(value != set(LANGUAGES) for value in languages.values()):
        raise ValueError("each semantic task needs EN, RU and mixed formulations in one split")
    for split, rows in splits.items():
        if not rows:
            raise ValueError("separate calibration and untouched holdout are required")
        for lang in LANGUAGES:
            labels = {r["labels"]["relevant_to_question"] for r in rows if r["language"] == lang}
            if labels != {True, False}:
                raise ValueError(f"{split}/{lang} needs positive and hard-negative captures")
        rows.sort(key=lambda row: row["pair_id"])
    lock = {"schema_version": 1, "config": deepcopy(config),
        "criterion": "maximize_recall_at_observed_thresholds_with_zero_false_admissions;stricter_tie;nonzero_positive",
        "mpnet_archived_threshold": 0.7453,
        "calibration_sha256": digest(splits["calibration"]),
        "holdout_sha256": digest(splits["holdout"]),
        "observation_unit": "semantic_fact_family_not_translation",
        "unseen_provenance": "reviewer_attested_requires_raw_capture_audit"}
    lock["fingerprint"] = digest(lock)
    return lock, splits["calibration"], splits["holdout"]


def _verify_seal(value: dict) -> None:
    if value.get("fingerprint") != digest({k: v for k, v in value.items() if k != "fingerprint"}):
        raise ValueError("artifact fingerprint mismatch")


def scoring_inputs(rows: list[dict]) -> list[dict]:
    """Only original question and scored text enter inference; labels stay out."""
    return [{"pair_id": r["pair_id"], "question": r["question"], "evidence_text": r["evidence_text"]}
            for r in rows]


def _scored(lock: dict, rows: list[dict], scores: dict, split: str) -> list[dict]:
    _verify_seal(lock)
    if digest(rows) != lock[f"{split}_sha256"]:
        raise ValueError("frozen dataset has changed")
    if scores.get("config_sha256") != digest(lock["config"]):
        raise ValueError("scorer/runtime/budget/input contract changed")
    raw = scores.get("rows", [])
    index = {s.get("pair_id"): s for s in raw}
    if len(index) != len(raw) or set(index) != {r["pair_id"] for r in rows}:
        raise ValueError("missing/duplicate/foreign score pair (including holdout leakage)")
    result = []
    for row in rows:
        score_row = index[row["pair_id"]]
        if (score_row.get("status") != "ok" or score_row.get("degraded") is not False
                or score_row.get("input_sha256") != row["input_sha256"]):
            raise ValueError("degraded or unbound scoring is BLOCKED, not a quality result")
        score = score_row.get("score")
        if type(score) not in (int, float) or not math.isfinite(score):
            raise ValueError("nonfinite/invalid score")
        result.append({**row, "score": score})
    return result


def metrics(rows: list[dict], threshold: float) -> dict:
    relevant = lambda r: r["labels"]["relevant_to_question"]
    tp = sum(relevant(r) and r["score"] >= threshold for r in rows)
    fp = sum(not relevant(r) and r["score"] >= threshold for r in rows)
    positives = sum(relevant(r) for r in rows)
    negatives = len(rows) - positives
    return {"pairs": len(rows), "semantic_tasks": len({r["fact_family"] for r in rows}),
        "true_positive": tp, "false_admissions": fp, "positives": positives, "negatives": negatives,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / positives if positives else None,
        "false_positive_rate": fp / negatives if negatives else None}


def _all_metrics(rows: list[dict], threshold: float) -> dict:
    return {"overall": metrics(rows, threshold), "by_language": {
        lang: metrics([r for r in rows if r["language"] == lang], threshold) for lang in LANGUAGES}}


def calibrate(lock: dict, calibration: list[dict], scores: dict) -> dict:
    rows = _scored(lock, calibration, scores, "calibration")
    boundaries = sorted({r["score"] for r in rows})
    eligible = [(metrics(rows, t)["true_positive"], t) for t in boundaries
                if metrics(rows, t)["false_admissions"] == 0 and metrics(rows, t)["true_positive"] > 0]
    threshold = max(eligible)[1] if eligible else None
    result = {"schema_version": 1, "lock_fingerprint": lock["fingerprint"],
        "calibration_scores_sha256": digest(scores), "threshold": threshold,
        "status": "THRESHOLD_FROZEN_NOT_VALIDATED" if threshold is not None else "NO_GO",
        "metrics": _all_metrics(rows, threshold) if threshold is not None else None,
        "holdout_evaluated": False, "product_activation": False}
    result["fingerprint"] = digest(result)
    return result


def evaluate_holdout(lock: dict, holdout: list[dict], calibrated: dict, scores: dict) -> dict:
    _verify_seal(calibrated)
    if calibrated.get("lock_fingerprint") != lock.get("fingerprint"):
        raise ValueError("threshold belongs to another frozen experiment")
    threshold = calibrated.get("threshold")
    if calibrated.get("status") != "THRESHOLD_FROZEN_NOT_VALIDATED" or threshold is None:
        raise ValueError("calibration is NO_GO; holdout must remain unopened")
    rows = _scored(lock, holdout, scores, "holdout")
    measured = _all_metrics(rows, threshold)
    return {"status": "MEASURED_NOT_PRODUCT_ACCEPTANCE", "threshold": threshold,
        "threshold_fingerprint": calibrated["fingerprint"], "holdout_scores_sha256": digest(scores),
        "metrics": measured, "product_activation": False,
        "zero_false_admits_with_positive": measured["overall"]["false_admissions"] == 0
             and measured["overall"]["true_positive"] > 0}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_new(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    freeze = sub.add_parser("freeze")
    for field in ("records", "documents", "config", "output_dir"):
        freeze.add_argument("--" + field.replace("_", "-"), type=Path, required=True)
    for action in ("calibrate", "holdout"):
        p = sub.add_parser(action)
        for field in ("lock", "rows", "scores", "output"):
            p.add_argument("--" + field, type=Path, required=True)
        if action == "holdout": p.add_argument("--threshold", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "freeze":
            lock, cal, hold = freeze_dataset(_read(args.records), _read(args.documents), _read(args.config))
            args.output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
            for name, value in (("lock.json", lock), ("calibration.json", cal), ("PRIVATE_holdout.json", hold)):
                path = args.output_dir / name
                _write_new(path, value)
                path.chmod(0o600)
        else:
            lock, rows, scores = _read(args.lock), _read(args.rows), _read(args.scores)
            result = (calibrate(lock, rows, scores) if args.action == "calibrate" else
                      evaluate_holdout(lock, rows, _read(args.threshold), scores))
            _write_new(args.output, result)
        print(json.dumps({"status": "ARTIFACT_WRITTEN_NOT_PRODUCT_ACCEPTANCE"}))
        return 0
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
