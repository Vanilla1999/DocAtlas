from __future__ import annotations

import sqlite3

from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore


def _doc(content: str, **metadata) -> Document:
    return Document(
        source="docs/guide.md",
        content=content,
        metadata={
            "format": "markdown",
            "chunking_schema": "parent-child-v1",
            "child_target_tokens": 32,
            "child_hard_max_tokens": 64,
            **metadata,
        },
    )


def test_v2_indexes_retrieval_context_but_delivers_verbatim_text(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    source = "# Install\n\nRun the frobnicate command.\n"
    store.add_documents([_doc(source)], recreate=True)

    results = store.query("guide frobnicate", limit=3, budget=200)
    assert results
    assert results[0].text in source
    assert "Document: docs/guide.md" not in results[0].text
    assert results[0].metadata["stable_chunk_id"].startswith("child-")
    embedded = store.list_sections_for_embedding()
    assert embedded[0]["text"].startswith(
        "Document Title: guide\nLocation: docs/guide.md\n"
        "Heading Path: Install"
    )
    assert embedded[0]["display_text"] == source


def test_reindex_local_edit_preserves_unaffected_ids_and_reports_prune_set(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    before = "# Alpha\n\nunchanged\n\n# Beta\n\nold value\n"
    after = "# Alpha\n\nunchanged\n\n# Beta\n\nnew value\n"
    store.add_documents([_doc(before)])
    ids_before = {
        row["display_text"]: row["section_id"] for row in store.list_sections_for_embedding()
    }
    store.add_documents([_doc(after)])
    ids_after = {
        row["display_text"]: row["section_id"] for row in store.list_sections_for_embedding()
    }

    assert ids_before["# Alpha\n\nunchanged\n\n"] == ids_after["# Alpha\n\nunchanged\n\n"]
    assert ids_before["# Beta\n\nold value\n"] not in set(ids_after.values())
    assert store.index_health()["ok"] is True


def test_metadata_only_edit_preserves_child_identity_but_refreshes_context(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    content = "# Configure\n\nCall Client.connect().\n"
    store.add_documents([_doc(content, title="Old title", authority="community")])
    before = store.list_sections_for_embedding()[0]

    store.add_documents([_doc(content, title="New title", authority="official")])
    after = store.list_sections_for_embedding()[0]

    assert after["stable_chunk_id"] == before["stable_chunk_id"]
    assert after["vector_id"] == before["vector_id"]
    assert after["section_id"] == before["section_id"]
    assert after["content_hash"] != before["content_hash"]
    assert after["context_content_hash"] != before["context_content_hash"]
    assert after["text"].startswith("Document Title: New title")


def test_context_generation_persists_provenance_and_filter_columns(tmp_path):
    db = tmp_path / "index.db"
    store = SQLiteStore(db)
    store.add_documents([_doc(
        "# Configure\n\nUse CONFIG_KEY.\n",
        title="SDK guide",
        library_id="example-sdk",
        resolved_version="2.4.1",
        version_family="2.x",
        project_identity="acme/project",
        project_doc_path="docs/guide.md",
        module_id="client",
        doc_scope="runtime",
        source_class="project_file",
        authority="official",
        docs_snapshot_exact=True,
    )])

    info = store.generation_info()
    assert info is not None
    assert info["context_schema_version"] == "deterministic-context-v2"
    assert info["context_config_hash"]
    assert info["retrieval_config_hash"]
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM retrieval_children").fetchone()
        assert row is not None
        assert row["library_id"] == "example-sdk"
        assert row["resolved_version"] == "2.4.1"
        assert row["project_path"] == "docs/guide.md"
        assert row["authority"] == "official"
        assert row["docs_snapshot_exact"] == 1
        assert "/tmp/" not in row["context_prefix"]


def test_expansion_never_crosses_parent_boundary(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    source = (
        "# Alpha\n\nneedle alpha one.\n\nalpha two.\n\nalpha three.\n\n"
        "# Beta\n\nforbidden beta.\n"
    )
    store.add_documents([_doc(source, child_target_tokens=10, child_hard_max_tokens=20)])

    results = store.query("needle", limit=10, budget=500, expand="page")
    assert results
    assert all("forbidden beta" not in item.text for item in results)
    assert len(results) <= 10


def test_additive_migration_keeps_v1_rows_readable(tmp_path):
    db = tmp_path / "index.db"
    store = SQLiteStore(db)
    store.add_documents([Document(source="legacy.md", content="# Legacy\nold text")])
    store.add_documents([_doc("# Current\nnew text")])

    assert store.query("old", limit=2, budget=100)[0].source == "legacy.md"
    health = store.index_health()
    assert health["schema_versions"] == {"parent-child-v1": 1, "sqlite-sections-v1": 1}
    assert health["issues"]["mixed_schema_versions"] is True
    assert health["ok"] is False

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM parent_sections").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM retrieval_parents").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM generation_sources").fetchone()[0] == 1


def test_legacy_promoted_filter_preserves_multi_term_fts_semantics(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    store.add_documents(
        [
            Document(
                source="both.md",
                content="alpha beta exact sentinel",
                metadata={"library_id": "sdk"},
            ),
            Document(
                source="alpha.md",
                content="alpha only sentinel",
                metadata={"library_id": "sdk"},
            ),
        ]
    )

    results = store.query(
        "alpha beta", limit=10, budget=500, filters={"library_id": "sdk"}
    )

    assert [result.source for result in results] == ["both.md"]


def test_failed_v2_rebuild_rolls_back_to_previous_source_rows(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    store.add_documents([_doc("# Stable\n\nold searchable fact\n")])
    old_ids = store.section_ids_for_source("docs/guide.md")

    broken = _doc(
        "# Broken\n\nreplacement\n",
        child_target_tokens=600,
        child_hard_max_tokens=500,
    )
    try:
        store.add_documents([broken])
    except ValueError as exc:
        assert "hard_max_tokens" in str(exc)
    else:
        raise AssertionError("invalid rebuild must fail")

    assert store.section_ids_for_source("docs/guide.md") == old_ids
    assert store.query("searchable", limit=2, budget=100)[0].text.endswith("old searchable fact\n")


def test_failed_v2_rebuild_does_not_publish_extracted_snapshot(tmp_path, monkeypatch):
    extracted = tmp_path / "extracted"
    store = SQLiteStore(tmp_path / "index.db", extracted)
    store.add_documents([_doc("# Stable\n\nold extracted fact\n")])
    markdown_path = next(extracted.glob("*.md"))
    json_path = next(extracted.glob("*.json"))
    markdown_before = markdown_path.read_bytes()
    json_before = json_path.read_bytes()

    def fail_validation(*args, **kwargs):
        raise ValueError("injected generation failure")

    monkeypatch.setattr(store, "_validate_generation", fail_validation)
    try:
        store.add_documents([_doc("# Replacement\n\nnew extracted fact\n")])
    except ValueError as exc:
        assert "injected generation failure" in str(exc)
    else:
        raise AssertionError("injected rebuild failure must propagate")

    assert markdown_path.read_bytes() == markdown_before
    assert json_path.read_bytes() == json_before
    assert not list(extracted.glob("*.tmp"))


def test_delete_source_prunes_parent_rows_and_allows_same_source_reingest(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    original = _doc("# Replaceable\n\nold\n")
    store.add_documents([original])

    assert store.delete_source(original.source) is True
    assert store.collection_stats()["parent_sections_count"] == 0
    store.add_documents([_doc("# Replaceable\n\nnew\n")])

    assert store.query("new", limit=1, budget=100)[0].text.endswith("new\n")
    assert store.index_health()["ok"] is True


def test_unactivated_candidate_cannot_mutate_active_source_snapshot(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    store.add_documents([_doc("# Stable\n\nold searchable fact\n")])
    active_before = store.active_generation_id()

    candidate = store.add_documents(
        [_doc("# Stable\n\nreplacement fact\n")],
        activate_generation=False,
    )

    assert candidate.generation_id != active_before
    assert store.active_generation_id() == active_before
    assert store.query("searchable", limit=1, budget=100)[0].text.endswith(
        "old searchable fact\n"
    )
    assert store.index_health()["ok"] is True


def test_delete_source_activates_an_immutable_generation_without_it(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    first = _doc("# Remove\n\nremove sentinel\n")
    second = Document(
        source="docs/keep.md",
        content="# Keep\n\nkeep sentinel\n",
        metadata={**first.metadata},
    )
    store.add_documents([first, second])
    active_before = store.active_generation_id()

    assert store.delete_source(first.source) is True
    assert store.active_generation_id() != active_before
    assert all(
        row.source != first.source
        for row in store.query("remove sentinel", limit=3, budget=100)
    )
    assert store.query("keep sentinel", limit=1, budget=100)[0].source == second.source
    assert store.index_health()["ok"] is True


def test_chunk_config_change_rebuilds_every_v2_source_in_one_generation(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    first = _doc("# First\n\nfirst sentinel\n")
    second = Document(
        source="docs/second.md",
        content="# Second\n\nsecond sentinel\n",
        metadata={**first.metadata},
    )
    store.add_documents([first, second])

    changed = _doc(
        "# First\n\nfirst sentinel updated\n",
        child_target_tokens=40,
        child_hard_max_tokens=80,
    )
    store.add_documents([changed])
    rows = store.list_sections_for_embedding()

    assert {row["source"] for row in rows} == {first.source, second.source}
    assert len({row["chunk_config_hash"] for row in rows}) == 1
    assert store.query("second sentinel", limit=1, budget=100)[0].source == second.source


def test_stable_ids_do_not_depend_on_machine_local_project_root(tmp_path):
    content = "# Portable\n\nportable identity sentinel\n"
    first = SQLiteStore(tmp_path / "first.db")
    second = SQLiteStore(tmp_path / "second.db")
    first.add_documents([_doc(content, project_path="/home/alice/repository")])
    second.add_documents([_doc(content, project_path="D:/work/repository")])

    assert {
        row["stable_chunk_id"] for row in first.list_sections_for_embedding()
    } == {
        row["stable_chunk_id"] for row in second.list_sections_for_embedding()
    }


def test_legacy_recreate_and_delete_all_cannot_leave_stale_active_generation(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    store.add_documents([_doc("# Old\n\nstale v2 sentinel\n")])

    store.add_documents(
        [Document(source="replacement.txt", content="fresh legacy sentinel")],
        recreate=True,
    )
    assert store.active_generation_id() is None
    assert all(
        row.source != "docs/guide.md"
        for row in store.query("stale sentinel", limit=3, budget=100)
    )

    store.add_documents([_doc("# Again\n\nactive sentinel\n")])
    assert store.active_generation_id() is not None
    assert store.delete_all() is True
    assert store.active_generation_id() is None
    assert not store.query("active sentinel", limit=3, budget=100)


def test_superseded_generation_retention_is_bounded_and_cannot_delete_active(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    for version in range(4):
        store.add_documents([_doc(f"# Version\n\nvalue {version}\n")])
    active = store.active_generation_id()
    candidates = store.superseded_generation_candidates(retain=1)

    assert len(candidates) == 2
    assert all(row["generation_id"] != active for row in candidates)
    assert store.delete_superseded_generations(
        [active, *(row["generation_id"] for row in candidates)]
    ) == 2
    assert store.active_generation_id() == active
    assert store.index_health()["ok"] is True


def test_delete_rebuilds_pre_contextual_active_generation(tmp_path):
    store = SQLiteStore(tmp_path / "index.db")
    first = _doc("# Remove\n\nremove legacy sentinel\n")
    second = Document(
        source="docs/keep.md",
        content="# Keep\n\nkeep legacy sentinel\n",
        metadata={**first.metadata},
    )
    store.add_documents([first, second])
    active = store.active_generation_id()
    with store._connect() as conn:
        conn.execute(
            """UPDATE index_generations
               SET context_schema_version = '', context_config_hash = '',
                   retrieval_config_hash = ''
               WHERE generation_id = ?""",
            (active,),
        )

    assert store.delete_source(first.source) is True
    info = store.generation_info()
    assert info and info["context_config_hash"] and info["retrieval_config_hash"]
    assert store.query("keep legacy sentinel", limit=1, budget=100)[0].source == second.source
