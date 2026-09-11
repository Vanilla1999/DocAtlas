import pytest
from eval.evidence_quality_v2.documentation_audit import approved_set_present


def test_approved_span_is_not_a_universal_source_gap_claim():
    documents = {'first.md': 'Same fact.\n', 'alternative.md': 'Header\nSame fact.\n'}
    primary = {'parts': [{'path': 'missing.md', 'text': 'Same fact.', 'line_start': 1, 'line_end': 1}]}
    alternate = {'parts': [{'path': 'alternative.md', 'text': 'Same fact.', 'line_start': 2, 'line_end': 2}]}
    assert not approved_set_present(primary, documents)
    assert approved_set_present(alternate, documents)
    assert not approved_set_present({'parts': []}, documents)
    assert approved_set_present({'parts': [{'path': 'first.md', 'text': documents['first.md']}]}, documents)
    assert not approved_set_present({'parts': [{'path': 'first.md', 'text': 'Missing fact.'}]}, documents)


@pytest.mark.parametrize('change', ['negation', 'line', 'missing_part'])
def test_documentation_audit_preserves_occurrence_and_required_parts(change):
    document = 'Deploy only after approval.\nRecord the accepted version.\n'
    parts = [dict(path='a.md', text='Deploy only after approval.', line_start=1, line_end=1),
             dict(path='a.md', text='Record the accepted version.', line_start=2, line_end=2)]
    assert approved_set_present({'parts': parts}, {'a.md': document})
    if change == 'negation':
        parts[0]['text'] = 'Deploy without approval.'
    elif change == 'line':
        parts[0].update(line_start=2, line_end=2)
    else:
        parts[1]['text'] = 'Sign a missing receipt.'
    assert not approved_set_present({'parts': parts}, {'a.md': document})
