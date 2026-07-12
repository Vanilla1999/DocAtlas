from __future__ import annotations

from pathlib import Path

from docmancer.docs.domain.project_state import (
    create_project_docs_next_action,
    evaluate_documentation_sections,
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
    assert [item["tool"] for item in action["after"]] == ["prepare_docs", "get_docs_context"]
    assert action["after"][0]["arguments_patch"] == {"action": "sync_project_docs", "project_path": str(tmp_path)}
    assert action["after"][1]["arguments_patch"] == {"project_path": str(tmp_path), "question": "architecture"}


def test_create_project_docs_next_action_contains_machine_readable_model_handoff(tmp_path):
    action = create_project_docs_next_action(tmp_path, "Explain the architecture")

    gap = action["documentation_gap"]
    assert gap["suggested_path"] == "ARCHITECTURE.md"
    assert all(section["evidence"] for section in gap["required_sections"])
    assert "do not invent unsupported facts" in gap["rules"]
    assert action["after_file_change"] == {
        "tool": "prepare_docs",
        "arguments_patch": {"action": "sync_project_docs", "project_path": str(tmp_path)},
    }


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


def test_manifest_only_evidence_is_partial_and_not_complete(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"demo\"\n")

    gap = create_project_docs_next_action(tmp_path)["documentation_gap"]

    by_name = {section["name"]: section for section in gap["required_sections"]}
    assert gap["evidence_complete"] is False
    assert by_name["purpose"]["state"] == "partial"
    assert by_name["runtime flow"]["state"] == "missing"
    assert "runtime configuration" in by_name["runtime flow"]["missing_evidence"]
    assert by_name["runtime flow"]["discovery_suggestions"]


def test_one_missing_required_section_keeps_aggregate_incomplete():
    required = [
        {"name": "purpose", "evidence": ["manifests"]},
        {"name": "runtime flow", "evidence": ["entrypoints", "runtime configuration"]},
    ]
    evidence = [
        {"category": "manifests", "paths": ["pyproject.toml"]},
        {"category": "entrypoints", "paths": ["src/main.py"]},
    ]

    sections, complete = evaluate_documentation_sections(required, evidence)

    assert complete is False
    assert sections[0]["state"] == "complete"
    assert sections[1]["state"] == "partial"
    assert sections[1]["missing_evidence"] == ["runtime configuration"]


def test_empty_evidence_payload_does_not_complete_category():
    sections, complete = evaluate_documentation_sections(
        [{"name": "entrypoints", "evidence": ["entrypoints"]}],
        [{"category": "entrypoints", "paths": [], "facts": []}],
    )

    assert complete is False
    assert sections[0]["state"] == "missing"
    assert sections[0]["missing_evidence"] == ["entrypoints"]


def test_section_without_required_evidence_is_not_complete():
    sections, complete = evaluate_documentation_sections(
        [{"name": "unknown", "evidence": []}],
        [],
    )

    assert complete is False
    assert sections[0]["state"] == "missing"
    assert sections[0]["missing_evidence"] == ["required evidence categories"]


def test_all_sections_complete_only_with_non_empty_evidence():
    sections, complete = evaluate_documentation_sections(
        [
            {"name": "purpose", "evidence": ["manifests"]},
            {"name": "entrypoints", "evidence": ["entrypoints"]},
        ],
        [
            {"category": "manifests", "paths": ["pyproject.toml"]},
            {"category": "entrypoints", "facts": ["src/main.py exposes main()"]},
        ],
    )

    assert complete is True
    assert [section["state"] for section in sections] == ["complete", "complete"]


def test_non_string_evidence_and_blank_category_are_ignored():
    sections, complete = evaluate_documentation_sections(
        [{"name": "entrypoints", "evidence": ["entrypoints"]}],
        [
            {"category": "entrypoints", "paths": [None], "facts": [42]},
            {"category": "   ", "paths": ["src/main.py"]},
        ],
    )

    assert complete is False
    assert sections[0]["state"] == "missing"
    assert sections[0]["evidence_paths"] == []
    assert sections[0]["facts"] == []


def test_duplicate_evidence_categories_are_merged():
    sections, complete = evaluate_documentation_sections(
        [{"name": "entrypoints", "evidence": ["entrypoints"]}],
        [
            {"category": "entrypoints", "paths": ["src/main.py"]},
            {"category": "entrypoints", "facts": ["main() starts the service"]},
        ],
    )

    assert complete is True
    assert sections[0]["evidence_paths"] == ["src/main.py"]
    assert sections[0]["facts"] == ["main() starts the service"]
