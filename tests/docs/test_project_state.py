from __future__ import annotations

from pathlib import Path

from docmancer.docs.domain.project_state import (
    create_project_docs_next_action,
    has_high_level_project_overview,
    partition_project_doc_state,
    project_docs_structured_next_action,
)


def test_partition_project_doc_state_splits_current_stale_and_ignored():
    candidates = [
        {"path": "README.md", "content_hash": "a", "mtime_ns": 1},
        {"path": "docs/architecture.md", "content_hash": "b", "mtime_ns": 2},
    ]
    indexed = [
        {"path": "README.md", "content_hash": "a", "mtime_ns": 1},
        {"path": "docs/architecture.md", "content_hash": "old", "mtime_ns": 2},
        {"path": "docs/generated.md", "content_hash": "x", "mtime_ns": 3},
    ]

    current, stale, ignored = partition_project_doc_state(candidates, indexed)

    assert [item["path"] for item in current] == ["README.md"]
    assert stale[0]["path"] == "docs/architecture.md"
    assert stale[0]["stale_reasons"] == ["content_hash_changed"]
    assert ignored[0]["reason"] == "indexed_source_not_discovered"


def test_has_high_level_project_overview_recognizes_architecture_and_readme():
    assert has_high_level_project_overview([{"path": "docs/architecture.md", "reason": "architecture"}])
    assert has_high_level_project_overview([{"path": "README.md", "reason": "root_readme"}])
    assert not has_high_level_project_overview([{"path": "docs/api.md", "reason": "docs"}])


def test_create_project_docs_next_action_shape_includes_followups(tmp_path):
    action = create_project_docs_next_action(tmp_path, "architecture")

    assert action["action"] == "create_reviewable_project_doc"
    assert action["requires_confirmation"] is True
    assert action["preferred_path"] == "ARCHITECTURE.md"
    assert [item["tool"] for item in action["after"]] == ["inspect_project_docs", "sync_project_docs", "get_project_docs"]
    assert action["after"][2]["arguments_patch"] == {"project_path": str(tmp_path), "query": "architecture"}


def test_project_docs_structured_next_action_values(tmp_path):
    next_action, requires_confirmation, confirmation_reason, arguments_patch, agent_message, user_message = project_docs_structured_next_action(
        reason_code="architecture_doc_creation_recommended",
        root=Path(tmp_path),
    )

    assert next_action["type"] == "ask_user_to_create_project_doc"
    assert requires_confirmation is True
    assert confirmation_reason == "repo_write"
    assert arguments_patch == {"project_path": str(tmp_path)}
    assert "high-level" in agent_message
    assert user_message
