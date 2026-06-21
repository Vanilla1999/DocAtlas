from __future__ import annotations

from docmancer.docs.domain.quality import looks_like_code_or_command


def test_markdown_prose_with_bold_is_not_code_snippet():
    assert looks_like_code_or_command("The primary **Docmancer Docs pipeline** fetches documentation.") is False


def test_python_class_snippet_is_code():
    assert looks_like_code_or_command("from pydantic import BaseModel\nclass User(BaseModel):\n    pass") is True


def test_cli_command_is_code_or_command():
    assert looks_like_code_or_command("doc-atlas mcp docs-serve") is True


def test_decorator_api_example_is_code():
    assert looks_like_code_or_command('@app.get("/")\ndef read_root():\n    return {}') is True
