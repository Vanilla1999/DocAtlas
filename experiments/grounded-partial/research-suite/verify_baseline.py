"""Verify all 80 untouched projector inputs against frozen native outputs."""
import gzip,json
from pathlib import Path
from docmancer.docs.application.docs_context_projection import project_docs_context
from eval.evidence_quality_v2.run import load_protocol,registry_for,audit_payload
from eval.evidence_quality_v2.semantic import assess_context
_,cases,manifest=load_protocol()
base=json.loads(Path('/tmp/docatlas-h1-baseline/baselines.json').read_text())
spans=lambda p:[(s['path_or_url'],s['snippet']) for s in p.get('sources',[])]
rows=[]
for case in cases:
 trace=json.loads(gzip.decompress(Path('/tmp/docatlas-h1-baseline',case['id']+'.trace.json.gz').read_bytes()))
 inp=trace['stages']['projector_inputs'][0]
 payload,snapshot=project_docs_context(retrieval=inp)
 original=next(r for r in base if r['id']==case['id'])
 assert spans(payload)==spans(original['payload']),case['id']
 errors=audit_payload(payload,snapshot,Path('/tmp/docatlas-continued-systemic/acceptance/full80_current/corpus')/case['project_group'])
 assert not errors,(case['id'],errors)
 rows.append({'id':case['id'],'answerability':case['answerability'],'assessment':assess_context(case,payload,registry_for(case['project_group'],manifest))})
assert sum(r['assessment']['context_sufficiency']=='sufficient' for r in rows if r['answerability']=='within_budget')==33
print(json.dumps({'cases':80,'unchanged_paths_snippets':80,'within_budget_sufficient':33,'audit_errors':0}))
