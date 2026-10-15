"""Related quotes need their canonical intervening explanation, not more budget."""
from eval.evidence_quality_v2.run import audit_payload, documents_for, load_protocol
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.observer import observe_call


def test_index_restriction_and_cause_arrive_together_in_first_packet(tmp_path):
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c['id'] == 'uv-04')
    root = tmp_path / 'project'
    write_project(root, documents_for('uv', manifest))
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, root)
        payload, trace = observe_call(service, {
            'question': case['question'], 'project_path': str(root), 'scope': 'all',
        })
    required = case['required_claims'][0]['witness_sets'][0]['parts'][0]['text']
    assert any(required in s['snippet'] for s in payload.get('sources', [])), payload
    assert audit_payload(payload, trace['snapshot'], root) == []
    assert payload['answer_supported'] is False and payload['edit_ready'] is False
