from __future__ import annotations

from docmancer.retrieval.fusion import reciprocal_rank_fusion, weighted_rrf


def _hit(i):
    return {"id": i}


def test_rrf_combines_ranks_across_sources():
    candidates = {
        "lexical": [_hit(1), _hit(2), _hit(3)],
        "dense": [_hit(2), _hit(4)],
    }
    ranked = reciprocal_rank_fusion(candidates, k_rrf=10)
    ids = [hid for hid, _, _ in ranked]
    # Doc 2 appears in both sources at decent ranks; it should rank above docs
    # appearing in only one list.
    assert ids[0] == 2
    assert set(ids) == {1, 2, 3, 4}


def test_weighted_rrf_respects_weights():
    candidates = {
        "lexical": [_hit(1), _hit(2)],
        "dense": [_hit(2), _hit(1)],
    }
    # Heavy dense weight should pull doc 2 to the top despite the lexical tie.
    ranked = weighted_rrf(candidates, weights={"lexical": 0.1, "dense": 5.0}, k_rrf=10)
    assert ranked[0][0] == 2


def test_contributions_track_ranks():
    candidates = {
        "lexical": [_hit(7)],
        "dense": [_hit(8), _hit(7)],
    }
    ranked = reciprocal_rank_fusion(candidates, k_rrf=10)
    contrib_by_id = {hid: contrib for hid, _, contrib in ranked}
    assert contrib_by_id[7] == {"lexical": 1, "dense": 2}
    assert contrib_by_id[8] == {"dense": 1}
