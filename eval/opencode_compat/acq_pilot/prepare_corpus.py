import hashlib,json,subprocess,shutil
from pathlib import Path
import yaml

root=Path('/home/viadmin/StudioProjects/DocAtlas')
out=Path('/tmp/opencode/acq-pilot')
old=Path('/tmp/opencode/semantic-signal-experiment/project')
project=out/'L2-project'
assert not project.exists()
project.mkdir()
catalog=yaml.safe_load((old/'docatlas.project-docs.yaml').read_text())
entries={x['path']:x for x in catalog['documents']}
for name in entries:
    dst=project/name; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(old/name,dst)
paths=subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD'],cwd=root,text=True).splitlines()
questions=json.loads((root/'eval/opencode_compat/acq_pilot/oracle.json').read_text())['questions']
oldquestions=json.loads((root/'eval/opencode_compat/original_project_questions20.json').read_text())
needles=[q[k] for q in questions+oldquestions for k in ('question','search_question') if q.get(k)]
excluded=[]
for name in paths:
    p=Path(name)
    if p.suffix.lower()!='.md' or not (len(p.parts)==1 or p.parts[0] in ('docs','wiki','roadmap','v2plan')): continue
    if name in entries: continue
    text=subprocess.check_output(['git','show','HEAD:'+name],cwd=root).decode('utf-8')
    reason=None
    if p.name.lower()=='agents.md': reason='agent instructions'
    elif any(n in text for n in needles): reason='contains benchmark question'
    elif any(s in name.lower() for s in ('benchmark','evaluation','eval_', 'gold20','acq_pilot','research_evidence')): reason='benchmark/evaluation path'
    if reason:
        excluded.append({'path':name,'reason':reason}); continue
    dst=project/name; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_text(text)
    entries[name]={'path':name,'role':'other','scope':'project','description':'Project documentation: '+name,'authority':'source_of_truth','status':'active','impact':'track'}
catalog['documents']=list(entries.values())
for entry in catalog['documents']:
    if entry.get('module_path'): (project/entry['module_path']).mkdir(parents=True,exist_ok=True)
(project/'docatlas.project-docs.yaml').write_text(yaml.safe_dump(catalog,sort_keys=False,allow_unicode=True))
manifest={'base_commit':'3d21bfea','additions_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'files':[],'excluded':excluded,'note':'L0 files preserved when paths collide; additions artificially project/source_of_truth/active'}
for name in sorted(entries):
    data=(project/name).read_bytes(); manifest['files'].append({'path':name,'sha256':hashlib.sha256(data).hexdigest(),'origin':'L0' if (old/name).exists() and name in {x['path'] for x in yaml.safe_load((old/'docatlas.project-docs.yaml').read_text())['documents']} else 'HEAD'})
facts=[f for q in questions for f in q['facts']]
matches=[]
for f in facts:
    hits=[]
    for item in manifest['files']:
        txt=(project/item['path']).read_text(); pos=0
        while (i:=txt.find(f['quote'],pos))>=0:
            hits.append({'path':item['path'],'line_start':txt.count('\n',0,i)+1,'line_end':txt.count('\n',0,i+len(f['quote']))+1,'sha256':item['sha256']});pos=i+1
    matches.append({'fact':f['id'],'occurrences':hits})
for name,obj in [('corpus-manifest.json',manifest),('quote-occurrences.json',matches)]:
    (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
print('documents',len(entries),'excluded',len(excluded),'matches',sum(len(x['occurrences']) for x in matches))
