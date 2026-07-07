from __future__ import annotations

import json

from docmancer.docs.interfaces.mcp.output_contract import compact_mcp_payload, normalize_output_mode, paginate_context_items


def _bytes(payload: dict) -> int:
    return len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))


def test_compact_mcp_payload_keeps_context_pack_summaries_when_content_is_huge() -> None:
    payload = {
        "status": "success",
        "tool": "get_project_context",
        "context_pack": [
            {
                "path": f"docs/{index}.md",
                "title": f"Doc {index}",
                "heading_path": ["Root", f"Section {index}"],
                "source_class": "project_doc",
                "freshness": "current",
                "token_estimate": 10_000,
                "why_selected": "matched query",
                "line_start": 10,
                "line_end": 50,
                "score": 0.9,
                "content": "x" * 40_000,
            }
            for index in range(4)
        ],
        "supporting_snippets": [{"path": "docs/0.md", "snippet": "y" * 20_000}],
        "warnings": [],
    }

    compact = compact_mcp_payload(payload, max_bytes=12_000, tool="get_project_context", page_size=2)

    assert _bytes(compact) <= 12_000
    assert compact["context_pack"]
    assert compact["context_pack"][0]["path"] == "docs/0.md"
    assert compact["context_pack"][0]["content_omitted"] is True
    assert "content" not in compact["context_pack"][0]
    assert compact["mcp_compaction"]["truncated"] is True
    assert compact["mcp_compaction"]["next_page"] == 2
    assert "Retry with page=2" in compact["mcp_compaction"]["guidance"]
    assert any(warning["code"] == "mcp_compact_output_truncated" for warning in compact["warnings"])


def test_paginate_context_items_returns_distinct_pages() -> None:
    items = [{"path": f"docs/{index}.md"} for index in range(5)]

    first = paginate_context_items(items, page=1, page_size=2)
    second = paginate_context_items(items, page=2, page_size=2)

    assert first["items"] == [{"path": "docs/0.md"}, {"path": "docs/1.md"}]
    assert second["items"] == [{"path": "docs/2.md"}, {"path": "docs/3.md"}]
    assert first["next_page"] == 2
    assert second["next_page"] == 3


def test_normalize_output_mode_shared_details_fallback() -> None:
    assert normalize_output_mode({"details": True}, details_fallback=True) == "debug"
    assert normalize_output_mode({"output_mode": "full"}) == "full"
    assert normalize_output_mode({"output_mode": "wat"}) == "answer"
