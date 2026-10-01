"""Pre-evaluation checks for fresh FP32 pilot; no tuned quality assertions."""
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]/'experiments/language_aware_context'


def test_v2_tasks_have_no_v1_source_or_question_overlap():
    old=json.loads((ROOT/'pilot.tasks.json').read_text())
    new=json.loads((ROOT/'pilot_v2.tasks.json').read_text())
    p=json.loads((ROOT/'pilot_v2.protocol.json').read_text())
    p1=json.loads((ROOT/'pilot.protocol.json').read_text())
    assert len(new)==9 and len({t['id'] for t in new})==9
    assert not {t['question'] for t in old} & {t['question'] for t in new}
    assert not {s['blob'] for s in p1['sources']} & {s['blob'] for s in p['sources']}
    assert {lang:sum(t['query_language']==lang for t in new) for lang in ('ru','en','mixed')}=={'ru':3,'en':3,'mixed':3}
    assert sum(t['answerable'] for t in new)==7
    assert len({t['family'] for t in new})==3


def test_fp32_worker_has_no_quantization_and_has_real_health_gate():
    tree=ast.parse((ROOT/'pilot_fp32_agent.py').read_text())
    calls=[ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)]
    assert 'AutoModelForCausalLM.from_pretrained' in calls
    assert 'model.generate' in calls
    assert not any('quantize' in f for f in calls)
    source=(ROOT/'pilot_fp32_agent.py').read_text()
    assert source.index('failed disjoint health') < source.index('for line in sys.stdin:')
    assert 'torch_dtype=torch.float32' in source


def test_v2_uses_old_prompts_and_old_packing_not_new_flow():
    source=(ROOT/'pilot_v2_run.py').read_text()
    assert 'from .pilot_io import' in source
    assert 'flow_experiment' not in source
    protocol=json.loads((ROOT/'pilot_v2.protocol.json').read_text())
    old=json.loads((ROOT/'pilot.protocol.json').read_text())
    assert protocol['conditions']==old['conditions']
    assert protocol['budgets']==old['budgets']
    assert protocol['product_activation'] is False
