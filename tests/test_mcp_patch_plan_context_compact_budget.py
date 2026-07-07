import json
from pathlib import Path

from docmancer.docs.interfaces.mcp.project_tools import handle_project_tool
from docmancer.docs.service import LibraryDocsService


def test_patch_plan_context_compact_payload_is_bounded_and_without_debug_noise():
    root = Path(__file__).parent / "fixtures/patch_plan_context/nbo_menu"

    payload = handle_project_tool(
        "get_patch_plan_context",
        {
            "question": "Plan menu_line system_line menu_notifier menu_icon tab_icon bottom sheet",
            "project_path": str(root),
            "symbol_queries": ["MenuLine", "MenuIcon", "SystemLine", "MenuNotifier", "TabIcon"],
            "max_files": 5,
            "max_snippets": 4,
            "max_tokens": 400,
            "output_mode": "compact",
        },
        LibraryDocsService(),
    )

    assert payload is not None
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    assert len(encoded) <= 32_000
    assert payload["output_mode"] == "compact"
    assert "diagnostics" not in payload
    assert "debug" not in payload
    assert "schema_version" in payload
    assert "relevant_files" in payload
