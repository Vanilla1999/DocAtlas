import copy
import pytest
from docmancer.docs.domain.evidence_qualification import qualify_evidence
from tests.docs._reference_binding_fixtures import capture_reference_case, visible


@pytest.mark.parametrize("name", ["VeloraGuide", "VELORAGUIDE", "veloraguide", "Z17Manual", "ARCADIA", "RunNotes", "ПАМЯТКА", "Порядок"])
@pytest.mark.parametrize("language", ["en", "ru"])
def test_locator_rename_preserves_command_without_body_change(tmp_path, name, language):
    question = (f"What installation command is documented in the file {name}?" if language == "en"
                else f"Какая installation command указана в файле {name}?")
    capture = capture_reference_case(tmp_path, {name+".md": "# Install\n\nInstallation command: run `atlas prepare`.\n"}, question)
    assert "atlas prepare" in visible(capture)


@pytest.mark.parametrize("command", ["velora bootstrap", "orion launch", "zed sync"])
def test_command_substitution_is_preserved(tmp_path, command):
    cap = capture_reference_case(tmp_path, {"Manual.md": f"# Install\n\nInstallation command: run `{command}`.\n"},
        "What installation command is documented in the file Manual?")
    assert command in visible(cap)


@pytest.mark.parametrize("name,expected", [("Foo.md", "upper prepare"), ("foo.md", "lower prepare")])
def test_exact_case_collision_keeps_document_identity(tmp_path, name, expected):
    cap = capture_reference_case(tmp_path, {
        "Foo.md": "# Installation\n\nInstallation command: run `upper prepare`.\n",
        "foo.md": "# Installation\n\nInstallation command: run `lower prepare`.\n",
    }, f"What installation command is documented in the file {name}?")
    assert expected in visible(cap)
    assert {s["path_or_url"] for s in cap["public_payload"]["sources"]} == {name}


def test_navigation_only_source_does_not_prove_a_fact(tmp_path):
    cap = capture_reference_case(tmp_path, {"Manual.md": "# Installation\n\n- [Installation command](command.md)\n"},
        "What installation command is documented in the file Manual?")
    assert not cap["public_payload"].get("sources")


def test_other_project_index_does_not_invalidate_selected_source(tmp_path):
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from eval.project_context_quality.capture_public_context import capture_public_call
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
    root = tmp_path/"wanted"
    other = tmp_path/"other"
    write_project(root, {"Guide.md": "# Install\n\nInstallation command: run `atlas prepare`.\n"})
    write_project(other, {"Guide.md": "# Install\n\nInstallation command: run `foreign prepare`.\n"})
    with isolated_service(tmp_path/"state") as (service, config):
        index_project(service, config, root)
        index_project(service, config, other)
        capture = capture_public_call(service, dict(project_path=str(root), scope="project",
            question="What installation command is documented in the file Guide?"))
    assert "atlas prepare" in visible(capture) and "foreign prepare" not in visible(capture)
    payload = capture["public_payload"]
    assert docs_context_budget_tokens(payload) <= 800
    assert validate_model_visible_projection(payload, snapshot=capture["projection_attempts"][-1]["snapshot"], max_tokens=800) == []


def test_forged_heading_trace_does_not_authorize_sibling(tmp_path):
    capture = capture_reference_case(tmp_path, {"Tasks.md":
        "# QueueTasks\n\nQueueTasks groups tasks.\n\n## OtherTasks\n\nTasks execute in order. Later tasks stop on error.\n"
    }, "What happens to OtherTasks when later tasks stop on error?")
    rows = capture["projection_attempts"][0]["before_projection"]["context_pack"]
    source = next(copy.deepcopy(row) for row in rows if "OtherTasks" in str(row.get("content") or ""))
    source["heading_path"] = source["section"] = "QueueTasks"
    probe = {"query_text": "When do QueueTasks stop?", "query_terms": ["tasks", "stop", "error"],
        "bound_subjects": ["queuetasks"], "bound_subject_context": "QueueTasks"}
    result = qualify_evidence(probe, query_id="query-original", evidence_text=source["content"], visible_text=source["content"], candidate=source)
    assert not result.qualified
