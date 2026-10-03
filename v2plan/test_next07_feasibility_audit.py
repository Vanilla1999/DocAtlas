"""Verify the diagnostic, never label absent recovery as acceptance PASS."""
from v2plan.next07_feasibility_audit import audit


def test_audit_reports_missing_event_frame_and_consumer_rejection():
    report = audit()
    assert report['verdict'] == 'BLOCKED'
    assert report['examples'][0]['part_frames'][1] is None
    assert report['applicability_matrix_default_exception'] == [[True, False], [True, False]]
    assert len(report['not_run']) == 4


def test_audit_preserves_original_question_offsets():
    for example in audit()['examples']:
        question = example['question']
        for need in example['retrieval_needs']:
            assert question[need['query_span_start']:need['query_span_end']] == need['query_span_text']
        for contract in example['contracts']:
            for span in contract['constraint_spans']:
                assert 0 <= span['start'] < span['end'] <= len(question)
