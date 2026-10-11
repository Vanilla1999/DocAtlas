import json
import pytest
from eval.evidence_quality_v2.cost import model_visible_text, count_input, summarize_usage, percentiles
from eval.evidence_quality_v2.answers import assess_answer, context_answer_matrix

class BytesEncoder:
    def encode(self, text, **kwargs): return list(text.encode())






@pytest.fixture
def record():
    case={'id':'a','project_group':'p','policy':{'version':'2'},'required_claims':[{'id':'approval','witness_sets':[{'parts':[{'text':'Deploy only after approval.'}]}]}]}
    payload={'sources':[{'evidence_id':'s','path_or_url':'a.md','snippet':'Deploy only after approval.'}]}
    return case,payload,{'a.md':{'project_group':'p','version':'2'}}




