import json
from pathlib import Path
R=Path('/tmp/opencode/acq-pilot'); out=[]
for corpus in ('L0','L2'):
    observed=json.loads((R/f'observation-{corpus}-v0-P1.json').read_text())
    replay=json.loads((R/f'candidates-{corpus}-v0-P1.json').read_text())
    search=[x for x in observed['events'] if x['stage']=='search_rows']
    qualify=[x for x in observed['events'] if x['stage']=='qualification']
    out.append({'corpus':corpus,'question':'P1','variant':'v0','lane_comparisons':[{'text_equal':a['query']==b['text'],'ordered_ids_equal':a['ordered_ids']==b['ordered_ids'],'actual_filters':a['filters'],'diagnostic_filters':b['filters'],'filter_shape_difference':'single-value IN versus scalar equality'} for a,b in zip(search,replay['lanes'])], 'qualification_counts':[{'before':len(q['before']),'after':len(q['after'])} for q in qualify]})
(R/'observation-comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
