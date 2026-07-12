from __future__ import annotations

from pathlib import Path

from docmancer.docs.impact import analyze_docs_impact, format_docs_impact_markdown


def test_code_change_produces_bounded_host_authoring_brief(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    guide = docs / "auth.md"
    original = "# Authentication\n\nUse `issue_token` from `src/auth.py`.\n"
    guide.write_text(original, encoding="utf-8")

    report = analyze_docs_impact(
        tmp_path,
        ["src/auth.py"],
        changed_symbols=["issue_token"],
    )

    brief = report["authoring_brief"]
    assert brief["schema_version"] == "documentation-update-brief-1"
    assert brief["status"] == "ready_for_host_edit"
    assert brief["allowed_edits"] == [{
        "path": "docs/auth.md",
        "heading_path": ["Authentication"],
        "reason_code": "section_reference_changed_symbol",
        "confidence": "high",
    }]
    assert brief["facts_to_verify"][0]["source_path"] == "src/auth.py"
    assert brief["follow_up"]["tool"] == "prepare_docs"
    assert brief["follow_up"]["arguments_patch"] == {
        "action": "sync_project_docs",
        "project_path": str(tmp_path.resolve()),
        "changed_paths": ["docs/auth.md"],
    }
    assert guide.read_text(encoding="utf-8") == original
    assert "Host-model documentation update brief" in format_docs_impact_markdown(report)


def test_incomplete_impact_brief_forbids_unverified_claims(tmp_path: Path) -> None:
    (tmp_path / "ARCHITECTURE.rst").write_text(
        "Architecture\n============\n",
        encoding="utf-8",
    )

    report = analyze_docs_impact(tmp_path, ["src/change.py"])

    brief = report["authoring_brief"]
    assert brief["status"] == "needs_evidence"
    assert any(
        item["reason_code"] == "section_formats_unsupported"
        for item in brief["missing_evidence"]
    )
    assert any("Do not claim behavior" in item for item in brief["must_not_invent"])


def test_changed_document_is_forwarded_to_reviewed_sync_handoff(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\nAccepted edit.\n", encoding="utf-8")

    report = analyze_docs_impact(tmp_path, ["docs/guide.md"])

    brief = report["authoring_brief"]
    assert brief["status"] == "docs_already_changed"
    assert brief["follow_up"]["arguments_patch"]["changed_paths"] == ["docs/guide.md"]
