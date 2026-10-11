"""Split test module; helpers live in _shared_test_docs_impact_task20.py."""
from tests.docs import _shared_test_docs_impact_task20 as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

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




def test_stale_section_schema_is_not_used_as_current_truth(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "ARCHITECTURE.md").write_text("# Architecture\n\nUse `issue_token`.\n", encoding="utf-8")
    reader = _indexed_reader(root, tmp_path / "index.db", schema="project-sections-old")

    indexed = reader.read(root)

    assert indexed["ARCHITECTURE.md"]["status"] == "stale"
    assert indexed["ARCHITECTURE.md"]["reason_code"] == "indexed_section_schema_stale"


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




def test_unrelated_unsupported_doc_does_not_make_every_diff_incomplete(tmp_path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Project\n", encoding="utf-8")
    (root / "docs" / "legacy.rst").write_text("Legacy\n======\n", encoding="utf-8")

    report = analyze_docs_impact(root, ["src/unrelated.py"])

    assert report["bounds"]["analysis_complete"] is True
    assert report["section_metadata"]["unsupported"] == []
    assert not any(item["path"] == "docs/legacy.rst" for item in report["impacts"])

