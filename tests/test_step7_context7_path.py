"""Step-7: body pool pruning by default; dense relevance and the Otsu cut stay opt-in."""
from __future__ import annotations

import pytest

from docmancer.docs.application import experimental_dense_relevance as dense
from docmancer.docs.application import experimental_selection_modes as modes
from docmancer.docs.application import joint_context_selection as selection


def test_relevance_cut_flag_is_opt_in(monkeypatch):
    name = "DOCATLAS_EXPERIMENT_JOINT_CUT"
    monkeypatch.delenv(name, raising=False)
    assert selection._EXPERIMENT_CHOICES[name] == ("off", "otsu_mean", "otsu_union")
    assert selection._experiment(name) == "off"


class _Runtime:
    path = "/fake-e5"
    weights_sha256 = "f" * 64


def _fake_model(monkeypatch, vectors):
    monkeypatch.setattr(dense, "_load", lambda path: _Runtime())
    monkeypatch.setattr(dense, "_VECTORS", {})

    def embed(runtime, texts, receipt):
        receipt["model_forwards"] += 1
        return [vectors[text] for text in texts]

    monkeypatch.setattr(dense, "_embed", embed)


def test_dense_scores_use_e5_prefixes_and_min_max_per_query(monkeypatch, tmp_path):
    _fake_model(monkeypatch, {
        "passage: a": [1.0, 0.0], "passage: b": [0.6, 0.8], "passage: c": [0.0, 1.0],
        "query: q": [1.0, 0.0], "query: r": [0.0, 1.0],
    })
    monkeypatch.setenv("DOCATLAS_EXPERIMENT_DENSE_CACHE", str(tmp_path / "cache"))
    rows = [{"snippet": "a"}, {"snippet": "b"}, {"snippet": "c"}]
    queries = {"q": {"text": "q"}, "r": {"text": "r"}}
    scores, receipt = dense.score_joint_dense(queries, rows, str(tmp_path))
    assert scores["q"] == pytest.approx([1.0, 0.6, 0.0])
    assert scores["r"] == pytest.approx([0.0, 0.8, 1.0])
    assert receipt["rows_embedded"] == 3 and receipt["rows_from_cache"] == 0
    # Row vectors depend only on row text: a fresh process reads them back
    # from the cache that plays the index role and embeds only the queries.
    monkeypatch.setattr(dense, "_VECTORS", {})
    again, receipt = dense.score_joint_dense({"q": {"text": "q"}}, rows, str(tmp_path))
    assert again["q"] == pytest.approx(scores["q"])
    assert receipt["rows_from_cache"] == 3 and receipt["rows_embedded"] == 0


def test_equal_dense_scores_all_count_as_the_best_match(monkeypatch, tmp_path):
    _fake_model(monkeypatch, {"passage: a": [1.0, 0.0], "passage: b": [1.0, 0.0], "query: q": [0.0, 1.0]})
    monkeypatch.delenv("DOCATLAS_EXPERIMENT_DENSE_CACHE", raising=False)
    scores, _ = dense.score_joint_dense({"q": {"text": "q"}}, [{"snippet": "a"}, {"snippet": "b"}],
                                        str(tmp_path))
    assert scores["q"] == [1.0, 1.0]


def test_dense_requires_an_absolute_model_directory():
    with pytest.raises(modes.JointSemanticRelevanceError, match="DOCATLAS_EXPERIMENT_DENSE_PATH"):
        dense.score_joint_dense({"q": {"text": "q"}}, [{"snippet": "a"}], "relative/model")
