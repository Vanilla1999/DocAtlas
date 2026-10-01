from copy import deepcopy
import pytest
from eval.evidence_quality_v2.semantic import assess_context, normalize_markdown
from eval.evidence_quality_v2.trace import classify_first_loss, bounded_completeness, STAGES

@pytest.fixture
def example():
    case = {'id':'neutral', 'project_group':'forge', 'policy':{'version':'2','authority':'source_of_truth','lifecycle':'active'},
        'required_claims':[{'id':'permission','witness_sets':[{'parts':[{'text':'Deploy only after approval.'}]}],
        'contradiction_sets':[{'parts':[{'text':'Deploy without approval.'}]}]}]}
    registry = {p:dict(project_group='forge',version='2',authority='source_of_truth',lifecycle='active') for p in ('a.md','b.md')}
    source = dict(evidence_id='a',path_or_url='a.md',snippet='Deploy only after approval.',line_start=1,line_end=1)
    return case, registry, {'sources':[source]}

@pytest.mark.parametrize('path', ['a.md','b.md'])
def test_alternative_sources(example,path):
    case, registry, payload = example
    payload['sources'][0]['path_or_url'] = path
    assert assess_context(case,payload,registry)['context_sufficiency']=='sufficient'

@pytest.mark.parametrize('key,value', [('version','3'),('project_group','elsewhere'),('authority','historical'),('lifecycle','proposed')])
def test_policy_not_relevance(example,key,value):
    case, registry, payload = example
    registry['a.md'][key]=value
    result=assess_context(case,payload,registry)
    assert result['context_sufficiency']=='insufficient'
    assert result['rejected_sources']

@pytest.mark.parametrize('snippet,expected', [('Deploy without approval.','contradicted'),('Deploy only after approval.','supported'),('Deployment is subject to authorization.','needs_review'),('Deploy.','needs_review')])
def test_relation_and_review(example,snippet,expected):
    case, registry, payload=example
    payload['sources'][0]['snippet']=snippet
    assert assess_context(case,payload,registry)['claims']['permission']['status']==expected

def test_explicit_path(example):
    case, registry, payload=example
    case['allowed_paths']=['b.md']
    assert assess_context(case,payload,registry)['required_supported']==0

def test_partial_introduced_list(example):
    case, registry, payload=example
    case['required_claims'][0]['witness_sets']=[{'parts':[{'text':'Does not replace:'},{'text':'- compiler'},{'text':'- debugger'}],'same_source':True}]
    payload['sources'][0]['snippet']='Does not replace:\n- compiler'
    assert assess_context(case,payload,registry)['context_sufficiency']=='insufficient'
    payload['sources'][0]['snippet']+='\n- debugger'
    assert assess_context(case,payload,registry)['context_sufficiency']=='sufficient'

def test_formatting_only():
    assert normalize_markdown('| `kind` | `docs_context` |')==normalize_markdown('|kind|docs_context|')
    assert normalize_markdown('must not')!=normalize_markdown('must')


def test_separate_citations_support_one_fact_without_joined_quote(example):
    case, registry, payload = example
    case['required_claims'][0]['witness_sets'] = [{'parts': [
        {'path': 'a.md', 'text': 'Cells cannot contain blocks.\n\nBlank lines are required.',
         'line_start': 1, 'line_end': 3}]}]
    payload['sources'] = [dict(evidence_id='a', path_or_url='a.md',
        snippet='Cells cannot contain blocks.', line_start=1, line_end=1),
        dict(evidence_id='b', path_or_url='a.md', snippet='Blank lines are required.',
             line_start=3, line_end=3)]
    before = deepcopy(payload)
    result = assess_context(case, payload, registry)
    assert result['context_sufficiency'] == 'sufficient'
    assert result['claims']['permission']['supporting_witnesses'][0]['evidence_ids'] == ['a', 'b']
    bindings = result['claims']['permission']['supporting_witnesses'][0]['citation_bindings']
    assert [b['part']['text'] for b in bindings] == ['Cells cannot contain blocks.', 'Blank lines are required.']
    assert payload == before
    payload['sources'][1]['path_or_url'] = 'b.md'
    assert assess_context(case, payload, registry)['context_sufficiency'] != 'sufficient'
    payload['sources'][1]['path_or_url'] = 'a.md'
    payload['sources'].pop()
    assert assess_context(case, payload, registry)['context_sufficiency'] != 'sufficient'


def test_rendered_list_formatting(example):
    case, registry, payload = example
    case['required_claims'][0]['witness_sets'] = [{'parts': [
        {'text': 'Does not replace:\n- *compiler*\n- [debugger](https://example.invalid)'}]}]
    payload['sources'][0]['snippet'] = 'Does not replace:\n* compiler\n* debugger'
    assert assess_context(case, payload, registry)['context_sufficiency'] == 'sufficient'


@pytest.mark.parametrize('original,mutation', [
    ('at most 3 sources', 'at most 4 sources'),
    ('use docs_context', 'use docs_answer'),
    ('must not edit', 'must edit'),
    ('only after approval', 'after approval'),
    ('version 1.6.1', 'version 1.6.2'),
    ('" /-S"', '"/-S"'),
    ('` /-S`', '`/-S`'),
    ("' /-S'", "'/-S'"),
    ('```python\nif allowed:\n    deploy()\n```', '```python\nif allowed:\ndeploy()\n```'),
])
def test_meaning_mutations_are_not_formatting_equivalence(example, original, mutation):
    case, registry, payload = example
    case['required_claims'][0]['witness_sets'] = [{'parts': [{'text': original}]}]
    payload['sources'][0]['snippet'] = mutation
    result = assess_context(case, payload, registry)
    assert result['context_sufficiency'] != 'sufficient'
    assert result['required_supported'] == 0


@pytest.mark.parametrize('identity', ['mkdocs-06', 'uv-06'])
def test_saved_responses_support_requested_facts(identity):
    import json
    from pathlib import Path
    from eval.evidence_quality_v2.run import load_protocol, registry_for
    from eval.evidence_quality_v2.revised_gold import revised_case
    repo = Path(__file__).resolve().parents[2]
    _, cases, manifest = load_protocol()
    original = next(c for c in cases if c['id'] == identity)
    case = revised_case(original)
    assert case['question'] == original['question']
    wire = json.loads((repo / 'roadmap/search-quality-2026-10-01/audit/raw/external80/native' / f'{identity}.json').read_text())['wire']
    payload = wire.get('structuredContent') or json.loads(wire['content'][0]['text'])
    assert assess_context(case, payload, registry_for(case['project_group'], manifest))['context_sufficiency'] == 'sufficient'


def test_quote_integrity_remains_separate_from_semantic_equivalence(tmp_path):
    from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
    from eval.evidence_quality_v2.observer import observe_call
    from eval.evidence_quality_v2.audit import audit_payload
    project = tmp_path / 'project'
    write_project(project, {'docs/deploy.md': '# Deployment\n\nDeploy the release only after approval.\n'})
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, project)
        payload, trace = observe_call(service, dict(question='When may I deploy the release?', project_path=str(project), scope='all'))
    assert payload['sources']
    assert not audit_payload(payload, trace['snapshot'], project)
    import hashlib
    source = payload['sources'][0]
    assert source['content_sha256'] != hashlib.sha256((project / source['path_or_url']).read_bytes()).hexdigest()
    for key, value in [('snippet', source['snippet'] + ' Invented.'),
                       ('content_sha256', '0' * 64), ('evidence_id', 'not-bound'),
                       ('path_or_url', '../elsewhere.md')]:
        mutated = deepcopy(payload)
        mutated['sources'][0][key] = value
        assert audit_payload(mutated, trace['snapshot'], project), key

@pytest.mark.parametrize('lost', range(7))
def test_first_loss(lost):
    stages={name:dict(complete=True,presence='present' if i<lost else 'absent') for i,name in enumerate(STAGES)}
    assert classify_first_loss(stages)['stage']==STAGES[lost]

def test_truncated_trace_cannot_prove_loss():
    assert classify_first_loss({'source':dict(complete=True,presence='present')})['category']=='unobserved'
    assert bounded_completeness(3,8)=='truncated'
    assert bounded_completeness(3,None)=='unobserved'

def test_expanded_final_witness_is_not_reconstructed_from_old_index():
    assert classify_first_loss({'projection':dict(complete=True,presence='present')},literal_visible=False)['category']=='evaluator_mismatch'

def test_observer_is_transparent_and_one_call(tmp_path):
    from eval.evidence_quality_v2.runtime import write_project,isolated_service,index_project
    from eval.evidence_quality_v2.observer import observe_call
    from scripts.run_project_docs_self_host_gate import call_docs_tool_payload
    project=tmp_path/'project'
    write_project(project,{'docs/deploy.md':'# Deployment\n\nDeploy the release only after approval.\n'})
    with isolated_service(tmp_path/'state') as (service,config):
        index_project(service,config,project)
        args=dict(question='When may I deploy the release?',project_path=str(project),scope='all')
        before=call_docs_tool_payload('get_docs_context',args,service)
        actual,trace=observe_call(service,args)
        assert actual==before
        assert len(trace['stages']['projector_inputs'])==1
        assert trace['stages']['retrieved_candidates']
        assert trace['stages']['query_window']


def test_frozen_replay_uses_actual_prepared_projector_input(tmp_path):
    from eval.evidence_quality_v2.runtime import write_project,isolated_service,index_project
    from eval.evidence_quality_v2.observer import observe_call
    from docmancer.docs.application.docs_context_projection import project_docs_context
    from docmancer.docs.application.model_visible_projection import validate_model_visible_projection
    project=tmp_path/'project'
    write_project(project,{'docs/deploy.md':'# Deployment\n\nDeploy the release only after approval.\n'})
    with isolated_service(tmp_path/'state') as (service,config):
        index_project(service,config,project)
        actual,trace=observe_call(service,dict(question='When may I deploy the release?',project_path=str(project),scope='all'))
        raw=deepcopy(trace['stages']['projector_inputs'][0])
        assert isinstance(raw,dict)
        payload,snapshot=project_docs_context(retrieval=raw,max_tokens=800)
        assert payload==trace['stages']['projector_outputs'][0]['payload']
        assert not validate_model_visible_projection(payload,snapshot=snapshot,max_tokens=800)
