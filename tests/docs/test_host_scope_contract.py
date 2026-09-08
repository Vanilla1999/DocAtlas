"""Host-visible scope intent and real project/module isolation are distinct."""
from copy import deepcopy

import jsonschema
import pytest

from docmancer.cli.commands import _get_template_content
from docmancer.mcp.agent_workflow_contract import public_agent_contract, runtime_public_tool_dicts
from docmancer.mcp.docs_server import call_docs_tool_payload
from tests._shared_test_docs_service import _flutter_project, _service_with_real_agent


def test_host_policy_distinguishes_onboarding_from_repo_policy():
    policy = public_agent_contract()["workflow"]["scope_planning"]
    assert policy["repository_overview_scope"] == "all"
    assert policy["repo_level_policy_scope"] == "project"
    assert policy["known_module_scope"] == "module"
    assert policy["module_path_implies_scope"] == "module"
    assert policy["all_requires_no_module_filter"] is True
    assert policy["explicit_scope_is_authoritative"] is True
    assert policy["all_is_repository_local"] is True
    assert policy["never_widen_project_to_all"] is True


def test_host_examples_validate_and_keep_distinct_scope_intents():
    contract = public_agent_contract()
    tools = {tool["name"]: tool for tool in runtime_public_tool_dicts()}
    examples = {row["id"]: row for row in contract["examples"]}
    for key, scope in (("repository-overview", "all"), ("repository-policy", "project"),
                       ("known-module", "module")):
        example = examples[key]
        args = example["arguments"]
        jsonschema.validate(args, tools["get_docs_context"]["inputSchema"])
        assert args["scope"] == scope
        assert args["project_path"] == "/repo"
        assert ("module_path" in args) == (scope == "module")
        assert args["question"]


def test_advertised_scope_explains_all_without_adding_a_default():
    tool = next(tool for tool in runtime_public_tool_dicts() if tool["name"] == "get_docs_context")
    scope = tool["inputSchema"]["properties"]["scope"]
    assert "repo-level docs only" in scope["description"]
    assert "repo-level plus modules" in scope["description"]
    assert "same repository" in scope["description"]
    assert "onboarding" in tool["description"]
    assert "explicit scope" in tool["description"]
    assert "default" not in scope
    assert scope["enum"] == ["project", "module", "all"]


@pytest.mark.parametrize("template", ["skill.md", "claude_code_skill.md", "claude_desktop_skill.md",
                                      "cursor_agents_md.md", "copilot_instructions.md", "project_bootstrap.md"])
def test_generated_host_guides_include_the_scope_decision(template):
    rendered = _get_template_content(template)
    for phrase in ('scope="all"', 'scope="project"', 'scope="module"', 'project_path',
                   'onboarding', 'explicit scope'):
        assert phrase in rendered


@pytest.mark.parametrize("scope,module_path,question,expected", [
    ("all", None, "Explain BackendOnlyAnswer.", "packages/backend/README.md"),
    ("project", None, "Explain BackendOnlyAnswer.", None),
    ("module", "packages/backend", "Explain SharedNeedle.", "packages/backend/README.md"),
    ("all", "packages/backend", "Explain SharedNeedle.", "packages/backend/README.md"),
    ("all", None, "Explain ForeignOnlyAnswer.", None),
])
def test_public_scope_never_implicitly_widens(tmp_path, monkeypatch, scope, module_path, question, expected):
    project = _flutter_project(tmp_path)
    (project / "README.md").write_text("# Root\n\nSharedNeedle RootOnlyAnswer.")
    for name in ("backend", "frontend"):
        module = project / "packages" / name
        module.mkdir(parents=True)
        (module / "README.md").write_text(f"# {name}\n\nSharedNeedle {name.title()}OnlyAnswer.")
    foreign_root = tmp_path / "foreign"
    foreign_root.mkdir()
    foreign = _flutter_project(foreign_root)
    (foreign / "README.md").write_text("# Foreign\n\nForeignOnlyAnswer is not owned by the requested project.")
    service = _service_with_real_agent(tmp_path, monkeypatch)
    for target in (project, foreign):
        assert service.ingest_project_docs(str(target), with_vectors=False).status == "success"
    request = {"question": question, "project_path": str(project), "scope": scope}
    if module_path:
        request["module_path"] = module_path
    before = deepcopy(request)
    payload = call_docs_tool_payload("get_docs_context", request, service)
    assert request == before
    paths = {s["path_or_url"] for s in payload.get("sources", [])}
    if expected:
        assert expected in paths, payload
    elif question == "Explain BackendOnlyAnswer.":
        assert not any(path.startswith("packages/") for path in paths)
    else:
        assert not paths, payload
    if module_path:
        assert paths == {"packages/backend/README.md"}
    assert payload.get("answer_supported") is not True
    assert payload.get("edit_ready") is not True
    assert len(paths) <= 3
    assert payload["estimated_tokens"] <= 800
