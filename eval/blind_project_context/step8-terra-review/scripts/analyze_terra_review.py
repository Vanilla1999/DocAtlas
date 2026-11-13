import json
import sys
import re
import hashlib
from pathlib import Path
from collections import Counter,defaultdict
import tiktoken

OUT=Path('/tmp/opencode/terra-step8')
TREE=Path('/tmp/opencode/step8-review')
WORK=Path('/home/viadmin/.cache/docatlas-step8-review-work')
sys.path.insert(0,str(TREE/'eval/blind_project_context'))
from score import rows_of,placements,covers,decode_context
from corpus import documents
enc=tiktoken.get_encoding('o200k_base')
cases={c['id']:c for c in json.loads((OUT/'cases.json').read_text())}
gold={t['topic_id']:t for t in json.loads((TREE/'eval/blind_project_context/oracle.json').read_text())['topics'] if t['topic_id'] in {c['topic_id'] for c in cases.values()}}
audit={f['fact_id']:f['occurrences'] for f in json.loads((TREE/'eval/blind_project_context/witness-audit.json').read_text())['facts'] if f['fact_id'].split('.')[0] in gold}
docs={c:documents(WORK/(c+'-0')/'project') for c in ['L0','L2']}

def payloads(value):
    if isinstance(value,dict):
        if 'context_format' in value or ('sources' in value and 'status' in value):
            yield value
        else:
            for v in value.values(): yield from payloads(v)
    elif isinstance(value,list):
        for v in value: yield from payloads(v)

results=[]
for file in sorted(OUT.glob('*/*/*.jsonl')):
    if not file.with_suffix('.receipt.json').exists(): continue
    corpus,arm,case_id=file.relative_to(OUT).parts
    case_id=case_id.removesuffix('.jsonl')
    if case_id not in cases: continue
    events=[json.loads(l) for l in file.read_text().splitlines()]
    finishes=[e['part'] for e in events if e['type']=='step_finish']
    final='\n'.join(e['part']['text'] for e in events if e['type']=='text')
    tools=[e['part'] for e in events if e['type']=='tool_use']
    usage=Counter()
    for f in finishes:
        t=f['tokens']
        for k in ('input','output','reasoning'): usage[k]+=t[k]
        usage['cache_read']+=t['cache']['read']
        usage['cache_write']+=t['cache']['write']
    spans=defaultdict(list)
    anomalies=[]
    refs={}
    flow=[]
    tool_tokens=0
    all_output=[]
    for tool in tools:
        state=tool['state']; inp=state.get('input'); output=state.get('output','')
        tool_tokens+=len(enc.encode(output))
        all_output.append(output)
        meta=state.get('metadata',{}).get('metadata',{})
        info={'tool':tool['tool'],'input':inp,'status':state['status'],'output_tokens':len(enc.encode(output)), 'nested_calls':meta.get('toolCalls',[]),'code_error':bool(meta.get('error')),'truncated':bool(meta.get('truncated'))}
        try: parsed=json.loads(output)
        except (ValueError,TypeError): parsed=None
        packs=list(payloads(parsed))
        for p in packs:
            info['more_context']=p.get('more_context')
            info['source_selection']=p.get('source_selection')
            rows=rows_of(p)
            for row in rows:
                spots=placements(docs[corpus].get(row['path']),row['line_start'],row['line_end'],row['text'])
                if len(spots)==1: spans[row['path']].append(spots[0])
                elif not spots: anomalies.append('not_verbatim:'+str(row))
            for row in decode_context(p).get('sources',[]) if p.get('context_format') else []:
                refs[row.get('ref')]=[row.get('path'),row.get('line_start'),row.get('line_end')]
        if tool['tool']=='read' and isinstance(inp,dict):
            path=Path(inp['path'])
            project=WORK/(corpus+'-0')/'project'
            try: rel=str(path.relative_to(project))
            except ValueError: rel=None
            if rel in docs[corpus]:
                for match in re.finditer(r'(?m)^(\d+): (.*)$',output):
                    line=int(match[1]); text=match[2]
                    spots=placements(docs[corpus][rel],line,line,text)
                    if len(spots)==1:
                        a,b=spots[0]
                        if b<len(docs[corpus][rel]) and docs[corpus][rel][b]=='\n': b+=1
                        spans[rel].append((a,b))
        flow.append(info)
    delivered=[]
    for fact in gold[cases[case_id]['topic_id']]['facts']:
        present=any(covers(spans[o['path']],spot) for o in audit[fact['fact_id']][corpus] for spot in placements(docs[corpus].get(o['path']),o['line_start'],o['line_end'],fact['quote']))
        delivered.append({'id':fact['fact_id'],'found':present,'quote':fact['quote']})
    cited=set(re.findall(r'ev-[0-9a-f]+',final))
    receipt=json.loads(file.with_suffix('.receipt.json').read_text())
    result={**receipt,'steps':len(finishes),'usage':dict(usage),'input_including_cache':usage['input']+usage['cache_read']+usage['cache_write'],'tool_output_tokens':tool_tokens,'tools':dict(Counter(t['tool'] for t in tools)),'flow':flow,'final':final,'facts_in_read_evidence':delivered,'evidence_count':sum(f['found'] for f in delivered),'facts_total':len(delivered),'unseen_cited_refs':sorted(cited-refs.keys()),'known_refs':refs,'source_anomalies':anomalies,'error_events':[e for e in events if e['type']=='error']}
    results.append(result)
    file.with_suffix('.answer.md').write_text(final+'\n')
(OUT/'analysis.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
lines=[]
for r in results:
    lines += [f"## {r['corpus']} {r['arm']} {r['case']}",f"Evidence {r['evidence_count']}/{r['facts_total']}; input {r['input_including_cache']}; tools {r['tool_output_tokens']}; steps {r['steps']}",r['final'],'','### Trace']
    for f in r['flow']:
        lines.append(json.dumps({k:v for k,v in f.items() if k!='source_selection'},ensure_ascii=False))
    lines += ['']
(OUT/'answers-and-flow.md').write_text('\n'.join(lines))
print('Analyzed',len(results),'sessions')
