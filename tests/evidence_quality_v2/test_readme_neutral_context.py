"""Neutral metamorphic controls, separate from the 80 real README tasks."""
from copy import deepcopy
from pathlib import Path
import pytest
from tests.test_named_document_context_integration import _named_document_service
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.run import audit_payload as integrity
from docmancer.docs.application.docs_context_projection import project_docs_context
from docmancer.docs.application.model_visible_projection import _refresh_estimate, validate_model_visible_projection
from docmancer.docs.interfaces.mcp.context_tools import _omit_nullable_reason_code


def capture(service, request):
    payload, trace = observe_call(service, request)
    trace['projector_call_inputs'] = [{'retrieval': value} for value in trace['stages']['projector_inputs']]
    return payload, trace


def replay(frozen, variant):
    assert variant == 'A_current'
    payload, snapshot = project_docs_context(**deepcopy(frozen))
    _omit_nullable_reason_code(payload)
    _refresh_estimate(payload)
    return payload, {'validator_errors': validate_model_visible_projection(payload, snapshot=snapshot, max_tokens=800)}

TEXT = '''# Pebble

Pebble is a Python package for creating beautiful command line interfaces
in a composable way with as little code as necessary. It provides defaults.

Pebble in three points:

- Arbitrary nesting of commands
- Automatic help page generation
- Lazy loading of subcommands at runtime
'''
CASES = [
    ('What kind of interfaces does Pebble create, and how is it intended to compose them?',
     'command line interfaces\nin a composable way'),
    ('Перечисли все три возможности Pebble из списка Pebble in three points.',
     'Pebble in three points:\n\n- Arbitrary nesting of commands\n- Automatic help page generation\n- Lazy loading of subcommands at runtime'),
]


@pytest.mark.parametrize('question,expected',CASES)
def test_retrieved_safe_context_survives_unknown_question_class(tmp_path,monkeypatch,question,expected):
    service,root=_named_document_service(tmp_path,monkeypatch,['README.md'],{'README.md':TEXT})
    payload,trace=capture(service,{'question':question,'project_path':root,'scope':'all'})
    assert any(expected in s['snippet'] for r in trace['stages']['retrieved_candidates'] for s in r['sources'])
    assert payload.get('context_available') is True
    assert any(expected in s['snippet'] for s in payload['sources'])
    assert not integrity(payload,trace['snapshot'],Path(root))
    assert payload['answer_supported'] is payload['answer_available'] is payload['edit_ready'] is False
    assert payload['retrieval_coverage']=='partial'
    assert 'query-original' not in payload['covered_query_ids']


@pytest.mark.parametrize('change', ['project','stale','freshness','risk','lifecycle'])
def test_hint_context_does_not_bypass_candidate_safety(tmp_path,monkeypatch,change):
    service,root=_named_document_service(tmp_path,monkeypatch,['README.md'],{'README.md':TEXT})
    base,trace=capture(service,{'question':CASES[0][0],'project_path':root,'scope':'all',
                              'lookup_queries':['interfaces']})
    assert base['context_available'] is True
    frozen=deepcopy(trace['projector_call_inputs'][0])
    assert frozen['retrieval']['context_pack'], 'safety control requires nonempty candidates'
    for source in frozen['retrieval']['context_pack']:
        if change=='project': source['project_identity']='other-project'
        elif change=='stale': source['stale']=True
        elif change=='freshness': source['index_freshness']='unsynchronized'
        elif change=='risk': source['risk_flags']=['untrusted_content']
        elif change=='lifecycle': source['lifecycle_status']='historical'
    payload,proof=replay(frozen,'A_current')
    assert not payload.get('context_available')
    assert payload['answer_supported'] is False
    assert not proof['validator_errors']


def test_foreign_project_same_path_never_enters_owned_context(tmp_path,monkeypatch):
    from contextlib import closing
    import hashlib
    import json

    from docmancer.docs.application.project_docs_member_transaction import local_project_identity
    from tests._fixture_member_transaction import fixture_member_mutation

    service,root=_named_document_service(tmp_path,monkeypatch,['README.md'],{'README.md':'# Owned\n\nOnly owned facts are available.\n'})
    foreign=tmp_path/'foreign';foreign.mkdir();(foreign/'README.md').write_text(TEXT)
    (foreign/'docatlas.project-docs.yaml').write_text((Path(root)/'docatlas.project-docs.yaml').read_text())
    policy = service.member_storage_policy
    previous_generation = policy.generation()
    assert previous_generation is not None
    original = {Path(root): (Path(root) / 'README.md').read_bytes(),
                foreign: (foreign / 'README.md').read_bytes()}
    mutation = fixture_member_mutation(
        service, foreign, ('README.md',), expected_generation_id=previous_generation,
    )
    result = service.sync_project_docs(str(foreign), mutation=mutation)
    assert result.status == 'success'
    assert result.diagnostics['mode'] == 'member_upsert'
    assert result.diagnostics['vector_sync'] == {'status': 'not_requested'}
    metrics = result.diagnostics['metrics']
    assert metrics['members'] == metrics['new_count'] == 1
    assert metrics['changed_count'] == metrics['sources_deleted'] == 0
    assert metrics['generation_id'] == policy.generation() != previous_generation
    assert policy.validate(foreign, mutation['storage_path'])
    with closing(policy.connect()) as conn:
        rows = conn.execute(
            'SELECT source, content, content_hash, metadata_json FROM generation_sources '
            'WHERE generation_id = ? ORDER BY source', (metrics['generation_id'],),
        ).fetchall()
    assert {row['source'] for row in rows} == {str(project / 'README.md') for project in original}
    for project, data in original.items():
        row = next(row for row in rows if row['source'] == str(project / 'README.md'))
        metadata = json.loads(row['metadata_json'])
        digest = hashlib.sha256(data).hexdigest()
        assert row['content'].encode('utf-8') == data == (project / 'README.md').read_bytes()
        assert row['content_hash'] == digest
        assert metadata['project_doc_content_hash'] == 'sha256:' + digest
        assert metadata['project_doc_catalog_entry_hash'] == mutation['documents'][0]['catalog_entry_hash']
        assert metadata['project_identity'] == local_project_identity(project)
        assert metadata['project_path'] == str(project)
        assert metadata['project_doc_path'] == 'README.md'
        assert metadata['source_class'] == 'project_file'
    assert local_project_identity(Path(root)) != local_project_identity(foreign)
    payload,trace=capture(service,{'question':CASES[0][0],'project_path':root,'scope':'all'})
    assert not any('Pebble' in s['snippet'] for s in payload.get('sources',[]))
    assert not integrity(payload,trace['snapshot'],Path(root))


@pytest.mark.parametrize('question,expected',CASES)
def test_lookup_identical_to_original_is_not_a_new_requirement(tmp_path,monkeypatch,question,expected):
    service,root=_named_document_service(tmp_path,monkeypatch,['README.md'],{'README.md':TEXT})
    args={'question':question,'project_path':root,'scope':'all'}
    base,base_trace=capture(service,args)
    duplicate,trace=capture(service,{**args,'lookup_queries':[question]})
    assert base['context_available'] is True
    assert duplicate==base
    assert trace['observer_counts']==base_trace['observer_counts']

@pytest.mark.parametrize('lookup',['Pebble must not refresh','pebble must refresh','Pebble must refresh v2'])
def test_distinct_lookup_retains_its_own_direction(lookup):
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    plan=build_documentation_query_plan('Pebble must refresh',lookup_queries=(lookup,))
    assert any(q.origin=='host_lookup' and q.text==lookup for q in plan.queries)


@pytest.mark.parametrize("question", [
    "Как Pebble отправляет сообщения через квантовый канал?",
    "Как Pebble Pebble отправляет сообщения через квантовый канал?",
])
def test_name_only_hint_does_not_establish_an_unknown_topic(tmp_path, monkeypatch, question):
    service, root = _named_document_service(tmp_path, monkeypatch, ["README.md"], {"README.md": TEXT})
    answer, trace = capture(service, {"question": question, "project_path": root, "scope": "all"})
    # Retrieval really found the owned document. Only the subject matches;
    # source eligibility does not establish relevance to this new allegation.
    assert trace["stages"]["retrieved_candidates"]
    assert not answer.get("context_available"), answer
    assert not answer["answer_supported"]
    assert not integrity(answer, trace["snapshot"], Path(root))
