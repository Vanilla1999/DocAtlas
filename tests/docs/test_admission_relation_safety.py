"""Current-byte/pipeline contract."""
import json
from tests.docs.test_admission_relation_witnesses import CASES
from tests.docs._reference_binding_fixtures import capture_reference_case


def test_raw_owner_documents_and_private_meanings_never_leak_to_public_dto(tmp_path):
    q, _, body, *_ = CASES[0]
    cap = capture_reference_case(tmp_path, {'Guide.md':'# Rules\n\n'+body}, q)
    wire = json.dumps(cap['public_payload'])
    assert all(term not in wire for term in ('raw_document', '_admission_demands', 'need_witness_spans', '_reference_evidence'))
    from eval.agent_developer_v1.relation_source_context_controls import run_relation_source_context_controls
    run_relation_source_context_controls(tmp_path / 'current-source-context')
