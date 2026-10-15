"""Count real dispatcher calls and returned source bytes, not recorder summaries."""
from copy import deepcopy
from docmancer.retrieval.dispatch import RetrievalDispatcher
from tests.docs._evidence_set_fixtures import capture_case


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
