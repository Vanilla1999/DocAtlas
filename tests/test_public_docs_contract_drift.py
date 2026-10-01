from pathlib import Path

import jsonschema

from docmancer.mcp.docs_server import current_tools

REPO = Path(__file__).resolve().parents[1]


def test_operational_job_calls_match_advertised_three_tool_contract():
    tools = {tool["name"]: tool for tool in current_tools()}
    assert set(tools) == {"get_docs_context", "prepare_docs", "docs_status"}
    jsonschema.validate({"action": "job", "job_id": "example"}, tools["docs_status"]["inputSchema"])
    jsonschema.validate({"action": "cancel_docs_job", "job_id": "example"}, tools["prepare_docs"]["inputSchema"])
    text = (REPO / "wiki/Architecture.md").read_text()
    assert 'docs_status(action="job", job_id=...)' in text
    assert 'prepare_docs(action="cancel_docs_job", job_id=...)' in text
    assert "Call `get_docs_job_status(job_id)`" not in text
    assert "in-memory dictionary of jobs" not in text


def test_project_context_instructions_use_evidence_not_certification_gate():
    text = (REPO / "docs/mcp-docs-server.md").read_text()
    assert "Project reads never produce `docs_answer`" in text
    assert "`sources`" in text and "`evidence_id`" in text
    assert "false answer flags do not prohibit" in text
    assert "does not authorize an edit" in text
    assert "The project answer contract requires" not in text
    assert "The host may answer only covered claims" not in text
    for path in ("docs/source-continuation.md", "docs/AGENT_DOCS_WORKFLOW.md"):
        guidance = (REPO / path).read_text()
        assert "snippets" in guidance and "semantic completeness" in guidance


def test_skill_uses_only_bounded_preparation_and_public_cancel_route():
    text = (REPO / "SKILL.md").read_text()
    assert "unbounded `next_action`" not in text
    assert 'prepare_docs(action="cancel_docs_job", job_id=...)' in text
    assert "evidence_ids" in text or "evidence_id" in text


def test_vector_troubleshooting_requires_explicit_degraded_opt_in():
    text = (REPO / "wiki/Troubleshooting.md").read_text()
    section = text.split('### `doc-atlas query --mode hybrid`', 1)[1].split("\n### ", 1)[0]
    assert "fail closed" in section
    assert "--allow-degraded" in section
    assert "does not" in section and "semantic retrieval success" in section
    assert "The dispatcher fell back to lexical because" not in section
