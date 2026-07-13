from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from docmancer.cli.__main__ import cli
from docmancer.core.models import Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.docs import impact
from docmancer.docs.application.project_section_index import ProjectSectionIndexReader
from docmancer.docs.impact import analyze_docs_impact, changed_evidence_from_git, evaluate_labeled_section_impact
from docmancer.docs.section_metadata import SECTION_METADATA_SCHEMA_VERSION


def _run(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def _git_project(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _run(root, "init")
    _run(root, "config", "user.email", "tests@example.com")
    _run(root, "config", "user.name", "Tests")
    (root / "api.py").write_text("def old_api():\n    return 1\n", encoding="utf-8")
    (root / "session.ts").write_text("export class OldSession {}\n", encoding="utf-8")
    (root / "auth.dart").write_text("class OldNotifier {}\n", encoding="utf-8")
    (root / "move.py").write_text("def retained_symbol():\n    return 1\n", encoding="utf-8")
    (root / "fallback.go").write_text("func OldFallback() {}\n", encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "base")
    return root


def test_git_diff_derives_python_typescript_dart_rename_delete_and_move(tmp_path):
    root = _git_project(tmp_path)
    base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    (root / "api.py").write_text("def new_api():\n    return 2\n", encoding="utf-8")
    (root / "session.ts").unlink()
    (root / "auth.dart").write_text("class NewNotifier {}\n", encoding="utf-8")
    (root / "src").mkdir()
    _run(root, "mv", "move.py", "src/move.py")
    (root / "fallback.go").write_text("func NewFallback() {}\n", encoding="utf-8")
    _run(root, "add", "-A")
    _run(root, "commit", "-m", "change symbols")

    evidence = changed_evidence_from_git(root, base)

    assert {"old_api", "new_api", "OldSession", "OldNotifier", "NewNotifier"} <= set(evidence["symbols"])
    assert {"move.py", "src/move.py"} <= set(evidence["paths"])
    assert any(change["kind"] == "renamed" for change in evidence["changes"])
    assert evidence["diagnostics"]["symbol_confidence"] == "low"
    assert "fallback.go" in evidence["diagnostics"]["fallback_paths"]


def test_git_diff_preserves_unicode_paths_and_symbols(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _run(root, "init")
    _run(root, "config", "user.email", "tests@example.com")
    _run(root, "config", "user.name", "Tests")
    source = root / "café.ts"
    source.write_text("export class OldApi {}\n", encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "base")
    base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    source.write_text("export class NewApi {}\n", encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "change")

    evidence = changed_evidence_from_git(root, base)

    assert evidence["paths"] == ["café.ts"]
    assert evidence["symbols"] == ["OldApi", "NewApi"]
    assert evidence["diagnostics"]["symbol_confidence"] == "high"


def test_pure_rename_is_explicit_low_confidence_fallback(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _run(root, "init")
    _run(root, "config", "user.email", "tests@example.com")
    _run(root, "config", "user.name", "Tests")
    (root / "old.ts").write_text("export class StableApi {}\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "impact.md").write_text("# Impact\n", encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "base")
    base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    _run(root, "mv", "old.ts", "new.ts")
    _run(root, "commit", "-m", "move")

    evidence = changed_evidence_from_git(root, base)
    report = analyze_docs_impact(root, evidence["paths"], diff_evidence=evidence)

    assert evidence["diagnostics"]["symbol_confidence"] == "low"
    assert set(evidence["diagnostics"]["fallback_paths"]) == {"old.ts", "new.ts"}
    assert report["section_candidates"]["review"][0]["path"] == "docs/impact.md"


def test_patch_byte_budget_forces_conservative_fallback(tmp_path, monkeypatch):
    root = _git_project(tmp_path)
    base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    (root / "api.py").write_text("def new_api():\n    return '" + "x" * 5000 + "'\n", encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "large patch")
    monkeypatch.setattr(impact, "_MAX_PATCH_BYTES", 128)

    evidence = changed_evidence_from_git(root, base)

    assert evidence["diagnostics"]["patch_truncated"] is True
    assert evidence["diagnostics"]["symbol_confidence"] == "low"
    assert "api.py" in evidence["diagnostics"]["fallback_paths"]


def test_bounded_process_runner_enforces_bytes_and_deadline():
    stdout, _stderr, _returncode, truncated, timed_out = impact._run_process_bounded(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 100000)"],
        max_stdout_bytes=128,
        timeout_seconds=2,
    )
    assert len(stdout) == 128
    assert truncated is True
    assert timed_out is False

    _stdout, _stderr, _returncode, _truncated, timed_out = impact._run_process_bounded(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        max_stdout_bytes=128,
        timeout_seconds=0.05,
    )
    assert timed_out is True


def test_typescript_local_variable_is_not_reported_as_api_symbol():
    patch = """diff --git a/app.ts b/app.ts
--- a/app.ts
+++ b/app.ts
@@ -2 +2 @@ function handler() {
-  const temporary = oldValue;
+  const temporary = newValue;
"""

    symbols, diagnostics = impact._symbols_from_patch(patch)

    assert symbols == ["handler"]
    assert "temporary" not in symbols
    assert diagnostics["symbol_confidence"] == "low"
    assert diagnostics["fallback_paths"] == ["app.ts"]


def test_mixed_supported_diff_uses_low_confidence_for_unparsed_file():
    patch = """diff --git a/a.ts b/a.ts
--- a/a.ts
+++ b/a.ts
@@ -1 +1 @@
-export class OldApi {}
+export class NewApi {}
diff --git a/b.ts b/b.ts
--- a/b.ts
+++ b/b.ts
@@ -8 +8 @@
-  return oldValue;
+  return newValue;
"""

    symbols, diagnostics = impact._symbols_from_patch(patch)

    assert symbols == ["OldApi", "NewApi"]
    assert diagnostics["symbol_confidence"] == "low"
    assert diagnostics["fallback_paths"] == ["b.ts"]
    assert diagnostics["reason_code"] == "diff_symbol_parser_partial"


def test_symbol_limit_is_explicit_and_falls_back_for_omitted_symbols():
    patch_parts = []
    for index in range(130):
        path = f"src/change_{index:03}.ts"
        patch_parts.append(
            f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n"
            f"-export class Old{index:03} {{}}\n+export class New{index:03} {{}}\n"
        )

    symbols, diagnostics = impact._symbols_from_patch("".join(patch_parts))

    assert len(symbols) == impact._MAX_SYMBOLS
    assert diagnostics["symbols_total"] == 260
    assert diagnostics["symbols_truncated"] is True
    assert diagnostics["symbol_confidence"] == "low"
    assert "src/change_129.ts" in diagnostics["fallback_paths"]


def test_dart_call_expression_is_not_a_changed_definition():
    patch = """diff --git a/auth.dart b/auth.dart
--- a/auth.dart
+++ b/auth.dart
@@ -4 +4 @@
-  return oldCompute();
+  return compute();
"""

    symbols, diagnostics = impact._symbols_from_patch(patch)

    assert symbols == []
    assert diagnostics["symbol_confidence"] == "low"
    assert diagnostics["fallback_paths"] == ["auth.dart"]


def _hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _indexed_reader(root: Path, db_path: Path, *, stale: bool = False, schema: str = SECTION_METADATA_SCHEMA_VERSION) -> ProjectSectionIndexReader:
    doc = root / "ARCHITECTURE.md"
    metadata = {
        "project_path": str(root.resolve()),
        "source_class": "project_file",
        "project_docs": True,
        "project_doc_path": "ARCHITECTURE.md",
        "project_doc_content_hash": "sha256:stale" if stale else _hash(doc),
        "project_doc_sections_schema": schema,
        "project_doc_sections_status": "parsed",
        "project_doc_sections_reason": "section_metadata_parsed",
        "project_doc_sections": [{
            "source_document_path": "ARCHITECTURE.md",
            "heading_path": ["Architecture", "Authentication"],
            "mentioned_paths": [],
            "mentioned_symbols": ["issue_token"],
            "paths_truncated": False,
            "symbols_truncated": False,
            "fields_truncated": False,
            "document_sections_truncated": False,
            "content_hash": "sha256:" + "0" * 64,
        }],
    }
    SQLiteStore(str(db_path), extracted_dir=str(root / ".extracted")).add_documents([
        Document(source=str(doc.resolve()), content=doc.read_text(encoding="utf-8"), metadata=metadata)
    ])
    return ProjectSectionIndexReader(db_path)


def test_matching_indexed_hash_avoids_markdown_reparse(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ARCHITECTURE.md").write_text("# Architecture\n\n## Authentication\nUse `issue_token`.\n", encoding="utf-8")
    reader = _indexed_reader(root, tmp_path / "index.db")
    monkeypatch.setattr(impact, "extract_section_metadata_result", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("reparsed")))

    report = analyze_docs_impact(root, ["src/auth.py"], changed_symbols=["issue_token"], section_reader=reader)

    assert report["section_metadata"]["indexed_current"] == ["ARCHITECTURE.md"]
    assert report["section_candidates"]["must_update"][0]["metadata_source"] == "index"
    assert report["next_actions"] == []


def test_docs_impact_cli_reads_sections_from_configured_index(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ARCHITECTURE.md").write_text("# Architecture\n\n## Authentication\nUse `issue_token`.\n", encoding="utf-8")
    db_path = tmp_path / "custom-index.db"
    _indexed_reader(root, db_path)
    config_path = tmp_path / "docmancer.yaml"
    config_path.write_text(f"index:\n  db_path: {db_path}\n", encoding="utf-8")

    result = CliRunner().invoke(cli, [
        "docs-impact",
        "--project-path", str(root),
        "--changed-file", "src/auth.py",
        "--changed-symbol", "issue_token",
        "--config", str(config_path),
        "--format", "json",
    ])

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["section_metadata"]["indexed_current"] == ["ARCHITECTURE.md"]
    assert report["section_metadata"]["reparsed_missing"] == []


def test_stale_hash_reparses_and_requests_sync(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    doc = root / "ARCHITECTURE.md"
    doc.write_text("# Architecture\n\nUse `issue_token`.\n", encoding="utf-8")
    reader = _indexed_reader(root, tmp_path / "index.db", stale=True)
    calls: list[str] = []
    real = impact.extract_section_metadata_result
    monkeypatch.setattr(impact, "extract_section_metadata_result", lambda path, **kwargs: calls.append(str(path)) or real(path, **kwargs))

    report = analyze_docs_impact(root, ["src/auth.py"], changed_symbols=["issue_token"], section_reader=reader)

    assert calls
    assert report["section_metadata"]["reparsed_stale"] == ["ARCHITECTURE.md"]
    assert report["next_actions"][0]["tool"] == "prepare_docs"
    assert report["next_actions"][0]["reason_code"] == "refresh_stale_or_missing_section_metadata"


def test_stale_section_schema_is_not_used_as_current_truth(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ARCHITECTURE.md").write_text("# Architecture\n\nUse `issue_token`.\n", encoding="utf-8")
    reader = _indexed_reader(root, tmp_path / "index.db", schema="project-sections-old")

    indexed = reader.read(root)

    assert indexed["ARCHITECTURE.md"]["status"] == "stale"
    assert indexed["ARCHITECTURE.md"]["reason_code"] == "indexed_section_schema_stale"


def test_invalid_indexed_section_shape_is_stale_instead_of_crashing(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    doc = root / "README.md"
    doc.write_text("# Project\n", encoding="utf-8")
    metadata = {
        "project_path": str(root.resolve()),
        "source_class": "project_file",
        "project_docs": True,
        "project_doc_path": "README.md",
        "project_doc_content_hash": _hash(doc),
        "project_doc_sections_schema": SECTION_METADATA_SCHEMA_VERSION,
        "project_doc_sections": ["corrupt"],
    }
    db_path = tmp_path / "index.db"
    SQLiteStore(str(db_path), extracted_dir=str(tmp_path / ".extracted")).add_documents([
        Document(source=str(doc.resolve()), content=doc.read_text(encoding="utf-8"), metadata=metadata)
    ])
    reader = ProjectSectionIndexReader(db_path)

    indexed = reader.read(root)
    report = analyze_docs_impact(root, ["src/change.py"], section_reader=reader)

    assert indexed["README.md"]["status"] == "stale"
    assert indexed["README.md"]["reason_code"] == "indexed_sections_invalid"
    assert report["section_metadata"]["reparsed_stale"] == ["README.md"]


def test_oversized_indexed_section_field_is_rejected(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    doc = root / "README.md"
    doc.write_text("# Project\n", encoding="utf-8")
    metadata = {
        "project_path": str(root.resolve()),
        "source_class": "project_file",
        "project_docs": True,
        "project_doc_path": "README.md",
        "project_doc_content_hash": _hash(doc),
        "project_doc_sections_schema": SECTION_METADATA_SCHEMA_VERSION,
        "project_doc_sections": [{
            "source_document_path": "README.md",
            "heading_path": ["x" * 513],
            "mentioned_paths": [],
            "mentioned_symbols": [],
            "paths_truncated": False,
            "symbols_truncated": False,
            "fields_truncated": False,
            "document_sections_truncated": False,
            "content_hash": "sha256:" + "0" * 64,
        }],
    }
    db_path = tmp_path / "index.db"
    SQLiteStore(str(db_path), extracted_dir=str(tmp_path / ".extracted")).add_documents([
        Document(source=str(doc.resolve()), content=doc.read_text(encoding="utf-8"), metadata=metadata)
    ])

    indexed = ProjectSectionIndexReader(db_path).read(root)

    assert indexed["README.md"]["status"] == "stale"
    assert indexed["README.md"]["reason_code"] == "indexed_sections_invalid"


def test_indexed_path_cannot_escape_project_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    doc = root / "README.md"
    doc.write_text("# Project\n", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("secret\n", encoding="utf-8")
    metadata = {
        "project_path": str(root.resolve()),
        "source_class": "project_file",
        "project_docs": True,
        "project_doc_path": "../outside.md",
        "project_doc_content_hash": _hash(outside),
        "project_doc_sections_schema": SECTION_METADATA_SCHEMA_VERSION,
        "project_doc_sections": [],
    }
    db_path = tmp_path / "index.db"
    SQLiteStore(str(db_path), extracted_dir=str(tmp_path / ".extracted")).add_documents([
        Document(source=str(doc.resolve()), content=doc.read_text(encoding="utf-8"), metadata=metadata)
    ])

    assert ProjectSectionIndexReader(db_path).read(root) == {}


def test_symbol_parser_failure_keeps_conservative_path_impact(tmp_path):
    root = _git_project(tmp_path)
    (root / "README.md").write_text("# Project\n", encoding="utf-8")
    _run(root, "add", "README.md")
    _run(root, "commit", "-m", "add docs")
    base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    (root / "fallback.go").write_text("func ChangedFallback() {}\n", encoding="utf-8")
    _run(root, "add", "fallback.go")
    _run(root, "commit", "-m", "change unsupported symbol")
    diff = changed_evidence_from_git(root, base)

    report = analyze_docs_impact(root, diff["paths"], diff_evidence=diff)

    assert report["diff_evidence"]["symbol_confidence"] == "low"
    assert report["section_candidates"]["review"]
    assert report["section_candidates"]["review"][0]["confidence"] == "low"


def test_symbol_parser_fallback_never_silently_ignores_non_authority_doc(tmp_path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "impact.md").write_text("# Impact\n\nGeneral maintenance notes.\n", encoding="utf-8")
    diagnostics = {
        "symbol_confidence": "low",
        "fallback_paths": ["internal/change.go"],
        "reason_code": "diff_symbol_parser_fallback",
    }

    report = analyze_docs_impact(
        root,
        ["internal/change.go"],
        diff_evidence={"symbols": [], "diagnostics": diagnostics},
    )

    assert report["section_candidates"]["review"][0]["path"] == "docs/impact.md"
    assert report["section_candidates"]["review"][0]["confidence"] == "low"
    assert report["recommendation"].startswith("Review the listed docs")


def test_symbol_parser_fallback_keeps_module_doc_confidence_low(tmp_path):
    root = tmp_path / "repo"
    module = root / "packages" / "billing"
    module.mkdir(parents=True)
    (module / "README.md").write_text("# Billing\n", encoding="utf-8")
    changed_path = "packages/billing/internal/change.go"
    diagnostics = {
        "symbol_confidence": "low",
        "fallback_paths": [changed_path],
        "reason_code": "diff_symbol_parser_fallback",
    }

    report = analyze_docs_impact(
        root,
        [changed_path],
        diff_evidence={"symbols": [], "diagnostics": diagnostics},
    )

    candidate = report["section_candidates"]["review"][0]
    assert candidate["path"] == "packages/billing/README.md"
    assert candidate["reason_code"] == "diff_symbol_parser_fallback"
    assert candidate["confidence"] == "low"


def test_test_only_symbol_evidence_does_not_mark_project_docs(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _run(root, "init")
    _run(root, "config", "user.email", "tests@example.com")
    _run(root, "config", "user.name", "Tests")
    (root / "README.md").write_text("# API\nUse `issue_token`.\n", encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_auth.py").write_text("def issue_token():\n    pass\n", encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "base")
    base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    (tests / "test_auth.py").write_text("def renamed_test_helper():\n    pass\n", encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "rename test helper")

    evidence = changed_evidence_from_git(root, base)
    report = analyze_docs_impact(root, evidence["paths"], diff_evidence=evidence)

    assert report["summary"]["code_files"] == 0
    assert report["section_candidates"]["must_update"] == []
    assert report["summary"]["docs_to_review"] == 0


def test_truncated_section_metadata_forces_low_confidence_review(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    references = " ".join(f"`Symbol{index:02}`" for index in range(1, 66))
    (root / "README.md").write_text(f"# API\n{references}\n", encoding="utf-8")

    report = analyze_docs_impact(root, ["src/change.py"], changed_symbols=["Symbol65"])

    candidate = report["section_candidates"]["review"][0]
    assert candidate["reason_code"] == "section_metadata_truncated"
    assert candidate["confidence"] == "low"
    assert report["section_metadata"]["truncated"] == ["README.md"]
    assert report["bounds"]["analysis_complete"] is False
    assert report["recommendation"].startswith("Analysis is incomplete")


def test_large_docs_set_is_bounded_and_reports_truncation(tmp_path):
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    for index in range(230):
        (docs / f"section-{index:03d}.md").write_text(f"# Section {index}\n\nUse `ChangedSymbol`.\n", encoding="utf-8")

    report = analyze_docs_impact(root, ["src/change.py"], changed_symbols=["ChangedSymbol"])

    returned = sum(len(items) for items in report["section_candidates"].values())
    serialized = len(json.dumps(report, ensure_ascii=False).encode("utf-8"))
    assert returned <= 200
    assert serialized <= 32 * 1024
    assert report["bounds"]["truncated"] is True
    assert report["bounds"]["section_candidates_total"] >= 200
    rendered = impact.format_docs_impact_markdown(report)
    assert "Truncation notice" in rendered
    assert "Continue with:" in rendered


def test_docs_discovery_and_markdown_reparse_work_are_bounded(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    for index in range(600):
        (docs / f"section-{index:03d}.md").write_text(f"# Section {index}\n", encoding="utf-8")
    calls = 0
    real = impact.extract_section_metadata_result

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(impact, "extract_section_metadata_result", counted)

    report = analyze_docs_impact(root, ["src/change.py"], changed_symbols=["ChangedSymbol"])

    assert calls <= impact._MAX_DOCS_ANALYZED
    assert report["bounds"]["docs_candidates_analyzed"] <= impact._MAX_DOCS_ANALYZED
    assert report["bounds"]["docs_candidates_truncated"] is True
    assert any("discovery truncated" in warning for warning in report["warnings"])
    assert report["bounds"]["analysis_complete"] is False
    assert report["recommendation"].startswith("Analysis is incomplete")


def test_headingless_markdown_can_match_changed_symbol(tmp_path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "guide.md").write_text("Call `issue_token` here.\n", encoding="utf-8")

    report = analyze_docs_impact(root, ["src/auth.py"], changed_symbols=["issue_token"])

    match = next(item for item in report["section_candidates"]["must_update"] if item["path"] == "docs/guide.md")
    assert match["heading_path"] == []
    assert report["bounds"]["analysis_complete"] is True


def test_unreadable_markdown_forces_incomplete_review(tmp_path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "guide.md").write_bytes(b"# Guide\n\xff")

    report = analyze_docs_impact(root, ["src/auth.py"], changed_symbols=["issue_token"])

    assert report["section_metadata"]["read_errors"] == ["docs/guide.md"]
    assert "section_document_read_errors" in report["bounds"]["incomplete_reasons"]
    assert any(
        item["path"] == "docs/guide.md" and item["reason_code"] == "section_document_read_error"
        for item in report["section_candidates"]["review"]
    )


def test_deleted_document_is_not_classified_as_code(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# Project\n", encoding="utf-8")
    evidence = {
        "changes": [{"kind": "deleted", "paths": ["docs/old.md"]}],
        "diagnostics": {"fallback_paths": ["docs/old.md"]},
    }

    report = analyze_docs_impact(root, ["docs/old.md"], diff_evidence=evidence)

    assert report["summary"]["code_files"] == 0
    assert report["summary"]["docs_updated"] == 1
    assert report["impacts"] == [{
        "path": "docs/old.md", "status": "deleted", "reasons": ["documentation_deleted"],
        "changed_files": ["docs/old.md"], "module_path": None,
    }]


def test_renamed_document_preserves_lifecycle_evidence(tmp_path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "new.md").write_text("# New\n", encoding="utf-8")
    evidence = {
        "changes": [{
            "kind": "renamed", "old_path": "docs/old.md", "new_path": "docs/new.md",
            "paths": ["docs/old.md", "docs/new.md"],
        }],
        "diagnostics": {"fallback_paths": ["docs/old.md", "docs/new.md"]},
    }

    report = analyze_docs_impact(root, ["docs/old.md", "docs/new.md"], diff_evidence=evidence)

    assert report["summary"]["code_files"] == 0
    renamed = next(item for item in report["impacts"] if item["status"] == "renamed")
    assert renamed["old_path"] == "docs/old.md"
    assert renamed["new_path"] == "docs/new.md"


def test_actual_git_handoff_classifies_deleted_and_renamed_docs(tmp_path):
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    _run(root, "init")
    _run(root, "config", "user.email", "tests@example.com")
    _run(root, "config", "user.name", "Tests")
    (docs / "delete.md").write_text("# Delete me\n", encoding="utf-8")
    (docs / "old.md").write_text("# Keep this content\n\nStable prose.\n", encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "base docs")
    base = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
    ).stdout.strip()
    (docs / "delete.md").unlink()
    (docs / "old.md").rename(docs / "new.md")
    _run(root, "add", "-A")
    _run(root, "commit", "-m", "change docs")

    evidence = changed_evidence_from_git(root, base)
    report = analyze_docs_impact(root, evidence["paths"], diff_evidence=evidence)

    assert report["summary"]["code_files"] == 0
    assert report["summary"]["docs_updated"] == 2
    assert {item["status"] for item in report["impacts"]} == {"deleted", "renamed"}


def test_requirements_txt_remains_dependency_metadata(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# Project\n", encoding="utf-8")

    report = analyze_docs_impact(root, ["requirements.txt"])

    assert report["summary"]["code_files"] == 1
    assert report["summary"]["docs_updated"] == 0
    assert report["impacts"][0]["reasons"] == ["dependency_metadata_changed"]


@pytest.mark.parametrize(
    ("old_path", "new_path", "expected_doc_path"),
    [
        ("docs/guide.md", "src/guide.py", "docs/guide.md"),
        ("src/guide.py", "docs/guide.md", "docs/guide.md"),
    ],
)
def test_cross_type_rename_preserves_code_and_document_lifecycle(
    tmp_path, old_path, new_path, expected_doc_path,
):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Project\n", encoding="utf-8")
    if new_path.endswith(".md"):
        (root / new_path).write_text("# Guide\n", encoding="utf-8")
    evidence = {
        "changes": [{
            "kind": "renamed", "old_path": old_path, "new_path": new_path,
            "paths": [old_path, new_path],
        }],
        "diagnostics": {"fallback_paths": [old_path, new_path]},
    }

    report = analyze_docs_impact(root, [old_path, new_path], diff_evidence=evidence)

    assert report["summary"]["code_files"] == 1
    lifecycle = next(item for item in report["impacts"] if item["path"] == expected_doc_path)
    assert lifecycle["status"] in {"deleted", "updated"}
    assert any(item["path"] == "README.md" for item in report["section_candidates"]["review"])


def test_document_copy_marks_only_the_new_path_as_changed(tmp_path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "old.md").write_text("# Guide\n", encoding="utf-8")
    (root / "docs" / "new.md").write_text("# Guide\n", encoding="utf-8")
    evidence = {
        "changes": [{
            "kind": "copied", "old_path": "docs/old.md", "new_path": "docs/new.md",
            "paths": ["docs/old.md", "docs/new.md"],
        }],
        "diagnostics": {"fallback_paths": ["docs/old.md", "docs/new.md"]},
    }

    report = analyze_docs_impact(root, ["docs/old.md", "docs/new.md"], diff_evidence=evidence)

    assert report["summary"]["code_files"] == 0
    assert report["summary"]["docs_updated"] == 1
    assert [item["path"] for item in report["impacts"]] == ["docs/new.md"]


def test_explicit_changed_file_overflow_is_rejected(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()

    with pytest.raises(ValueError, match="At most 500 explicit changed files"):
        analyze_docs_impact(root, [f"src/change_{index}.py" for index in range(501)])


def test_unrelated_unsupported_doc_does_not_make_every_diff_incomplete(tmp_path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Project\n", encoding="utf-8")
    (root / "docs" / "legacy.rst").write_text("Legacy\n======\n", encoding="utf-8")

    report = analyze_docs_impact(root, ["src/unrelated.py"])

    assert report["bounds"]["analysis_complete"] is True
    assert report["section_metadata"]["unsupported"] == []
    assert not any(item["path"] == "docs/legacy.rst" for item in report["impacts"])


def test_impacted_unsupported_architecture_doc_stays_conservative(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ARCHITECTURE.rst").write_text("Architecture\n============\n", encoding="utf-8")

    report = analyze_docs_impact(root, ["src/change.py"])

    assert report["bounds"]["analysis_complete"] is False
    assert report["section_metadata"]["unsupported"] == ["ARCHITECTURE.rst"]
    assert any(
        item["path"] == "ARCHITECTURE.rst" and item["reason_code"] == "section_format_unsupported"
        for item in report["section_candidates"]["review"]
    )


def test_hard_output_bound_compacts_auxiliary_metadata_too():
    paths = [f"docs/{'x' * 180}{index}.md" for index in range(400)]
    report = {
        "schema_version": "docs-impact-2",
        "project_path": "/repo",
        "summary": {},
        "changed_files": [],
        "changed_symbols": [],
        "impacts": [],
        "section_candidates": {"must_update": [], "review": [], "unlikely": []},
        "bounds": {"truncated": False, "max_output_bytes": 32 * 1024, "continuation": "x" * 100_000},
        "section_metadata": {"indexed_current": [], "reparsed_missing": list(paths), "reparsed_stale": []},
        "next_actions": [{"paths": list(paths)}],
        "diff_evidence": {"supported_paths": list(paths), "fallback_paths": []},
        "missing": [],
        "recommendation": "review",
        "warnings": [],
    }

    bounded = impact._bound_report(report)

    assert len(json.dumps(bounded, ensure_ascii=False).encode("utf-8")) <= 32 * 1024
    assert bounded["bounds"]["truncated"] is True
    assert bounded["omitted"]


def test_hard_output_bound_truncates_adversarial_individual_paths():
    segment = "x" * 240
    long_path = "/".join([segment] * 16) + ".py"
    report = {
        "schema_version": "docs-impact-2",
        "project_path": "/repo",
        "summary": {},
        "changed_files": [f"{long_path}{index}" for index in range(20)],
        "changed_symbols": [],
        "impacts": [],
        "section_candidates": {"must_update": [], "review": [], "unlikely": []},
        "bounds": {"truncated": False, "max_output_bytes": 32 * 1024},
        "section_metadata": {"indexed_current": [], "reparsed_missing": [], "reparsed_stale": []},
        "next_actions": [],
        "diff_evidence": {},
        "missing": [],
        "recommendation": "review",
        "warnings": [],
    }

    bounded = impact._bound_report(report)

    serialized = len(json.dumps(bounded, ensure_ascii=False).encode("utf-8"))
    assert serialized <= 32 * 1024
    assert bounded["bounds"]["serialized_bytes"] == serialized


def test_hard_output_bound_invalidates_actionable_authoring_brief():
    report = {
        "schema_version": "docs-impact-2",
        "project_path": "/repo",
        "summary": {},
        "changed_files": [],
        "changed_symbols": [],
        "impacts": [{"path": f"docs/{index}.md", "evidence": "x" * 1000} for index in range(100)],
        "section_candidates": {"must_update": [], "review": [], "unlikely": []},
        "bounds": {"truncated": False, "max_output_bytes": 32 * 1024},
        "section_metadata": {},
        "authoring_brief": {
            "schema_version": "documentation-update-brief-1",
            "status": "ready_for_host_edit",
            "allowed_edits": [{"path": "docs/guide.md", "heading_path": ["Guide"]}],
            "missing_evidence": [],
            "follow_up": {"tool": "prepare_docs", "arguments_patch": {"action": "sync_project_docs"}},
        },
        "next_actions": [],
        "diff_evidence": {},
        "missing": [],
        "recommendation": "review",
        "warnings": [],
    }

    bounded = impact._bound_report(report)

    assert len(json.dumps(bounded, ensure_ascii=False).encode("utf-8")) <= 32 * 1024
    assert bounded["bounds"]["output_truncated"] is True
    assert bounded["authoring_brief"]["allowed_edits"] == []
    assert bounded["authoring_brief"]["follow_up"] == {}
    assert any(
        item["reason_code"] == "output_truncated"
        for item in bounded["authoring_brief"]["missing_evidence"]
    )


def test_markdown_preserves_unlikely_and_truncation_contract(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# Overview\n\nUnrelated text.\n", encoding="utf-8")

    report = analyze_docs_impact(root, ["src/auth.py"], changed_symbols=["issue_token"])
    rendered = impact.format_docs_impact_markdown(report)

    assert report["section_candidates"]["unlikely"]
    assert "Unlikely to require an update" in rendered
    assert "### Review\n" not in rendered
    assert report["recommendation"].startswith("No maintained documentation changes")


def test_candidate_offset_produces_a_progressing_continuation(tmp_path):
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    for index in range(12):
        (docs / f"section-{index:02d}.md").write_text("# API\n\nUse `ChangedSymbol`.\n", encoding="utf-8")

    first = analyze_docs_impact(root, ["src/change.py"], changed_symbols=["ChangedSymbol"], candidate_limit=5)
    second = analyze_docs_impact(
        root,
        ["src/change.py"],
        changed_symbols=["ChangedSymbol"],
        candidate_offset=5,
        candidate_limit=5,
    )

    first_paths = {item["path"] for item in first["section_candidates"]["must_update"]}
    second_paths = {item["path"] for item in second["section_candidates"]["must_update"]}
    assert len(first_paths) == len(second_paths) == 5
    assert first_paths.isdisjoint(second_paths)
    assert "--candidate-offset 5" in first["bounds"]["continuation"]
    assert f"--project-path {root}" in first["bounds"]["continuation"]
    assert "--changed-symbol ChangedSymbol" in first["bounds"]["continuation"]
    assert "prepare_docs" not in first["bounds"]["continuation"]
    assert first["authoring_brief"]["allowed_edits"] == []
    assert second["authoring_brief"]["allowed_edits"] == []
    assert second["authoring_brief"]["follow_up"] == {}


def test_continuation_stops_at_candidate_evaluation_ceiling(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    body = "\n".join(f"## S{index}\nUse `ChangedSymbol`." for index in range(3))
    for index in range(4):
        (docs / f"section-{index}.md").write_text(f"# API\n{body}\n", encoding="utf-8")
    monkeypatch.setattr(impact, "_MAX_SECTION_CANDIDATES_EVALUATED", 10)

    report = analyze_docs_impact(
        root,
        ["src/change.py"],
        changed_symbols=["ChangedSymbol"],
        candidate_offset=10,
        candidate_limit=5,
    )

    assert report["bounds"]["candidate_evaluation_truncated"] is True
    assert report["bounds"]["section_candidates_returned"] == 0
    assert report["bounds"]["continuation"] is None
    assert report["bounds"]["continuation_reason"] == "evaluation_budget_exhausted_narrow_diff"


def test_continuation_preserves_config_and_cli_flags(tmp_path):
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    for index in range(3):
        (docs / f"section-{index}.md").write_text("# API\nUse `ChangedSymbol`.\n", encoding="utf-8")
    config_path = tmp_path / "custom.yaml"
    context = {"project_path": str(root), "config_path": str(config_path), "fail_on_missing": True}

    report = analyze_docs_impact(
        root,
        ["src/change.py"],
        changed_symbols=["ChangedSymbol"],
        candidate_limit=1,
        continuation_context=context,
    )

    command = report["bounds"]["continuation"]
    assert f"--project-path {root}" in command
    assert f"--config {config_path}" in command
    assert "--changed-symbol ChangedSymbol" in command
    assert "--fail-on-missing" in command


def test_distant_symbol_section_outranks_nearby_irrelevant_section(tmp_path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Nearby\n\nGeneral source notes.\n", encoding="utf-8")
    (root / "docs" / "distant.md").write_text("# Exact API\n\nUse `ChangedSymbol`.\n", encoding="utf-8")

    report = analyze_docs_impact(root, ["src/change.py"], changed_symbols=["ChangedSymbol"])

    assert report["section_candidates"]["must_update"][0]["path"] == "docs/distant.md"
    assert report["section_candidates"]["must_update"][0]["reason_code"] == "section_reference_changed_symbol"
    assert report["section_candidates"]["unlikely"][0]["path"] == "README.md"
    assert report["section_candidates"]["unlikely"][0]["reason_code"] == "no_explicit_reference_match"


def test_labeled_30_change_corpus_meets_precision_and_recall_gate(tmp_path):
    root = tmp_path / "repo"
    docs = root / "docs"
    docs.mkdir(parents=True)
    sections = ["# Impact"]
    for index in range(1, 31):
        sections.extend(["", f"## ChangedSymbol{index:02d}", f"Use `ChangedSymbol{index:02d}`."])
    (docs / "impact.md").write_text("\n".join(sections) + "\n", encoding="utf-8")
    corpus_path = Path(__file__).resolve().parents[2] / "eval" / "docs_impact" / "section_impact_corpus.json"
    cases = json.loads(corpus_path.read_text(encoding="utf-8"))

    quality = evaluate_labeled_section_impact(root, cases)

    assert quality["cases"] == 30
    assert quality["must_update_recall"] >= 0.90
    assert quality["must_update_precision"] >= 0.75
    assert quality["passed"] is True
    assert quality["automatic_symbol_cases"] == 27
    assert quality["conservative_fallback_cases"] == 3
    assert quality["fallback_review_expected"] == 3
    assert quality["fallback_review_matched"] == 3
    assert quality["fallback_review_precision"] >= 0.75
    assert quality["fallback_review_recall"] >= 0.90


def test_actual_git_pipeline_handles_30_change_quality_corpus(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    docs = root / "docs"
    docs.mkdir()
    _run(root, "init")
    _run(root, "config", "user.email", "tests@example.com")
    _run(root, "config", "user.name", "Tests")
    sections = ["# Impact"]
    for index in range(1, 31):
        sections.extend(["", f"## ChangedSymbol{index:02d}", f"Use `ChangedSymbol{index:02d}`."])
        if index <= 9:
            path = root / f"change_{index:02d}.py"
            old_line = f"def OldSymbol{index:02d}():\n    return 1\n"
        elif index <= 18:
            path = root / f"change_{index:02d}.ts"
            old_line = f"export class OldSymbol{index:02d} {{}}\n"
        elif index <= 27:
            path = root / f"change_{index:02d}.dart"
            old_line = f"class OldSymbol{index:02d} {{}}\n"
        else:
            internal = root / "internal"
            internal.mkdir(exist_ok=True)
            path = internal / f"change_{index:02d}.go"
            old_line = f"func OldSymbol{index:02d}() {{}}\n"
        path.write_text(old_line, encoding="utf-8")
    (docs / "impact.md").write_text("\n".join(sections) + "\n", encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "base")
    base = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

    for index in range(1, 31):
        if index <= 9:
            path = root / f"change_{index:02d}.py"
            new_line = f"def ChangedSymbol{index:02d}():\n    return 1\n"
        elif index <= 18:
            path = root / f"change_{index:02d}.ts"
            new_line = f"export class ChangedSymbol{index:02d} {{}}\n"
        elif index <= 27:
            path = root / f"change_{index:02d}.dart"
            new_line = f"class ChangedSymbol{index:02d} {{}}\n"
        else:
            path = root / "internal" / f"change_{index:02d}.go"
            new_line = f"func ChangedSymbol{index:02d}() {{}}\n"
        path.write_text(new_line, encoding="utf-8")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "change corpus")

    evidence = changed_evidence_from_git(root, base)
    report = analyze_docs_impact(root, evidence["paths"], diff_evidence=evidence)

    must_update_headings = {
        " > ".join(item["heading_path"])
        for item in report["section_candidates"]["must_update"]
    }
    assert len(must_update_headings) == 27
    assert evidence["diagnostics"]["symbol_confidence"] == "low"
    assert len(evidence["diagnostics"]["fallback_paths"]) == 3
    assert any(item["reason_code"] == "diff_symbol_parser_fallback" for item in report["section_candidates"]["review"])
