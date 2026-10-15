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
        after=call_docs_tool_payload('get_docs_context',args,service)
        assert actual==before==after
        assert any('Deploy the release only after approval.' in row['snippet'] for row in actual['sources'])
        assert trace['observer_counts'] == {'retrieval_calls': 1, 'validation_calls': 1}
        assert trace['retired_stages'] == ['rankings', 'qualified_fragments', 'expansions']
        assert all(not trace['stages'][stage] for stage in trace['retired_stages'])
        flow=trace['finalization_observation']
        assert flow['observation'] == 'recorded'
        assert flow['event_count'] == flow['recorded_events'] + flow['omitted_events']
        assert flow['diagnostic_error_count'] == flow['serialization_omitted_events'] == 0
        assert not hasattr(service, '_same_call_diagnostics_observer')
        assert (project/'docs/deploy.md').read_bytes() == b'# Deployment\n\nDeploy the release only after approval.\n'
        assert len(trace['stages']['projector_inputs'])==1
        assert trace['stages']['retrieved_candidates']
        assert trace['stages']['query_window']
