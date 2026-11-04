import difflib,hashlib,json
from pathlib import Path
R=Path('/tmp/opencode/acq-pilot'); D=R/'acquire-stage'
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''): h.update(chunk)
    return h.hexdigest()
old=D/'candidates-original-reconstructed.py'; current=R/'candidates.py'
diff=''.join(difflib.unified_diff(old.read_text().splitlines(keepends=True),current.read_text().splitlines(keepends=True),fromfile='candidates-original-reconstructed.py',tofile='../candidates.py'))
(D/'candidates-original-to-modified.patch').write_text(diff)
raws=sorted(R.glob('candidates-L[02]-v[05]-P[123].json'))
mapping={'note':'Reconstructed initial scalar version from the recorded tool patch in this session by reversing the sole subsequent edit; no independent initial file hash was recorded before SQL results, so exact byte identity cannot be independently established. Existing raw outputs were collected before scalar-to-IN edit. The modified script was not the version used for collection.','initial_reconstructed_path':str(old),'initial_reconstructed_sha256':sha(old),'modified_path':str(current),'modified_sha256':sha(current),'patch':str(D/'candidates-original-to-modified.patch'),'raw_artifacts':[{'path':str(p),'sha256':sha(p)} for p in raws]}
(D/'script-provenance.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2))
data=[]
for p in sorted(D.glob('acquired-*.json')):
    obj=json.loads(p.read_text()); lanes=[]
    prior=json.loads((R/f'candidates-{obj["corpus"]}-{obj["variant"]}-{obj["question_id"]}.json').read_text())
    for x,old_lane in zip(obj['lanes'],prior['lanes']):
        before=x['before'][0];after=x['after'];reported=after['reported_acquisition']
        lanes.append({'name':x['name'],'expand':x['arguments']['expand'],'before_count':before['count'],'before_estimated_tokens':before['estimated_tokens'],'before_text_bytes':before['text_bytes'],'after_count':after['count'],'after_estimated_tokens':after['estimated_tokens_from_rows'],'after_text_bytes':after['text_bytes_from_rows'],'reported_acquisition':reported,'seconds':x['seconds'],'expansion_observation_count':sum(e['stage']=='expansion' for e in x['before']),'sql_order_equal_prior_scalar_filter_probe':before['ordered_stable_ids']==old_lane['ordered_ids']})
    item={'file':str(p),'sha256':sha(p),'corpus':obj['corpus'],'variant':obj['variant'],'question_id':obj['question_id'],'active_generation':obj['active_generation'],'union_count':len(obj['ordered_union_section_ids']),'concat_count':len(obj['ordered_concat_section_ids']),'lanes':lanes}
    if (obj['corpus'],obj['variant'],obj['question_id'])==('L0','v0','P1'):
        observed=json.loads((R/'acquire-observed-L0-v0-P1.json').read_text())['events']
        item['p1_observed_store_parameter_and_order_comparison']=[{'text_equal':x['arguments']['text']==y['text'],'expand_equal':x['arguments']['expand']==y['expand'],'filters_equal':x['arguments']['filters']==y['filters'],'section_order_equal':x['ordered_section_ids']==y['ordered_section_ids']} for x,y in zip(obj['lanes'],observed)]
    data.append(item)
summary={'note':'Direct read-only production MemberReadStore.acquire_candidates. SQL events are observation wrappers, no score/selection replacement. P1 actual expand/filters observed; P2/P3 planner and effective_expand are replayed from request and service path, not separately observed in original stdio. Union is first-seen from acquired lane rows before dispatcher policy/qualification.','files':len(data),'lanes':sum(len(x['lanes']) for x in data),'items':data}
(D/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print('files',summary['files'],'lanes',summary['lanes'],'reported_skipped',sum(l['reported_acquisition']['resource_skipped_rows'] for d in data for l in d['lanes'] if l['reported_acquisition'] is not None))
print('P1 observations',next(d['p1_observed_store_parameter_and_order_comparison'] for d in data if 'p1_observed_store_parameter_and_order_comparison' in d))
