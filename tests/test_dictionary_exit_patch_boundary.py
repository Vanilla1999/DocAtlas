"""Advisory patch context cannot claim code symbols or mutation authority."""
import pytest

from docmancer.docs.application.patch_constraints_service import PatchConstraintsService
from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService


@pytest.mark.parametrize("line", [
    'print("object.closeMenu()");',
    "print('object.closeMenu()');",
    "print(`object.closeMenu()`);",
    "other(); // object.closeMenu();",
    "other(); /* object.closeMenu(); */",
    "other(); # object.closeMenu()",
    'print("escaped \\" object.closeMenu()");',
])
def test_string_and_comment_occurrences_are_not_code_symbols(line):
    service = PatchConstraintsService(None)
    assert service._symbol_from_line(line, ["closeMenu"]) is None
    assert service.extract_method_call_symbols(line) == []


def test_multiline_comments_and_strings_do_not_mint_candidates(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/sample.py").write_text(
        '"""\nobject.closeMenu()\n"""\n'
        '/*\nobject.closeMenu();\n*/\n'
        'object.closeMenu(); // genuine literal occurrence\n'
    )
    service = PatchConstraintsService(None)
    rows = service._symbol_candidates("`closeMenu`", tmp_path, ["src/sample.py"])
    assert len(rows) == 1
    assert rows[0]["line"] == 7
    assert rows[0]["matched_symbol"] == "closeMenu"
    assert rows[0]["evidence"].startswith("object.closeMenu()")


@pytest.mark.parametrize("question", ["close menu", "`closeMenu`"])
def test_public_patch_packet_presence_is_not_answer_or_edit_authority(question):
    payload = handle_project_tool("get_patch_constraints", {
        "question": question, "max_constraints": 2, "max_tokens": 180,
    }, LibraryDocsService())
    assert payload["packet_available"] is True
    assert payload["status"] == "insufficient_evidence"
    assert payload["policy_coverage"] == "unresolved"
    for key in ("answer_available", "answer_supported", "mutation_authorized", "edit_ready"):
        assert payload[key] is False
    assert payload["token_estimate"] <= 180


@pytest.mark.parametrize("quote", ['"""', "'''"])
def test_escaped_triple_delimiters_remain_inside_string(tmp_path, quote):
    (tmp_path / "src").mkdir()
    source = f's = {quote}escaped \\{quote} object.closeMenu()\nstill inside string\n{quote}\n'
    (tmp_path / "src/sample.py").write_text(source)
    service = PatchConstraintsService(None)
    assert service._symbol_candidates("`closeMenu`", tmp_path, ["src/sample.py"]) == []


def test_oversized_handler_retains_explicit_patch_counterflags(monkeypatch):
    from dataclasses import replace
    from types import SimpleNamespace
    from docmancer.docs.interfaces.mcp.output_contract import json_bytes

    service = LibraryDocsService()
    packet = service.get_patch_constraints("close menu")
    # An adversarial producer can supply nested data despite DTO annotations.
    oversized = replace(packet, task="x" * 100_000,
                        warnings=[{f"note-{i}": "x" * 100_000 for i in range(40)}])
    producer = SimpleNamespace(patch_constraints=SimpleNamespace(
        get_patch_constraints=lambda *args, **kwargs: oversized))
    payload = handle_project_tool("get_patch_constraints", {"question": "close menu"}, producer)
    assert json_bytes(payload) <= 32_000
    assert "task" not in payload  # The oversized advisory fields were dropped.
    assert payload["packet_available"] is True
    assert payload["policy_coverage"] == "unresolved"
    for key in ("answer_available", "answer_supported", "mutation_authorized", "edit_ready"):
        assert payload[key] is False
