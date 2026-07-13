from __future__ import annotations

from pathlib import Path
import json
import subprocess
import time

from docmancer.docs.impact import analyze_docs_impact, format_docs_impact_markdown, unaccepted_worktree_changes


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


def test_change_aware_metric_fixture_meets_predeclared_budgets(tmp_path: Path) -> None:
    fixture_path = Path(__file__).resolve().parents[2] / "eval" / "change_aware" / "maintenance_eval.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    true_positive = false_positive = false_negative = 0
    brief_sizes: list[int] = []
    latencies_ms: list[float] = []
    for case in fixture["cases"]:
        root = tmp_path / case["id"]
        root.mkdir()
        for relative, content in case["files"].items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        started = time.perf_counter()
        report = analyze_docs_impact(
            root,
            case["changed_paths"],
            changed_symbols=case.get("changed_symbols") or [],
        )
        latencies_ms.append((time.perf_counter() - started) * 1000)
        actual = {item["path"] for item in report["authoring_brief"]["allowed_edits"]}
        expected = set(case["expected_allowed_paths"])
        true_positive += len(actual & expected)
        false_positive += len(actual - expected)
        false_negative += len(expected - actual)
        brief_sizes.append(len(json.dumps(report["authoring_brief"], ensure_ascii=False).encode("utf-8")))

    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / max(1, true_positive + false_negative)
    budgets = fixture["budgets"]
    assert precision >= budgets["minimum_precision"]
    assert recall >= budgets["minimum_recall"]
    assert max(brief_sizes) <= budgets["maximum_brief_bytes"]
    assert max(latencies_ms) <= budgets["maximum_local_latency_ms"]


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
