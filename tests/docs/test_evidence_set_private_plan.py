"""Internal probing must not become a second public question plan."""
from tests.docs._evidence_set_fixtures import capture_case


def test_internal_subquestions_do_not_duplicate_public_facets(tmp_path, monkeypatch):
    from docmancer.docs.application import docs_context_projection as projection
    calls = []
    original = projection._run_core
    def observe(**kwargs):
        calls.append(kwargs['max_tokens'])
        return original(**kwargs)
    monkeypatch.setattr(projection, '_run_core', observe)
    cap = capture_case(tmp_path, 'httpx-07')
    packet = cap['public_payload']
    assert len(calls) == 1, f'private-plan metadata triggered repeated full projection: {calls}'
    assert not any(f['id'].startswith(('independent-part:', 'composed-part:'))
                   for f in packet.get('facets', []))
    assert packet['sources'] and packet.get('read_next')
    assert packet['query_coverage'] != 'full'
    assert not packet['answer_supported']


def test_planning_keeps_unresolved_and_relation_fields_without_public_facet_ids():
    from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
    question = 'What is OrbitClient default timeout? Also identify the private deployment choice.'
    plan = build_documentation_query_plan(question)
    rows = [q for q in plan.queries if q.query_id.startswith('query-part-')]
    assert len(rows) == 2
    assert rows[0].need_relation == 'default'
    assert rows[0].need_subject == 'OrbitClient'
    assert all(q.facet_id is None and q.public_parent_query_id is None for q in rows)
    assert plan.unresolved_parts
