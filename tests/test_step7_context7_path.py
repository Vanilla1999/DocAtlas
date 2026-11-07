"""Step-7: body pool pruning by default; dense relevance and the Otsu cut stay opt-in."""
from __future__ import annotations

import hashlib

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


def test_whole_pool_guard_checks_references_then_bytes_then_the_real_delivery(monkeypatch):
    built = []

    def packet(payload, snapshot, retrieval, rows, *, selection):
        built.append((len(rows), selection))
        return {"sources": rows}, {}

    monkeypatch.setattr(selection, "_selected_packet", packet)
    monkeypatch.setattr(selection, "_delivery_fits", lambda packet, limit: len(packet["sources"]) <= 2)
    rows = [{"snippet": "a", "source_uri": "u1"}, {"snippet": "b", "source_uri": "u2"}]
    # Too many distinct references or too many bytes: no packet is even built.
    assert not selection._whole_pool_fits({}, {}, {}, rows, 100, 1, 1)
    assert not selection._whole_pool_fits({}, {}, {}, [{"snippet": "x" * 401}], 100, 1, None)
    assert built == []
    # Otherwise the whole unselected pool goes through the delivery check.
    assert selection._whole_pool_fits({}, {}, {}, rows, 100, 1, 2)
    assert built[-1][0] == 2
    assert built[-1][1]["candidate_rows"] == 2 and built[-1][1]["budget_limited"] is False
    assert not selection._whole_pool_fits({}, {}, {}, rows * 2, 100, 1, None)


class _Stop(Exception):
    pass


@pytest.mark.parametrize("fits", [True, False])
def test_pool_pruning_runs_only_when_the_whole_pool_misses_the_budget(monkeypatch, fits):
    # Pruning settles competition for the delivery budget; a pool that fits
    # whole is delivered whole even under an explicit pruning mode.
    monkeypatch.setenv("DOCATLAS_EXPERIMENT_POOL_PRUNE", "body")
    monkeypatch.setattr(selection, "experimental_context_max_tokens", lambda: 4000)
    monkeypatch.setattr(selection, "authoritative_queries", lambda plan: {"q": {"text": "q"}})
    monkeypatch.setattr(selection, "_whole_pool_fits", lambda *args: fits)
    pruned = []

    def prune(payload, snapshot, queries, *, default_mode):
        pruned.append(default_mode)
        return payload, {"mode": default_mode}

    def stop(*args):
        raise _Stop

    monkeypatch.setattr(selection, "prune_checked_pool", prune)
    monkeypatch.setattr(selection, "_SelectionObservation", stop)
    # The selector receives checked, identity-bound sources. Continuation now
    # fingerprints that binding before this historical pruning probe stops it.
    row = {"evidence_id": "ev-pruning-fixture", "path_or_url": "guide.md",
           "snippet": "a", "content_sha256": hashlib.sha256(b"a").hexdigest(),
           "line_start": 1, "line_end": 1, "scope": "project",
           "project_identity": "local:pruning-fixture", "version_binding": "unversioned"}
    snapshot = {row["evidence_id"]: {"projected_source": row, "source": {
        "project_identity": row["project_identity"], "source_class": "project_file",
        "doc_scope": "project", "content": "a",
        "project_doc_content_hash": "sha256:" + row["content_sha256"],
    }}}
    with pytest.raises(_Stop):
        selection.select_joint_context({"sources": [row]}, snapshot, {})
    assert pruned == ([] if fits else ["body"])
