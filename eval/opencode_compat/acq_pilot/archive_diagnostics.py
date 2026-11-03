import json,re,sqlite3,zipfile,time,sys
from pathlib import Path
from docmancer.retrieval.lexical_terms import lexical_tokens,lexical_terms
from docmancer.core.sqlite_store import SQLiteStore
import docmancer.retrieval.experimental_acquisition as EA
R=Path('/tmp/opencode/acq-pilot'); DB=Path('/home/viadmin/.local/share/docatlas-semantic-signal-experiment/docatlas-home/mcp-members/members.db')
archive=Path('/home/viadmin/Загрузки/acq_audit_tuning_diagnostics.zip')
with zipfile.ZipFile(archive) as z:
    report=json.loads(z.read('acq_diag.json'))['report']; ablate=json.loads(z.read('ablate.json'))
    for n in ('acq_lib.py','ablate2.py','acq_diag.json','ablate.json','ablate_results.txt'):
        (R/('archive-'+n)).write_bytes(z.read(n))
def connect():
    c=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True); c.row_factory=sqlite3.Row;c.execute('pragma query_only=on');return c
store=object.__new__(SQLiteStore);store._connect=connect
with connect() as c:
    generation=c.execute('select active_generation_id from index_state').fetchone()[0]
    windows=[dict(r) for r in c.execute('select * from retrieval_children where generation_id=? order by id',(generation,))]
    byid={r['id']:r for r in windows}
    (R/'L0-all-windows.json').write_text(json.dumps(windows,ensure_ascii=False))
    headings=[]
    for w in windows:
        md=json.loads(w['metadata_json'] or '{}'); m=re.search(r'Heading Path: ([^|\n]*)',w['context_prefix'] or '')
        extracted=m.group(1).strip() if m else None; heading=md.get('heading_path',[])
        headings.append({'id':w['id'],'stable_chunk_id':w['stable_chunk_id'],'path':md.get('project_doc_path') or w['source_path'],'metadata_heading_path':heading,'prefix_heading':extracted,'exact_join_match':extracted==' > '.join(heading) if isinstance(heading,list) else False,'title':w['title'],'title_terms_absent_body_description':sorted(set(lexical_terms(w['title'] or ''))-set(lexical_terms((w['display_text'] or '')+' '+(md.get('project_doc_description') or ''))))})
    (R/'heading-comparison.json').write_text(json.dumps(headings,ensure_ascii=False,indent=2))
    result=[]
    for record in report:
        q=record['q']; gold=record['gold']; path,span=gold.rsplit(':',1); parts=span.split('-'); a=int(parts[0]);b=int(parts[-1])
        for li,lane in enumerate(record['lanes']):
            text=lane['text']; terms=re.findall(r'\w+',text); expr='{title retrieval_text} : ('+' OR '.join('"'+t+'"' for t in terms)+')'
            fts={r[0] for r in c.execute('select rowid from retrieval_children_fts where retrieval_children_fts match ?', (expr,))} & set(byid)
            tset=set(lexical_terms(text)); py={w['id'] for w in windows if tset & set(lexical_tokens((w['title'] or '')+' '+(w['retrieval_text'] or '')))}
            differences=[]
            for id in sorted(fts^py):
                w=byid[id]; matched=[]
                for t in terms:
                    expression='{title retrieval_text} : ("'+t+'")'
                    if c.execute('select 1 from retrieval_children_fts where rowid=? and retrieval_children_fts match ?', (id,expression)).fetchone(): matched.append(t)
                differences.append({'id':id,'membership':'fts_only' if id in fts else 'python_only','match_terms':matched,'python_matched_terms':sorted(tset & set(lexical_tokens((w['title'] or '')+' '+(w['retrieval_text'] or '')))),'row':w})
            filters={'project_path':'/tmp/opencode/semantic-signal-experiment/project','source_class':'project_file'}
            EA.ACQUISITION_CANDIDATES=20000
            t=time.perf_counter(); rows=store._search_rows(text,20000,filters=filters); elapsed=time.perf_counter()-t
            def goldmatch(w):
                md=json.loads(w['metadata_json'] or '{}'); p=md.get('project_doc_path') or w['source_path'] or w['source']
                return str(p).endswith(path) and w['line_start']<=b and w['line_end']>=a
            ranks=[i+1 for i,w in enumerate(rows) if goldmatch(w)][:6]
            result.append({'question':q,'lane':li,'text':text,'query_terms':terms,'fts_count':len(fts),'python_count':len(py),'archive_fts_count':lane['fts_superset'],'archive_python_count':ablate['V0 current'][q-1]['sup'][li],'production_positive_count':len(rows),'archive_positive_count':lane['positive_utility'],'production_gold_ranks':ranks,'archive_gold_ranks':lane['gold_ranks'],'differences':differences,'filters':filters,'generation':generation,'seconds':elapsed})
            print(q,li,len(fts),len(py),len(rows),flush=True)
    (R/'archive-40-lanes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
