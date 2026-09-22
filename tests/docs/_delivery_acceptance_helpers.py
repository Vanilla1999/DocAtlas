"""Native delivery acceptance checks; the legacy rubric remains unchanged."""
from docmancer.docs.application.model_visible_projection_helpers import docs_context_budget_tokens
from tests.docs._evidence_set_fixtures import old_assessment


def assert_wire_constraints(capture):
    payload = capture['public_payload']
    assert docs_context_budget_tokens(payload) <= 800
    assert len(payload.get('sources', [])) <= 3
    assert all(payload[key] is False for key in
               ('answer_supported', 'answer_available', 'edit_ready'))


def assert_delivery(capture, case_id):
    assert_wire_constraints(capture)
    assert old_assessment(case_id, capture)['context_sufficiency'] == 'sufficient', (
        case_id, [(s['path_or_url'], s.get('line_start'), s.get('line_end'))
                  for s in capture['public_payload'].get('sources', [])])
