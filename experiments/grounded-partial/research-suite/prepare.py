"""Export source-only index units and question-only retrieval requests."""
import json,hashlib,sqlite3
from pathlib import Path
from eval.evidence_quality_v2.run import load_protocol,documents_for
p=Path('/tmp/docatlas-research-input');p.mkdir(exist_ok=False)
protocol,cases,manifest=load_protocol();docs=[];chunks=[];questions=[];sections={}
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
for lib in sorted({c['project_group'] for c in cases}):
 for path,body in documents_for(lib,manifest).items():
  dk=digest(lib+'\n'+path);docs.append({'key':dk,'library':lib,'path':path,'text':body,'version':next(s['ref'] for s in manifest['sources'] if s['project']==lib and s['path']==path)})
 db=sqlite3.connect('/tmp/docatlas-continued-systemic/acceptance/full80_current/state/'+lib+'/index.db');db.row_factory=sqlite3.Row
 sections[lib]=[dict(r) for r in db.execute('select title,anchor,source_path,line_start,line_end from retrieval_children')]
 for row in db.execute('select source_path,display_text,line_start,line_end from retrieval_children order by source_path,line_start,line_end,display_text'):
  r=dict(row);doc=next(d for d in docs if d['library']==lib and d['path']==r['source_path']);lines=doc['text'].splitlines(keepends=True);start=sum(map(len,lines[:r['line_start']-1]));end=sum(map(len,lines[:r['line_end']]));text=r['display_text'].strip();at=doc['text'].find(text,start,end);assert at>=0
  chunks.append({'key':digest(doc['key']+'\n'+str(at)+'\n'+text),'document':doc['key'],'library':lib,'path':r['source_path'],'text':text,'char_start':at,'char_end':at+len(text),'line_start':r['line_start'],'line_end':r['line_end']})
for c in cases:questions.append({'key':digest(c['project_group']+'\n'+c['question']),'library':c['project_group'],'question':c['question']})
for name,data in [('documents',docs),('chunks',chunks),('questions',questions),('sections',sections)]: (p/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False)+'\n')
print(len(docs),len(chunks),len(questions))
