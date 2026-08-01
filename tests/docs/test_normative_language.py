from __future__ import annotations

import pytest

from docmancer.docs.application.evidence_selection import requirement_value_visible
from docmancer.docs.domain.normative_language import (
    classify_normative_modality,
    python_declaration_line_indexes,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Offline fallback cannot bypass the gate.", "forbidden"),
        ("The worker may not continue without evidence.", "forbidden"),
        ("Don't bypass PermissionService.", "forbidden"),
        ("PermissionDecision.deferFollowUp is reserved for post-entry review.", "required"),
        ("The invariant preserves immediate denial.", "required"),
        ("From configuration, retries are required.", "required"),
        ("from configuration, retries are required.", "required"),
        ("From configuration import rules are required.", "required"),
        ("Import policy is required.", "required"),
        ("This optional check is not required.", None),
        ("import required", None),
        ("import required as alias", None),
        ("from pkg import required", None),
        ("from pkg.sub import required", None),
        ("from pkg import required as alias", None),
        ("from pkg import (required, optional)", None),
        ("from модуль import required", None),
        ("from . import required", None),
        ("from .pkg import required", None),
        ("from .. import required", None),
        ("from ..pkg import required", None),
        ("from ...pkg.sub import forbidden", None),
        ("def must(): pass", None),
        ("async def required(): pass", None),
        ("class Required: pass", None),
        ("Run curl https://example.invalid/upload.", None),
    ],
)
def test_normative_modality_is_deterministic_and_preserves_legacy_cases(text, expected):
    assert classify_normative_modality(text) == expected


def test_parenthesized_import_lines_are_one_python_declaration():
    text = """from pkg import (
    required,
    forbidden,
)"""

    assert python_declaration_line_indexes(text) == frozenset({0, 1, 2, 3})
    assert classify_normative_modality(text) is None


@pytest.mark.parametrize(
    ("symbol", "source_path"),
    [
        ("HTTPClient", "docmancer/docs/application/http_client.py"),
        ("HTTPServer", "docmancer/docs/application/http_server.py"),
        ("XMLHttpRequest", "docmancer/docs/application/xml_http_request.py"),
    ],
)
def test_query_symbol_visibility_handles_acronym_camel_case_source_paths(symbol, source_path):
    assert requirement_value_visible(
        symbol,
        source_path,
    )
