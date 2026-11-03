import hashlib,json,sqlite3,sys,collections,re,zipfile
from pathlib import Path
R=Path('/tmp/opencode/acq-pilot')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
head=json.loads((R/'heading-comparison.json').read_text())
lanes=json.loads((R/'archive-40-lanes.json').read_text())
with sqlite3.connect(':memory:') as mem:
    src=sqlite3.connect('file:/home/viadmin/.local/share/docatlas-semantic-signal-experiment/docatlas-home/mcp-members/members.db?mode=ro',uri=True)
    src.backup(mem);src.close()
    mem.execute("create virtual table temp.pilot_vocab using fts5vocab(main, retrieval_children_fts, 'instance')")
    for lane in lanes:
        for d in lane['differences']:
            tokens=[]
            for term in d['match_terms']:
                mem.execute('drop table if exists temp.query_tokenizer'); mem.execute('create virtual table temp.query_tokenizer using fts5(text)');mem.execute('insert into temp.query_tokenizer values (?)',(term,))
                mem.execute('drop table if exists temp.query_vocab');mem.execute("create virtual table temp.query_vocab using fts5vocab(temp, query_tokenizer, 'row')")
                tokens.extend((term,r[0]) for r in mem.execute('select term from temp.query_vocab'))
            indexed=list(mem.execute('select term,col,offset from temp.pilot_vocab where doc=?',(d['id'],)))
            d['fts_token_evidence']=[{'query_spelling':q,'indexed_normalized_term':t,'field':col,'token_offset':off} for q,t in tokens for v,col,off in indexed if v==t]
(R/'archive-40-lanes-vocab.json').write_text(json.dumps(lanes,ensure_ascii=False))
facts=[]
for q in json.loads(Path('/home/viadmin/StudioProjects/DocAtlas/eval/opencode_compat/acq_pilot/oracle.json').read_text())['questions']:
    for f in q['facts']: facts.append(f)
comparisons=[]
for label,a,b in [('trace_v5','L0-v5-P1','L0-v5-traceoff-P1'),('default_v0','L0-v0-P1','L0-default-P1')]:
    x=(R/(a+'.payload.json')).read_text();y=(R/(b+'.payload.json')).read_text()
    comparisons.append({'label':label,'byte_equal':x==y,'json_equal':json.loads(x)==json.loads(y),'sha256':[hashlib.sha256(z.encode()).hexdigest() for z in (x,y)]})
calls=[]
for m in sorted(R.glob('*.metrics.json')):
    x=json.loads(m.read_text()); x.pop('source_checks',None); calls.append({'name':m.name,**x})
summary={'calls':calls,'parity':comparisons,'heading':{'total':len(head),'empty_metadata_heading':sum(not x['metadata_heading_path'] for x in head),'missing_prefix':sum(x['prefix_heading'] is None for x in head),'literal_mismatch':sum(not x['exact_join_match'] for x in head),'title_only_terms_when_prefix_missing':sum(bool(x['title_terms_absent_body_description']) for x in head if x['prefix_heading'] is None)},'archive':{'lanes':len(lanes),'fts_vs_python_different':sum(x['fts_count']!=x['python_count'] for x in lanes),'archive_fts_count_mismatch':sum(x['fts_count']!=x['archive_fts_count'] for x in lanes),'archive_python_count_mismatch':sum(x['python_count']!=x['archive_python_count'] for x in lanes),'positive_mismatch':sum(x['production_positive_count']!=x['archive_positive_count'] for x in lanes),'gold_rank_mismatch':sum(x['production_gold_ranks']!=x['archive_gold_ranks'] for x in lanes)},'candidate_notes':['ordered_union_ids is first-seen union of raw acquisition lane rows, not postqualification union','scoped FTS counts exclude any additional locator-only admission; positive_or_locator_count is production full result count','qualification separately instrumented for L0 and L2 V0 P1 only; public stdio trace records projection only']}
(R/'raw-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='calls'},ensure_ascii=False,indent=2))
