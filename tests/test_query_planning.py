from __future__ import annotations

import subprocess
import sys

import pytest

from docmancer.docs.application.evidence_selection import build_requirements
from docmancer.retrieval.query_planning import (
    MAX_EXACT_TERMS,
    build_query_plan,
    extract_document_locator,
    extract_exact_terms,
    is_exact_technical_token,
    compile_backend_filters,
    metadata_matches_filters,
)


@pytest.mark.parametrize("modules", [
    ("docmancer.retrieval.contracts", "docmancer.docs"),
    ("docmancer.docs", "docmancer.retrieval.contracts"),
])
def test_public_packages_import_in_fresh_processes(modules):
    result = subprocess.run(
        [sys.executable, "-c", "; ".join([
            *(f"import {module}" for module in modules),
            "from docmancer.docs import LibraryDocsService",
            "from docmancer.docs.service import LibraryDocsService as Service",
            "assert LibraryDocsService is Service",
        ])], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr














