from __future__ import annotations

from pathlib import Path
import json
import subprocess
import time

from docmancer.docs.impact import analyze_docs_impact, format_docs_impact_markdown, git_worktree_state, unaccepted_worktree_changes


def test_authoring_brief_does_not_silently_truncate_sync_handoff(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    changed_paths = []
    for index in range(70):
        relative = f"docs/guide-{index:02}.md"
        changed_paths.append(relative)
        (tmp_path / relative).write_text(f"# Guide {index}\n", encoding="utf-8")

    report = analyze_docs_impact(tmp_path, changed_paths)

    brief = report["authoring_brief"]
    assert report["bounds"]["analysis_complete"] is False
    assert brief["status"] == "needs_evidence"
    assert brief["allowed_edits"] == []
    assert brief["follow_up"] == {}
    assert any(
        item["reason_code"] == "authoring_brief_limit_exceeded"
        for item in brief["missing_evidence"]
    )


def test_rename_and_delete_use_exact_incremental_sync_lifecycle(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "new.md").write_text("# Renamed\n", encoding="utf-8")
    evidence = {
        "changes": [
            {
                "kind": "renamed",
                "old_path": "docs/old.md",
                "new_path": "docs/new.md",
                "paths": ["docs/old.md", "docs/new.md"],
            },
            {"kind": "deleted", "paths": ["docs/deleted.md"]},
        ],
        "diagnostics": {"fallback_paths": ["docs/old.md", "docs/new.md", "docs/deleted.md"]},
    }

    report = analyze_docs_impact(
        tmp_path,
        ["docs/old.md", "docs/new.md", "docs/deleted.md"],
        diff_evidence=evidence,
    )

    arguments = report["authoring_brief"]["follow_up"]["arguments_patch"]
    assert arguments["deleted_paths"] == ["docs/deleted.md"]
    assert arguments["renamed_paths"] == [
        {"old_path": "docs/old.md", "new_path": "docs/new.md"}
    ]
    assert "changed_paths" not in arguments


def test_uncommitted_doc_proposal_is_not_an_accepted_sync_snapshot(tmp_path: Path) -> None:
    subprocess.run(["git", "-C", str(tmp_path), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "tests@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Tests"], check=True)
    guide = tmp_path / "README.md"
    guide.write_text("# Accepted\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "accepted"], check=True, capture_output=True)
    guide.write_text("# Rejected proposal\n", encoding="utf-8")

    dirty = unaccepted_worktree_changes(tmp_path, "HEAD", ["README.md"])

    assert dirty == ["README.md"]


def test_markdown_reports_optional_incremental_sync_result(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    report = analyze_docs_impact(tmp_path, ["README.md"])
    report["sync"] = {
        "status": "success",
        "message": "No derived writes were needed.",
        "metrics": {
            "files_reprocessed": 0,
            "sections_reprocessed": 0,
            "derived_writes": 0,
            "derived_deletes": 0,
            "latency_ms": 3,
        },
    }

    rendered = format_docs_impact_markdown(report)

    assert "### Incremental sync" in rendered
    assert "writes=0" in rendered


def test_git_worktree_state_distinguishes_clean_and_dirty_snapshots(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    readme = tmp_path / "README.md"
    readme.write_text("# Project\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "initial"], check=True)

    clean = git_worktree_state(tmp_path)
    assert clean["status"] == "clean"
    assert clean["reason_code"] == "git_worktree_clean"
    assert len(clean["head"]) == 40

    readme.write_text("# Changed\n", encoding="utf-8")
    assert git_worktree_state(tmp_path)["status"] == "dirty"


def test_git_worktree_state_treats_untracked_files_as_dirty(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("accepted\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "initial"], check=True)
    (tmp_path / "untracked.txt").write_text("draft\n", encoding="utf-8")

    assert git_worktree_state(tmp_path)["status"] == "dirty"


def test_git_worktree_state_fails_closed_outside_git(tmp_path: Path) -> None:
    assert git_worktree_state(tmp_path) == {
        "status": "not_git",
        "reason_code": "git_repository_required",
    }
