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
