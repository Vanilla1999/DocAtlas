import concurrent.futures
import json
import subprocess
import time
from pathlib import Path
import argparse

OUT=Path('/tmp/opencode/terra-step8')
parser=argparse.ArgumentParser()
parser.add_argument('--pilot',action='store_true')
args=parser.parse_args()
cases=json.loads((OUT/'cases.json').read_text())
jobs=[(corpus,arm,c) for corpus in ('L0','L2') for c in cases for arm in ('docatlas','search')]
if args.pilot:
    jobs=[j for j in jobs if j[0]=='L2' and j[2]['id']=='T01-ru']

def run(job):
    corpus,arm,case=job
    dest=OUT/corpus/arm/case['id']
    if dest.with_suffix('.jsonl').exists():
        return {'case':case['id'],'arm':arm,'corpus':corpus,'skipped_existing':True}
    start=time.monotonic()
    created=subprocess.run(['opencode','api','post','/api/session','--data',json.dumps({'location':{'directory':str(dest.parent)},'title':f"step8-review {corpus} {arm} {case['id']}"})],capture_output=True,text=True,check=True)
    session=json.loads(created.stdout)['data']['id']
    cmd=['opencode','run','--session',session,'--model','openai/gpt-6.1-terra#low','--agent','measure','--format','json',case['question']]
    with dest.with_suffix('.jsonl').open('w') as stdout, dest.with_suffix('.stderr').open('w') as stderr:
        try:
            p=subprocess.run(cmd,cwd=dest.parent,stdout=stdout,stderr=stderr,timeout=600)
            code=p.returncode
        except subprocess.TimeoutExpired:
            code='timeout'
    receipt={'case':case['id'],'arm':arm,'corpus':corpus,'session':session,'seconds':round(time.monotonic()-start,2),'exit':code}
    for endpoint,suffix in [(f'/api/session/{session}','session'),(f'/api/session/{session}/message','messages')]:
        exported=subprocess.run(['opencode','api','get',endpoint],capture_output=True,text=True,check=True)
        dest.with_suffix('.'+suffix+'.json').write_text(exported.stdout)
    dest.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt),flush=True)
    return receipt

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(run,jobs))
