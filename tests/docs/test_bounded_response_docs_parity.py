from pathlib import Path

from docmancer.mcp._docs_server_resources import MCP_RESOURCES


ROOT = Path(__file__).resolve().parents[2]


def test_response_note_preserves_public_omission_contract():
    note = (ROOT / "docs/mcp-response-contract.md").read_text(encoding="utf-8")
    quickstart = next(
        row["text"] for row in MCP_RESOURCES
        if row["uri"] == "docmancer://agent/quickstart"
    )
    assert 'omitted_counts' in quickstart
    assert 'status="truncated"' in quickstart
    assert '`omitted_counts`' in note
    assert "non-critical" in note
    assert "honor" in note.casefold()
    for field in ("status", "kind", "sources", "missing", "omitted_counts"):
        assert f"`{field}`" in note
    assert "no safe context" in note.casefold()
