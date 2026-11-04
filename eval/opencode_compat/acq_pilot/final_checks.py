import hashlib,json,sqlite3,sys
from pathlib import Path
import yaml
R=Path('/tmp/opencode/acq-pilot'); repo=Path('/home/viadmin/StudioProjects/DocAtlas'); old=Path('/tmp/opencode/semantic-signal-experiment/project')
catalog=yaml.safe_load((old/'docatlas.project-docs.yaml').read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'note':'L0 source manifest written after calls; preflight oracle and source hashes were frozen before calls','project':str(old),'catalog_sha256':sha(old/'docatlas.project-docs.yaml'),'files':[{'path':x['path'],'sha256':sha(old/x['path'])} for x in catalog['documents']]}
(R/'L0-manifest-postrun.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
installed=R/'venv/lib/python3.13/site-packages/docmancer'; comparisons=[]
for p in sorted((repo/'docmancer').rglob('*.py')):
    rel=p.relative_to(repo/'docmancer'); other=installed/rel
    compile(p.read_bytes(),str(p),'exec')
    comparisons.append({'path':str(rel),'source_sha256':sha(p),'installed_sha256':sha(other) if other.exists() else None,'equal':other.exists() and sha(p)==sha(other)})
for p in R.glob('*.py'): compile(p.read_bytes(),str(p),'exec')
states={}
for corpus in ('L0','L2'):
    p=Path('/home/viadmin/.local/share/docatlas-acq-pilot')/corpus/'docatlas-home/mcp-members/members.db'
    with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as c:
        states[corpus]={'path':str(p),'sha256_postrun':sha(p),'active_generation':c.execute('select active_generation_id from index_state').fetchone()[0], 'total_windows':c.execute('select count(*) from retrieval_children').fetchone()[0]}
summary={'source_modules':len(comparisons),'source_installed_mismatches':[x for x in comparisons if not x['equal']],'states':states,'invalid_env_exit':int((R/'invalid-env.exit').read_text()),'invalid_env_stderr':(R/'invalid-env.stderr').read_text()}
(R/'installed-module-hashes.json').write_text(json.dumps(comparisons,indent=2))
(R/'final-checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)); print(json.dumps(summary,ensure_ascii=False,indent=2))
