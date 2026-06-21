from __future__ import annotations

from docmancer.docs.application.library_docs_service import _drop_low_value_library_section
from docmancer.docs.domain.quality import is_trivial_section


def test_trivial_heading_only_section_is_filtered():
    assert is_trivial_section("Developer Interface", title="Developer Interface") is True


def test_short_command_section_is_kept():
    assert is_trivial_section("doc-atlas mcp docs-serve", title="Command") is False


def test_short_code_signature_is_kept():
    assert is_trivial_section("def get_project_context(question: str) -> dict", title="API") is False


def test_empty_version_heading_is_filtered():
    assert is_trivial_section("0.4.6 - 2026-04-27", title="0.4.6 - 2026-04-27") is True


def test_library_docs_heading_only_section_is_filtered_in_selection_path():
    assert _drop_low_value_library_section("Developer Interface", title="Developer Interface") is True
