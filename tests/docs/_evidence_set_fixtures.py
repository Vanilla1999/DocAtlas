"""Real indexed fixture; case labels stay entirely in the evaluator."""
from pathlib import Path
from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for, audit_payload
from eval.evidence_quality_v2.runtime import write_project, isolated_service, index_project
from eval.evidence_quality_v2.observer import observe_call
from eval.evidence_quality_v2.semantic import assess_context


def capture_case(tmp_path: Path, case_id: str, *, question: str | None = None) -> dict:
    _, cases, manifest = load_protocol()
    case = next(c for c in cases if c['id'] == case_id)
    root = tmp_path / 'corpus'
    write_project(root, documents_for(case['project_group'], manifest))
    with isolated_service(tmp_path / 'state') as (service, config):
        index_project(service, config, root)
        payload, trace = observe_call(service, {
            'project_path': str(root), 'scope': 'all',
            'question': case['question'] if question is None else question,
        })
    errors = audit_payload(payload, trace['snapshot'], root)
    assert errors == [], errors
    return {'public_payload': payload, 'trace': trace, 'manifest': manifest}


def old_assessment(case_id: str, capture: dict) -> dict:
    _, cases, _ = load_protocol()
    case = next(c for c in cases if c['id'] == case_id)
    return assess_context(case, capture['public_payload'],
                          registry_for(case['project_group'], capture['manifest']))
