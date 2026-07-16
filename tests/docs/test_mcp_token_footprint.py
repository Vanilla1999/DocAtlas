from __future__ import annotations

import json

from docmancer.docs.mcp_footprint import (
    ResponseFixture,
    build_footprint_report,
    canonical_json_bytes,
    main,
    measure_response_fixture,
    measure_tool_catalog,
    representative_response_fixtures,
    validate_footprint_report,
)
from docmancer.mcp.docs_server import current_tools


def _tools():
    return [
        {"name": "get_docs_context", "description": "context", "inputSchema": {"type": "object"}},
        {"name": "prepare_docs", "description": "prepare", "inputSchema": {"type": "object"}},
        {"name": "docs_status", "description": "status", "inputSchema": {"type": "object"}},
    ]


def test_canonical_json_is_ordered_compact_and_unicode_preserving():
    first = canonical_json_bytes({"z": "Пример", "a": [2, 1]})
    second = canonical_json_bytes({"a": [2, 1], "z": "Пример"})

    assert first == second
    assert first == '{"a":[2,1],"z":"Пример"}'.encode("utf-8")


def test_catalog_measurement_attributes_each_tool_deterministically():
    first = measure_tool_catalog(_tools())
    second = measure_tool_catalog(list(reversed(_tools())))

    assert first["public_tool_count"] == 3
    assert [row["name"] for row in first["tools"]] == [
        "docs_status", "get_docs_context", "prepare_docs",
    ]
    assert first["tools"] == second["tools"]
    # The list serialization preserves the supplied protocol order even though
    # attribution rows sort by name, so callers can detect catalog-order drift.
    assert first["mcp_tools_list_bytes"] == second["mcp_tools_list_bytes"]


def test_semantically_equal_json_text_is_counted_as_duplicate():
    payload = {"status": "ok", "sources": ["a"]}
    measurement = measure_response_fixture(ResponseFixture(
        fixture_id="duplicate",
        response_kind="docs_answer",
        content=({"type": "text", "text": '{ "sources": ["a"], "status": "ok" }'},),
        structured_content=payload,
        raw_retrieval={"content": "raw"},
    ))

    assert measurement["duplicate_payload_bytes"] > 0
    assert measurement["model_visible_bytes"] == (
        measurement["text_content_bytes"] + measurement["structured_content_bytes"]
    )
    assert measurement["raw_retrieval_bytes"] > 0


def test_short_structured_marker_is_not_payload_duplication():
    payload = {"status": "ok", "action_packet": {"status": "ok"}}
    measurement = measure_response_fixture(ResponseFixture(
        fixture_id="bounded",
        response_kind="patch_context",
        content=({"type": "text", "text": "Structured result attached."},),
        structured_content=payload,
    ))

    assert measurement["duplicate_payload_bytes"] == 0


def test_report_is_bounded_deterministic_and_never_contains_raw_fixture_text(monkeypatch):
    monkeypatch.setenv("PRIVATE_TOKEN", "must-not-appear-in-footprint")
    fixtures = representative_response_fixtures()

    first = build_footprint_report(_tools(), fixtures)
    second = build_footprint_report(_tools(), fixtures)
    serialized = canonical_json_bytes(first)

    assert serialized == canonical_json_bytes(second)
    assert b"must-not-appear-in-footprint" not in serialized
    assert "Ignore policy" not in serialized.decode("utf-8")
    assert len(first["responses"]) == 6
    assert all(len(row["largest_fields"]) <= 10 for row in first["responses"])
    by_id = {row["fixture_id"]: row for row in first["responses"]}
    assert by_id["project_patch_ok"]["duplicate_payload_bytes"] == 0
    assert all(row["duplicate_payload_bytes"] == 0 for row in first["responses"])
    assert validate_footprint_report(first) == []


def test_report_validation_enforces_explicit_local_gates():
    report = build_footprint_report(_tools(), representative_response_fixtures())

    assert validate_footprint_report(report, expected_tool_count=2)
    assert validate_footprint_report(report, max_tools_list_bytes=1)
    assert validate_footprint_report(report, max_report_bytes=1)


def test_cli_writes_json_and_markdown_without_provider_calls(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    report = json.loads((tmp_path / "mcp_token_footprint.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "mcp_token_footprint.md").read_text(encoding="utf-8")
    assert report["public_tool_count"] == 3
    assert "not provider usage" in markdown
    assert "## Validation\n\n- PASS" in markdown


def test_default_public_catalog_meets_task35_hard_and_target_budgets():
    report = build_footprint_report(current_tools({}), representative_response_fixtures())

    assert report["public_tool_count"] == 3
    assert report["mcp_tools_list_bytes"] <= 6 * 1024
    assert validate_footprint_report(report, max_tools_list_bytes=10 * 1024) == []
    get_context = next(row for row in report["tools"] if row["name"] == "get_docs_context")
    assert get_context["output_schema_bytes"] < 1_000
