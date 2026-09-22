"""Project-file and normalized-text hashes are distinct trust domains."""

from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.project_context_quality.capture_public_context import capture_public_call
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens


QUESTION = "Which command starts the Docs MCP server"
NEEDLE = "doc-atlas mcp docs-serve"
BODY = f"# Docs MCP server\n\nThe command that starts the Docs MCP server is \`{NEEDLE}\`.\n"


def test_crlf_project_file_keeps_native_reference_evidence(tmp_path):
    root = tmp_path / "corpus"
    write_project(root, {"README.md": BODY})
    path = root / "README.md"
    # Reproduce the Windows representation on any OS: project freshness hashes
    # raw bytes while the indexed source snapshot is normalized text.
    path.write_bytes(BODY.replace("\n", "\r\n").encode("utf-8"))

    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        capture = capture_public_call(service, {
            "project_path": str(root),
            "scope": "project",
            "question": QUESTION,
        })

    payload = capture["public_payload"]
    visible = "\n".join(row["snippet"] for row in payload.get("sources") or ())
    assert NEEDLE in visible, payload
    assert docs_context_budget_tokens(payload) <= 800
    assert len(payload.get("sources") or ()) <= 3
    assert all(payload[key] is False for key in (
        "answer_supported", "answer_available", "edit_ready",
    ))
