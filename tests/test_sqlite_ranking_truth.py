from __future__ import annotations

from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore


def _store(tmp_path, documents: list[Document], name: str = "ranking.db") -> SQLiteStore:
    store = SQLiteStore(tmp_path / name, tmp_path / f"{name}.extracted")
    store.add_documents(documents, recreate=True)
    return store


def _doc(source: str, title: str, body: str) -> Document:
    return Document(
        source=source,
        content=f"# {title}\n\n{body}",
        metadata={"title": title, "authority": "canonical", "version": "2.0"},
    )


def test_explicit_utility_rewards_title_matches_and_penalizes_legal_noise(tmp_path):
    legal_repetition = " ".join(["configure widget cache mode"] * 80)
    store = _store(
        tmp_path,
        [
            _doc(
                "docs/configuration.md",
                "Configure widget cache mode",
                "configure widget cache mode with cache_mode = bounded",
            ),
            _doc(
                "docs/legal.md",
                "Terms and Conditions for widget cache mode",
                legal_repetition,
            ),
        ],
    )

    results = store.query("configure widget cache mode", limit=2, budget=5_000)

    assert [result.source for result in results] == [
        "docs/configuration.md",
        "docs/legal.md",
    ]
    config_trace = results[0].metadata["ranking"]
    legal_trace = results[1].metadata["ranking"]
    assert config_trace["score_direction"] == "higher_is_better"
    assert config_trace["feature_contributions"]["title_term_boost"] > 0
    assert config_trace["feature_contributions"]["task_action_title_boost"] > 0
    assert legal_trace["feature_contributions"]["boilerplate_title_penalty"] < 0
    assert legal_trace["final_utility"] < config_trace["final_utility"]


def test_long_section_penalty_is_negative_and_does_not_reward_length(tmp_path):
    store = _store(
        tmp_path,
        [
            _doc("docs/focused.md", "Widget retry budget", "widget retry budget is three"),
            _doc(
                "docs/long.md",
                "Widget retry budget appendix",
                " ".join(["widget retry budget generic appendix"] * 900),
            ),
        ],
    )

    results = store.query("widget retry budget", limit=2, budget=20_000)

    assert results[0].source == "docs/focused.md"
    long_trace = next(
        result.metadata["ranking"]
        for result in results
        if result.source == "docs/long.md"
    )
    assert long_trace["feature_contributions"]["long_section_penalty"] < 0


def test_equal_feature_candidates_use_stable_identity_not_insertion_order(tmp_path):
    first = _doc("docs/a.md", "Configure widget", "alpha one configure widget")
    second = _doc("docs/b.md", "Configure widget", "bravo two configure widget")
    forward = _store(tmp_path, [first, second], "forward.db")
    reverse = _store(tmp_path, [second, first], "reverse.db")

    forward_results = forward.query("configure widget", limit=2, budget=2_000)
    reverse_results = reverse.query("configure widget", limit=2, budget=2_000)

    assert [item.source for item in forward_results] == [
        item.source for item in reverse_results
    ]
    assert [item.metadata["ranking"]["stable_id"] for item in forward_results] == [
        item.metadata["ranking"]["stable_id"] for item in reverse_results
    ]


def test_ranking_trace_exposes_named_components_without_document_text(tmp_path):
    store = _store(
        tmp_path,
        [_doc("docs/api.md", "WidgetClient fetch_record", "WidgetClient fetch_record timeout")],
    )

    result = store.query("WidgetClient fetch_record", limit=1, budget=1_000)[0]
    trace = result.metadata["ranking"]

    assert trace["raw_component_ranks"].keys() == {"fts5_bm25_cost"}
    assert isinstance(trace["raw_rank"], int)
    assert isinstance(trace["final_rank"], int)
    assert "text" not in trace
    assert "content" not in trace
