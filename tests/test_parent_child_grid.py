from __future__ import annotations

from eval.parent_child_index_grid import GRID, run_grid


def test_task40_grid_is_provider_free_and_preserves_task39_gates(tmp_path):
    report = run_grid(tmp_path / "grid.json")

    assert report["provider_free"] is True
    assert [row["target_tokens"] for row in report["variants"]] == list(GRID)
    assert all(row["quality_gate"]["status"] == "PASS" for row in report["variants"])
    assert all(row["incremental"]["unchanged_reindex_upserts"] == 0 for row in report["variants"])
    assert all(row["chunk_stats"]["visible_overlap_duplicate_rate"] == 0 for row in report["variants"])
    assert all(row["stress_corpus"]["quality_pass"] for row in report["variants"])
    assert all(
        row["stress_corpus"]["selected_evidence_tokens_median"]
        < report["stress_baseline"]["selected_evidence_tokens_median"]
        for row in report["variants"]
    )
    assert report["selected_target_tokens"] in GRID
    selected = next(
        row for row in report["variants"]
        if row["target_tokens"] == report["selected_target_tokens"]
    )
    assert selected["stress_corpus"]["selected_evidence_tokens_mean"] == min(
        row["stress_corpus"]["selected_evidence_tokens_mean"] for row in report["variants"]
    )
