"""Project mutation validation must precede project-facade initialization."""
from types import SimpleNamespace

import pytest

from docmancer.mcp import _docs_server_part01 as dispatch
from docmancer.docs.application.project_docs_service import ProjectDocsService


def _request():
    return {"action": "sync_project_docs", "project_path": "/fixture/project",
        "mutation": {"operation": "sync_project_docs", "confirm": True,
            "storage_path": "/fixture/project/.docatlas/docatlas.db",
            "catalog_sha256": "a" * 64, "expected_generation_id": None,
            "documents": [{"path": "README.md", "content_sha256": "b" * 64,
                "catalog_entry_hash": "sha256:" + "c" * 64}]}}





