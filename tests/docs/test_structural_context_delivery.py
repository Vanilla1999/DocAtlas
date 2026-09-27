"""Original direct questions must receive complete canonical source blocks.

No retrieval hints, edited sources, answer text in runtime, or raised budgets.
"""
from eval.evidence_quality_v2.run import documents_for, load_protocol, audit_payload
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens


def _query(tmp_path, library, question):
    _, _, manifest = load_protocol()
    documents = documents_for(library, manifest)
    project = tmp_path / 'project'
    write_project(project, documents)
    with isolated_service(tmp_path / 'state') as (service, config):
        inventory = index_project(service, config, project)
        assert not inventory['excluded_or_failed_paths']
        result, trace = observe_call(service, {
            'question': question, 'project_path': str(project), 'scope': 'all',
        })
    assert audit_payload(result, trace['snapshot'], project) == []
    assert result['answer_supported'] is False
    assert result['edit_ready'] is False
    assert docs_context_budget_tokens(result) <= 800
    assert len(result['sources']) <= 3
    return result, documents


def test_original_fastapi_timing_question_gets_the_timing_rule(tmp_path):
    result, documents = _query(tmp_path, 'fastapi',
        'When do FastAPI background tasks run relative to returning the response?')
    fact = documents['docs/en/docs/tutorial/background-tasks.md'].splitlines()[2]
    assert any(fact in source['snippet'] for source in result['sources']), result


def test_original_httpx_question_gets_all_four_complete_definitions(tmp_path):
    result, documents = _query(tmp_path, 'httpx',
        'Назови четыре типа timeout в HTTPX и объясни, что ограничивает каждый.')
    text = documents['docs/advanced/timeouts.md']
    start = text.index('* The **connect**')
    end = text.index('\n\nYou can configure', start)
    complete_list = text[start:end]
    # All items must remain together, not just four keywords or disconnected prefixes.
    assert any(complete_list in source['snippet'] for source in result['sources']), result
