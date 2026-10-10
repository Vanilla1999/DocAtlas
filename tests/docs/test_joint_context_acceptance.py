"""Frozen direct questions through the real index, dispatcher and validator."""
import pytest
from eval.evidence_quality_v2.run import documents_for, load_protocol, audit_payload
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.observer import observe_call

CASES = [
    ('fastapi-original', 'fastapi',
     'When do FastAPI background tasks run relative to returning the response?'),
    ('httpx-original', 'httpx',
     'Назови четыре типа timeout в HTTPX и объясни, что ограничивает каждый.'),
    ('httpx-paraphrase-1', 'httpx',
     'What do connect, read, write, and pool timeouts each limit in HTTPX?'),
    ('httpx-paraphrase-2', 'httpx',
     'What is the difference between connect, read, write, and pool timeout limits?'),
    ('fastapi-paraphrase-1', 'fastapi',
     'Does FastAPI run background tasks before or after returning its response?'),
    ('fastapi-paraphrase-2', 'fastapi',
     'At what point in the response lifecycle are FastAPI background tasks executed?'),
]


def required_block(library, documents):
    # Test-only witnesses from the locked canonical corpus, never runtime terms.
    if library == 'fastapi':
        raw = documents['docs/en/docs/tutorial/background-tasks.md']
        return raw.splitlines()[2]
    raw = documents['docs/advanced/timeouts.md']
    start = raw.index('* The **connect**')
    end = raw.index('\n\nYou can configure', start)
    return raw[start:end]


@pytest.mark.parametrize('case_id,library,question', CASES,
                         ids=[c[0] for c in CASES])
def test_original_and_known_paraphrase_deliver_complete_block(
    tmp_path, case_id, library, question,
):
    _, _, manifest = load_protocol()
    documents = documents_for(library, manifest)
    project = tmp_path / 'project'
    write_project(project, documents)
    request = {'question': question, 'project_path': str(project), 'scope': 'all'}
    assert 'lookup_queries' not in request
    with isolated_service(tmp_path / 'state') as (service, config):
        inventory = index_project(service, config, project)
        assert not inventory['excluded_or_failed_paths']
        payload, trace = observe_call(service, request)
    assert audit_payload(payload, trace['snapshot'], project) == []
    assert payload['answer_supported'] is False
    assert payload['edit_ready'] is False
    block = required_block(library, documents)
    assert any(block in row['snippet'] for row in payload.get('sources', [])), {
        'case_id': case_id, 'request': request, 'payload': payload,
    }
