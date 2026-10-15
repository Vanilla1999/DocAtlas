"""Split tests from test_docs_service.py; shared helpers remain in the façade module."""
from tests import _shared_test_docs_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})

def test_inspect_project_docs_recommends_architecture_bootstrap_when_no_docs(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.inspect_project_docs(str(project))

    assert result.reason_code == "no_project_docs"
    assert result.next_action["action"] == "create_reviewable_project_doc"
    assert result.next_action["type"] == "ask_user_to_create_project_doc"
    assert result.next_action["suggested_file"] == "ARCHITECTURE.md"
    assert result.next_action["handled_by"] == "coding_agent"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "repo_write"
    assert result.arguments_patch == {"project_path": str(project.resolve())}
    assert "No reviewable project docs" in (result.agent_message or "")
    assert "ARCHITECTURE.md" in (result.user_message or "")
    action = result.recommended_next_actions[-1]
    assert action["action"] == "create_reviewable_project_doc"
    assert action["requires_confirmation"] is True
    assert action["preferred_path"] == "ARCHITECTURE.md"
    assert "ARCHITECTURE.md" in action["suggested_paths"]
    assert [item["tool"] for item in action["after"]] == ["prepare_docs", "get_docs_context"]
    assert "reviewable ARCHITECTURE.md" in (result.agent_guidance or "")


def test_bootstrap_project_docs_stops_before_repo_write(tmp_path, monkeypatch):
    project = _flutter_project(tmp_path)
    service = _service_with_real_agent(tmp_path, monkeypatch)

    result = service.bootstrap_project_docs(str(project), question="Explain the architecture")

    assert result.status == "confirmation_required"
    assert result.reason_code == "no_project_docs"
    assert result.next_action["type"] == "ask_user_to_create_project_doc"
    assert result.requires_confirmation is True
    assert result.confirmation_reason == "repo_write"
    assert [action["tool"] for action in result.actions_taken] == ["inspect_project_docs"]












