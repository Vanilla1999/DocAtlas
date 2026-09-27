"""Literal probes must fit both the requested count and exact-parser span."""
import pytest
from docmancer.docs.domain.query_terms import documentation_technical_anchors,documentation_exact_terms

@pytest.mark.parametrize('limit',[1,2,3,4,12])
def test_literal_respects_requested_limit(limit):
    q=' '.join(f'cache-tool --zone r{i}' for i in range(20))
    assert len(documentation_technical_anchors(q,limit=limit))<=limit

def test_overlong_literal_is_not_admitted_without_exact_constraint():
    question='tool-'+('a'*140)+' --zone '+('b'*60)
    literals=[x for x in documentation_technical_anchors(question) if x.startswith('`')]
    assert all(any(t.value==x[1:-1] for t in documentation_exact_terms(x)) for x in literals)
