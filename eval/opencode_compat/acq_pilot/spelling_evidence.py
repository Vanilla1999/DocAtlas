import collections,json,re,unicodedata
from pathlib import Path
R=Path('/tmp/opencode/acq-pilot'); lanes=json.loads((R/'archive-40-lanes-vocab.json').read_text()); output=[]
def normalize(s):
    return ''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn')
for lane in lanes:
    if not lane['differences']: continue
    samples=[]
    for d in lane['differences']:
        evid=[]
        for item in d['fts_token_evidence']:
            field=item['field']; text=d['row'][field] or ''; needle=item['indexed_normalized_term']
            occurrences=[{'spelling':m.group(),'char_start':m.start(),'char_end':m.end()} for m in re.finditer(r'[^\W_]+',text,flags=re.UNICODE) if normalize(m.group())==needle]
            evid.append({**item,'matching_surface_spellings':occurrences})
        samples.append({'id':d['id'],'membership':d['membership'],'terms':d['match_terms'],'token_evidence':evid})
    output.append({'question':lane['question'],'lane':lane['lane'],'count':len(samples),'term_counts':dict(collections.Counter(t for x in samples for t in x['terms'])),'rows':samples})
(R/'archive-difference-spellings.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
