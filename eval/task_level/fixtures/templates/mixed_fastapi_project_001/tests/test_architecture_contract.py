from __future__ import annotations

from pathlib import Path


def test_docs_define_admin_contract() -> None:
    security = Path("docs/security.md").read_text(encoding="utf-8")
    errors = Path("docs/api-errors.md").read_text(encoding="utf-8")

    assert "require_admin" in security
    assert "error" in errors
