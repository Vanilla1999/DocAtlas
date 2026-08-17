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
