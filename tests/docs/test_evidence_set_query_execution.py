"""Count real dispatcher calls and returned source bytes, not recorder summaries."""
from copy import deepcopy
from docmancer.retrieval.dispatch import RetrievalDispatcher
from tests.docs._evidence_set_fixtures import capture_case


def test_native_composition_question_searches_the_named_concept(tmp_path, monkeypatch):
    calls = []
    actual = RetrievalDispatcher.run
    def record(self, query, **kwargs):
        result = actual(self, query, **kwargs)
        calls.append((query, deepcopy(kwargs), [c.text for c in result.chunks]))
        return result
    monkeypatch.setattr(RetrievalDispatcher, 'run', record)
    capture = capture_case(tmp_path, 'fastapi-06')
    focal = [entry for entry in calls if entry[0] == 'origin']
    assert focal, [(q, k.get('filters')) for q,k,_ in calls]
    assert any('protocol' in text and 'port' in text for _,_,rows in focal for text in rows)
    # Preserve both existing root filter policies, count them honestly.
    root_question = 'Из каких компонентов состоит origin в CORS?'
    roots = [k for q,k,_ in calls if q == root_question]
    assert len(roots) == 2
    assert any(k['filters'].get('authority') == 'source_of_truth' for k in roots)
    root_filters = {k:v for k,v in roots[0]['filters'].items() if k != 'authority'}
    assert all({k:v for k,v in opts['filters'].items() if k != 'authority'} == root_filters
               for _,opts,_ in calls)
    assert len(calls) <= 14
    assert len({(q, str(sorted(opts['filters'].items())), opts['limit'], opts['budget'], opts['expand'])
                for q,opts,_ in calls}) == len(calls)
    assert all(capture['public_payload'][k] is False for k in
               ('answer_supported','answer_available','edit_ready'))


def test_scheduling_does_not_promote_legacy_probe_and_trigger_a_second_rescue(tmp_path, monkeypatch):
    # Captured BASE makes seven calls. New metadata must not promote its old
    # requirement-only probe into an extra planned context/rescue direction.
    calls=[]
    actual=RetrievalDispatcher.run
    def record(self,query,**kwargs):
        calls.append((query,kwargs))
        return actual(self,query,**kwargs)
    monkeypatch.setattr(RetrievalDispatcher,'run',record)
    capture_case(tmp_path,'fastapi-10')
    assert len(calls)<=7, [(q,kw['budget']) for q,kw in calls]
