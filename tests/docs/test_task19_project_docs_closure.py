from __future__ import annotations

import json
from pathlib import Path

from docmancer.docs.domain.project_doc_ranking import (
    query_requests_history,
    rerank_project_doc_chunks,
)
from docmancer.docs.domain.project_query_intent import classify_project_query_intent
from docmancer.docs.domain.project_state import (
    PROJECT_DOCS_HANDOFF_MAX_BYTES,
    bound_project_docs_handoff,
    create_project_docs_next_action,
    project_docs_structured_next_action,
)
from docmancer.docs.models import ProjectDocsChunk
from docmancer.docs.project import ProjectMetadataReader
from docmancer.docs.project_docs_catalog import CATALOG_FILENAME


def _write_catalog(root: Path, body: str) -> None:
    (root / CATALOG_FILENAME).write_text(
        "schema_version: 1\n" + body,
        encoding="utf-8",
    )


def test_configured_monorepo_roots_discover_backend_docs_and_frontend_guides(tmp_path):
    (tmp_path / "backend" / "docs").mkdir(parents=True)
    (tmp_path / "frontend" / "guides").mkdir(parents=True)
    (tmp_path / "backend" / "docs" / "architecture.md").write_text(
        "# Backend architecture\n", encoding="utf-8"
    )
    (tmp_path / "frontend" / "guides" / "setup.md").write_text(
        "# Frontend setup\n", encoding="utf-8"
    )
    _write_catalog(
        tmp_path,
        """roots:
  - path: backend/docs
    scope: module
    module_path: backend
    authority: source_of_truth
  - path: frontend/guides
    scope: module
    module_path: frontend
    authority: supporting
""",
    )

    metadata = ProjectMetadataReader().read(tmp_path)

    assert metadata.docs_catalog_valid is True
    assert [item.path for item in metadata.docs_candidates] == [
        "backend/docs/architecture.md",
        "frontend/guides/setup.md",
    ]
    backend, frontend = metadata.docs_candidates
    assert (backend.doc_scope, backend.module_path, backend.authority) == (
        "module",
        "backend",
        "source_of_truth",
    )
    assert (frontend.doc_scope, frontend.module_path, frontend.authority) == (
        "module",
        "frontend",
        "supporting",
    )


def test_explicit_index_follows_only_safe_links_and_reports_loop_and_traversal(tmp_path):
    docs = tmp_path / "docs"
    nested = docs / "nested"
    nested.mkdir(parents=True)
    (tmp_path / "outside.md").write_text("# Outside\n", encoding="utf-8")
    (docs / "INDEX.md").write_text(
        "[Guide](guide.md)\n[Outside](../outside.md)\n", encoding="utf-8"
    )
    (docs / "guide.md").write_text(
        "[Details](nested/details.md)\n[Index](INDEX.md)\n", encoding="utf-8"
    )
    (nested / "details.md").write_text("# Details\n", encoding="utf-8")
    _write_catalog(
        tmp_path,
        """roots:
  - path: docs
    index: INDEX.md
    authority: source_of_truth
""",
    )

    metadata = ProjectMetadataReader().read(tmp_path)

    assert [item.path for item in metadata.docs_candidates] == [
        "docs/INDEX.md",
        "docs/guide.md",
        "docs/nested/details.md",
    ]
    assert all(item.path != "outside.md" for item in metadata.docs_candidates)
    assert any("outside the configured root" in warning for warning in metadata.warnings)
    assert any("index loop" in warning for warning in metadata.warnings)


def test_explicit_index_rejects_symlinked_targets(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    (docs / "linked.md").symlink_to(outside)
    (docs / "INDEX.md").write_text("[Linked](linked.md)\n", encoding="utf-8")
    _write_catalog(tmp_path, "roots:\n  - path: docs\n    index: INDEX.md\n")

    metadata = ProjectMetadataReader().read(tmp_path)

    assert [item.path for item in metadata.docs_candidates] == ["docs/INDEX.md"]
    assert any("symlink" in warning for warning in metadata.warnings)


def test_catalog_rejects_root_traversal_and_symlinked_root(tmp_path):
    outside = tmp_path.parent / "outside-docs"
    outside.mkdir(exist_ok=True)
    (tmp_path / "linked-docs").symlink_to(outside, target_is_directory=True)
    _write_catalog(
        tmp_path,
        """roots:
  - path: ../outside-docs
  - path: linked-docs
""",
    )

    metadata = ProjectMetadataReader().read(tmp_path)

    assert metadata.docs_catalog_valid is False
    assert metadata.docs_candidates == []
    assert any("stay within" in warning for warning in metadata.warnings)
    assert any("non-symlinked directory" in warning for warning in metadata.warnings)


def test_exact_document_metadata_wins_over_overlapping_configured_root(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
    _write_catalog(
        tmp_path,
        """documents:
  - path: docs/architecture.md
    role: project_architecture
    description: Exact authoritative architecture entry.
    authority: source_of_truth
roots:
  - path: docs
    authority: supporting
""",
    )

    candidate = ProjectMetadataReader().read(tmp_path).docs_candidates[0]

    assert candidate.reason == "project_architecture"
    assert candidate.description == "Exact authoritative architecture entry."
    assert candidate.authority == "source_of_truth"


def test_exact_documents_cannot_be_evicted_by_root_candidates_at_budget(tmp_path):
    exact = tmp_path / "zdocs"
    exact.mkdir()
    documents = []
    for index in range(500):
        relative = f"zdocs/doc-{index:03}.md"
        (tmp_path / relative).write_text(f"# Exact {index}\n", encoding="utf-8")
        documents.append(
            f"  - path: {relative}\n"
            "    role: other\n"
            f"    description: Exact document {index}.\n"
        )
    root = tmp_path / "aaa"
    root.mkdir()
    (root / "root.md").write_text("# Root\n", encoding="utf-8")
    _write_catalog(
        tmp_path,
        "documents:\n" + "".join(documents) + "roots:\n  - path: aaa\n",
    )

    metadata = ProjectMetadataReader().read(tmp_path)
    paths = {item.path for item in metadata.docs_candidates}

    assert len(paths) == 500
    assert "aaa/root.md" not in paths
    assert "zdocs/doc-499.md" in paths
    assert any("truncated at 500" in warning for warning in metadata.warnings)


def test_configured_root_discovery_has_a_hard_document_bound(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    for index in range(520):
        (docs / f"doc-{index:03}.md").write_text(f"# Doc {index}\n", encoding="utf-8")
    _write_catalog(tmp_path, "roots:\n  - path: docs\n")

    metadata = ProjectMetadataReader().read(tmp_path)

    assert len(metadata.docs_candidates) == 500
    assert any("truncated at 500" in warning for warning in metadata.warnings)


def test_explicit_index_has_a_per_file_link_bound(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    links = []
    for index in range(205):
        name = f"doc-{index:03}.md"
        (docs / name).write_text(f"# Doc {index}\n", encoding="utf-8")
        links.append(f"[Doc {index}]({name})")
    (docs / "INDEX.md").write_text("\n".join(links) + "\n", encoding="utf-8")
    _write_catalog(tmp_path, "roots:\n  - path: docs\n    index: INDEX.md\n")

    metadata = ProjectMetadataReader().read(tmp_path)

    assert len(metadata.docs_candidates) == 201
    assert any("links truncated at 200" in warning for warning in metadata.warnings)


def test_recursive_configured_root_rejects_symlinked_files(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    target = docs / "target.md"
    target.write_text("# Target\n", encoding="utf-8")
    (docs / "alias.md").symlink_to(target)
    _write_catalog(tmp_path, "roots:\n  - path: docs\n")

    metadata = ProjectMetadataReader().read(tmp_path)

    assert [item.path for item in metadata.docs_candidates] == ["docs/target.md"]
    assert any("symlink" in warning for warning in metadata.warnings)


def _chunk(path: str, *, status: str, authority: str, score: float) -> ProjectDocsChunk:
    return ProjectDocsChunk(
        title=path,
        content="Current agent workflow and repository architecture instructions.",
        source=f"/repo/{path}",
        url=None,
        path=path,
        lifecycle_status=status,
        authority=authority,
        metadata={"score": score},
    )


def test_completed_roadmap_is_searchable_only_for_explicit_history_intent():
    active = _chunk("AGENTS.md", status="active", authority="source_of_truth", score=0.5)
    completed = _chunk(
        "roadmap/OLD_TASK.md", status="completed", authority="historical", score=10.0
    )

    normal_question = "What is the current agent workflow?"
    normal = rerank_project_doc_chunks(
        [completed, active],
        question=normal_question,
        intent=classify_project_query_intent(normal_question),
        limit=5,
    )
    history_question = "What was the completed roadmap history?"
    history = rerank_project_doc_chunks(
        [completed, active],
        question=history_question,
        intent=classify_project_query_intent(history_question),
        limit=5,
    )
    current_roadmap_question = "What is the current roadmap?"
    current_roadmap = rerank_project_doc_chunks(
        [completed, active],
        question=current_roadmap_question,
        intent=classify_project_query_intent(current_roadmap_question),
        limit=5,
    )

    assert [item.path for item in normal] == ["AGENTS.md"]
    assert [item.path for item in current_roadmap] == ["AGENTS.md"]
    assert {item.path for item in history} == {"AGENTS.md", "roadmap/OLD_TASK.md"}


def test_operational_completed_and_browser_history_api_are_not_history_intent():
    assert query_requests_history("How is a background job marked completed?") is False
    assert query_requests_history("How does history.replaceState work?") is False
    assert query_requests_history("Show completed roadmap history") is True


def test_project_docs_handoff_is_deterministically_bounded_and_keeps_actions(tmp_path):
    action = create_project_docs_next_action(tmp_path, "Explain the architecture")
    gap = action["documentation_gap"]
    gap["required_sections"] = [
        {
            "name": f"section-{index}",
            "state": "partial",
            "evidence": [f"category-{index}", f"other-{index}"],
            "evidence_paths": [f"src/very/long/path/{index}/{part}.py" for part in range(80)],
            "facts": [(f"fact-{index}-{part} " + "x" * 300) for part in range(80)],
            "missing_evidence": [f"missing-{index}"],
            "discovery_suggestions": [
                f"Inspect repository files for missing-{index}; keep the claim unknown."
            ],
        }
        for index in range(24)
    ]
    gap["evidence_to_collect"] = [
        {
            "category": f"category-{index}",
            "paths": [f"src/{index}/{part}.py" for part in range(100)],
            "facts": [(f"observed-{index}-{part} " + "y" * 300) for part in range(100)],
        }
        for index in range(24)
    ]

    first = bound_project_docs_handoff(action)
    second = bound_project_docs_handoff(action)
    encoded = json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )

    assert first == second
    assert len(encoded) <= PROJECT_DOCS_HANDOFF_MAX_BYTES
    assert first["action"] == "create_reviewable_project_doc"
    assert first["after_file_change"]["tool"] == "prepare_docs"
    assert [item["tool"] for item in first["after"]] == [
        "prepare_docs",
        "get_docs_context",
    ]
    assert all(
        section["missing_evidence"]
        for section in first["documentation_gap"]["required_sections"]
    )
    bounds = first["documentation_gap"]["bounds"]
    assert bounds["truncated"] is True
    assert bounds["serialized_bytes"] <= PROJECT_DOCS_HANDOFF_MAX_BYTES
    assert bounds["serialized_bytes"] == len(encoded)
    assert sum(bounds["omitted_counts"].values()) > 0


def test_handoff_bounds_long_query_and_discards_unknown_bulk_fields(tmp_path):
    action = create_project_docs_next_action(tmp_path, "q" * 50_000)
    action["documentation_gap"]["required_sections"][0]["debug_blob"] = "x" * 50_000
    action["documentation_gap"]["evidence_to_collect"] = [
        {
            "category": "manifests",
            "paths": ["pyproject.toml"],
            "facts": ["f" * 50_000],
            "debug_blob": "y" * 50_000,
        }
    ]

    bounded = bound_project_docs_handoff(action)
    encoded = json.dumps(
        bounded, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    assert len(encoded) <= PROJECT_DOCS_HANDOFF_MAX_BYTES
    assert "debug_blob" not in bounded["documentation_gap"]["required_sections"][0]
    assert "debug_blob" not in bounded["documentation_gap"]["evidence_to_collect"][0]
    retry = next(item for item in bounded["after"] if item["tool"] == "get_docs_context")
    assert len(retry["arguments_patch"]["question"]) <= 512
    assert "action.arguments_patch.question_characters" in bounded["documentation_gap"]["bounds"]["omitted_counts"]


def test_canonical_production_handoff_is_bounded_without_manual_compaction(tmp_path):
    action = create_project_docs_next_action(tmp_path, "q" * 50_000)
    structured, *_rest = project_docs_structured_next_action(
        reason_code="no_project_docs",
        root=tmp_path,
        query="q" * 50_000,
    )

    for payload in (action, structured):
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        assert len(encoded) <= PROJECT_DOCS_HANDOFF_MAX_BYTES
        assert payload["documentation_gap"]["bounds"]["serialized_bytes"] <= PROJECT_DOCS_HANDOFF_MAX_BYTES
