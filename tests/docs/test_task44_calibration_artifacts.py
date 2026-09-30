"""Synthetic artifact-validation units, never calibration or model-quality data."""
from copy import deepcopy
import pytest
from experiments.crosslingual_relevance import rescue_calibration as cal


@pytest.fixture
def dataset():
    documents, rows = {}, []
    for split in ("calibration", "holdout"):
        key = split + "/rules.md"
        text = f"{split} relevant statement.\n{split} hard negative statement.\n"
        documents[key] = text
        for language in cal.LANGUAGES:
            for relevant, line in ((True, 1), (False, 2)):
                rows.append({"split": split, "task_id": "unit-"+split, "fact_family": "unit-family-"+split,
                    "language": language, "question": language + " synthetic unit question",
                    "evidence_text": text.splitlines(keepends=True)[line-1],
                    "source": {"project": "unit-"+split, "document_key": key,
                        "identity": "unit-identity-"+split, "document_sha256": cal.text_digest(text),
                        "line_start": line, "line_end": line},
                    "qualification": {"qualified": False, "reason": "insufficient_visible_match"},
                    "capture_trace_sha256": "1"*64,
                    "labels": {"source_allowed": True, "relevant_to_question": relevant,
                        "covered_fact_ids": ["unit-fact"] if relevant else [],
                        "reason": "SYNTHETIC UNIT FIXTURE ONLY", "reviewer_id": "unit-test"}})
    config = {"model_id": "unit/scorer", "model_revision": "1"*40, "capture_git_revision": "2"*40,
        "model_manifest_sha256": "3"*64, "runtime_sha256": "4"*64, "input_contract_sha256": "5"*64,
        "retrieval_profile_sha256": "6"*64, "score_kind": "unit-score",
        "score_direction": "higher_is_better", "max_evaluations": 60, "max_final_windows": 20,
        "max_length": 512, "timeout_seconds": 10, "truncation": "reject",
        "reviewer_id": "unit-only", "reviewed_before_scores": True}
    return rows, documents, config


def make_scores(lock, rows, positive=0.8, negative=0.2):
    return {"config_sha256": cal.digest(lock["config"]), "rows": [
        {"pair_id": r["pair_id"], "input_sha256": r["input_sha256"],
         "status": "ok", "degraded": False,
         "score": positive if r["labels"]["relevant_to_question"] else negative} for r in rows]}


def test_empty_capture_cannot_be_frozen(dataset):
    _, docs, config = dataset
    with pytest.raises(ValueError, match="no new rescue-path"):
        cal.freeze_dataset([], docs, config)


@pytest.mark.parametrize("change", ["seen_project", "seen_task", "veto", "qualified", "wrong_reason",
    "scored", "source_disallowed", "unlabelled", "unreviewed", "noncanonical", "snapshot", "revision"])
def test_invalid_capture_or_review_is_blocked(dataset, change):
    rows, docs, config = dataset
    row = rows[0]
    if change == "seen_project": row["source"]["project"] = "Typer"
    if change == "seen_task": row["task_id"] = "m15-dev-01"
    if change == "veto": row["qualification"]["missing_exact_terms"] = ["/-S"]
    if change == "qualified": row["qualification"]["qualified"] = True
    if change == "wrong_reason": row["qualification"]["reason"] = "unsafe_evidence"
    if change == "scored": row["score"] = 0.9
    if change == "source_disallowed": row["labels"]["source_allowed"] = False
    if change == "unlabelled": row["labels"]["relevant_to_question"] = None
    if change == "unreviewed": config["reviewed_before_scores"] = False
    if change == "noncanonical": row["evidence_text"] = "invented quote"
    if change == "snapshot": row["source"]["document_sha256"] = "0"*64
    if change == "revision": config["model_revision"] = "main"
    with pytest.raises(ValueError): cal.freeze_dataset(rows, docs, config)


def test_fact_family_cannot_cross_splits(dataset):
    for row in dataset[0]: row["fact_family"] = "shared-family"
    with pytest.raises(ValueError, match="leakage"):
        cal.freeze_dataset(*dataset)


def test_missing_language_cannot_hide_in_aggregate(dataset):
    rows, docs, config = dataset
    rows = [r for r in rows if r["language"] != "RU"]
    with pytest.raises(ValueError, match="EN, RU and mixed"):
        cal.freeze_dataset(rows, docs, config)


def test_duplicate_pairs_do_not_inflate_sample_size(dataset):
    dataset[0].append(deepcopy(dataset[0][0]))
    with pytest.raises(ValueError, match="duplicate"):
        cal.freeze_dataset(*dataset)


def test_scoring_input_excludes_labels_and_splits(dataset):
    lock, rows, holdout = cal.freeze_dataset(*dataset)
    public = cal.scoring_inputs(rows)
    assert all(set(r) == {"pair_id", "question", "evidence_text"} for r in public)
    assert lock["calibration_sha256"] != lock["holdout_sha256"]
    assert lock["mpnet_archived_threshold"] == 0.7453


def test_threshold_is_selected_only_from_calibration(dataset):
    lock, rows, holdout = cal.freeze_dataset(*dataset)
    result = cal.calibrate(lock, rows, make_scores(lock, rows))
    assert result["threshold"] == 0.8
    assert result["holdout_evaluated"] is False
    assert result["metrics"]["overall"]["semantic_tasks"] == 1
    for value in result["metrics"]["by_language"].values():
        assert value["precision"] == value["recall"] == 1.0
        assert value["pairs"] == 2 and value["false_admissions"] == 0
    with pytest.raises(ValueError, match="foreign score"):
        cal.calibrate(lock, rows, make_scores(lock, holdout))


def test_overlapping_scores_are_no_go_not_convenient_threshold(dataset):
    lock, rows, holdout = cal.freeze_dataset(*dataset)
    result = cal.calibrate(lock, rows, make_scores(lock, rows, positive=0.5, negative=0.5))
    assert result["status"] == "NO_GO" and result["threshold"] is None
    with pytest.raises(ValueError, match="must remain unopened"):
        cal.evaluate_holdout(lock, holdout, result, make_scores(lock, holdout))


def test_holdout_false_admits_are_reported_per_language_not_erased(dataset):
    lock, rows, holdout = cal.freeze_dataset(*dataset)
    threshold = cal.calibrate(lock, rows, make_scores(lock, rows))
    result = cal.evaluate_holdout(lock, holdout, threshold,
                                  make_scores(lock, holdout, positive=0.9, negative=0.85))
    assert result["zero_false_admits_with_positive"] is False
    assert result["metrics"]["overall"]["false_admissions"] == 3
    assert result["metrics"]["by_language"]["RU"]["precision"] == 0.5
    assert result["product_activation"] is False


@pytest.mark.parametrize("change", ["nonfinite", "degraded", "unbound", "config", "duplicate", "mutate_labels"])
def test_score_failures_and_postfreeze_changes_are_not_quality_results(dataset, change):
    lock, rows, _ = cal.freeze_dataset(*dataset)
    scores = make_scores(lock, rows)
    if change == "nonfinite": scores["rows"][0]["score"] = float("nan")
    if change == "degraded": scores["rows"][0]["degraded"] = True
    if change == "unbound": scores["rows"][0]["input_sha256"] = "0"*64
    if change == "config": scores["config_sha256"] = "0"*64
    if change == "duplicate": scores["rows"].append(deepcopy(scores["rows"][0]))
    if change == "mutate_labels": rows[0]["labels"]["relevant_to_question"] = not rows[0]["labels"]["relevant_to_question"]
    with pytest.raises(ValueError): cal.calibrate(lock, rows, scores)


def test_same_document_bytes_under_different_names_cannot_cross_splits(dataset):
    rows, docs, config = dataset
    docs["holdout/rules.md"] = docs["calibration/rules.md"]
    for row in rows:
        if row["split"] == "holdout":
            raw = docs["holdout/rules.md"]
            row["source"]["document_sha256"] = cal.text_digest(raw)
            row["evidence_text"] = raw.splitlines(keepends=True)[row["source"]["line_start"] - 1]
    with pytest.raises(ValueError, match="leakage"):
        cal.freeze_dataset(rows, docs, config)
