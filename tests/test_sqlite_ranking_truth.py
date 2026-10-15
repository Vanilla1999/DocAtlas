from __future__ import annotations

from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs.domain.evidence_qualification import qualify_evidence


def _store(tmp_path, documents: list[Document], name: str = "ranking.db") -> SQLiteStore:
    store = SQLiteStore(tmp_path / name, tmp_path / f"{name}.extracted")
    store.add_documents(documents, recreate=True)
    return store


def _doc(source: str, title: str, body: str, *, project_identity: str | None = None) -> Document:
    return Document(
        source=source,
        content=f"# {title}\n\n{body}",
        metadata={
            "title": title,
            "authority": "canonical",
            "version": "2.0",
            "format": "markdown",
            "chunking_schema": "parent-child-v1",
            "child_target_tokens": 2_000,
            "child_hard_max_tokens": 3_000,
            **({"project_identity": project_identity} if project_identity else {}),
        },
    )


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

    long_trace = next(
        result.metadata["ranking"]
        for result in results
        if result.source == "docs/long.md"
    )
    assert long_trace["feature_contributions"].get("long_section_penalty", 0) <= 0


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










def test_exact_filename_qualification_uses_the_same_corpus_as_fts(tmp_path):
    requested = _doc(
        "docatlas.project-docs.yaml",
        "Project documentation catalog",
        "Registered project documentation entries.",
    )
    similar = _doc(
        "docatlas.docs.yaml",
        "External documentation catalog",
        "Registered external documentation entries.",
    )
    store = _store(tmp_path, [similar, requested])

    results = store.query("docatlas.project-docs.yaml", limit=2, budget=2_000)

    assert results
    assert results[0].source == "docatlas.project-docs.yaml"
    assert results[0].metadata["lexical_match"]["exact_terms"] == [
        "docatlas.project-docs.yaml",
    ]
    assert "qualified" not in results[0].metadata["lexical_match"]
    assert results[0].metadata["lexical_match"]["missing_exact_terms"] == []
    assert all(
        result.metadata["lexical_match"]["missing_exact_terms"]
        for result in results
        if result.source == "docatlas.docs.yaml"
    )
