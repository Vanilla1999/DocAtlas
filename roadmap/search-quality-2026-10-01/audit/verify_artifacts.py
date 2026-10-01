"""Validate completion and preserve source bytes; never invokes product tools."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from run_live_mcp import OUT, ROOT, WORK, save


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    projects=json.loads((OUT/'raw/project80/results.json').read_text())
    external=json.loads((OUT/'raw/external80/results.json').read_text())
    grounded=json.loads((OUT/'raw/grounded/results.json').read_text())
    gproject=json.loads((OUT/'raw/grounded-project20/results.json').read_text())
    c7=json.loads((OUT/'raw/context7/results.json').read_text())
    translated=json.loads((OUT/'raw/translation10/results.json').read_text())
    trace=json.loads((OUT/'raw/trace-results.json').read_text())
    assert len(projects)==240 and len(external)==80
    assert Counter(r['lane'] for r in projects)==dict(default=80,all=80,guided=80)
    assert len({(r['id'],r['lane']) for r in projects})==240
    assert len({r['id'] for r in external})==80
    assert len(grounded)==160 and Counter(r['limit'] for r in grounded)=={3:80,5:80}
    assert len({(r['id'],r['limit']) for r in grounded})==160
    assert len(gproject)==20 and len(c7)==10 and len(translated)==10 and len(trace)==76
    assert not any(r.get('error') or r.get('is_error') for r in grounded+gproject+c7)
    assert not any(r.get('error') for r in trace)
    protocol=json.loads((OUT/'raw/protocol/external80.json').read_text())
    assert {r['id'] for r in external}=={c['id'] for c in protocol['cases']}
    case_by_id={c['id']:c for c in protocol['cases']}
    for r in external:
        assert r['request']['question']==case_by_id[r['id']]['question']
        raw=json.loads((OUT/'raw/external80/native'/f'{r["id"]}.json').read_text())
        assert raw['request']==r['request'] and not raw['is_error']
        assert r['tokens']['actual_tokens']<=800
    for lane in ('default','all','guided'):
        for prefix,file in [('projectA','questions.json'),('projectB','followup_questions.json')]:
            cases=json.loads((OUT/'raw/protocol'/file).read_text())['cases']
            rs={r['id']:r for r in projects if r['lane']==lane and r['id'].startswith(prefix)}
            for case in cases:
                row=rs[prefix+'-'+case['id']]
                assert row['request']['question']==case['question']
                if lane=='guided':assert row['request']['lookup_queries']==case['host_lookups']
                else:assert 'lookup_queries' not in row['request']
                assert row['tokens']['actual_tokens']<=800
                raw=json.loads((OUT/'raw/project80'/lane/(row['id']+'.json')).read_text())
                assert raw['request']==row['request'] and not raw['is_error']
    assert json.loads((OUT/'raw/public-integrity-corrected.json').read_text())['panels']['project80']['violations']==0
    assert json.loads((OUT/'raw/public-integrity-corrected.json').read_text())['panels']['external80']['violations']==0
    assert json.loads((OUT/'raw/snapshot-integrity.json').read_text())['violations']==0
    # Full byte snapshots make this report independent of transient work directories.
    copies=[]
    for group in ['docatlas-project',*sorted({r['project'] for r in external})]:
        data=json.loads((OUT/'raw/index'/f'{group}.json').read_text())
        base=WORK/'corpus'/group
        for entry in data['manifest']:
            blob=(base/entry['path']).read_bytes()
            assert sha(blob)==entry['sha256']
            dest=OUT/'corpus'/group/entry['path']
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():assert dest.read_bytes()==blob
            else:dest.write_bytes(blob)
            copies.append(dict(path=str(dest.relative_to(OUT)),sha256=sha(blob),bytes=len(blob)))
    save(OUT/'raw/preserved-corpus-manifest.json',dict(files=len(copies),bytes=sum(r['bytes'] for r in copies),rows=copies))
    for name in ('docatlas.yaml','docatlas.project-docs.yaml','docatlas.docs.yaml'):
        assert (ROOT/name).read_bytes()==(OUT/'backup'/name).read_bytes()
    # No production checkout tracked modifications from this audit.
    tracked=subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True)
    staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True)
    assert not tracked and not staged
    reports=['ANALYSIS_RU.md','ACTION_PLAN_RU.md','COMPARATORS_RU.md','PROJECT_80_REVIEW_RU.md','EXTERNAL_80_REVIEW_RU.md']
    links=[]
    for name in reports:
        text=(OUT/name).read_text()
        for link in re.findall(r'\]\(([^)]+)\)',text):
            if link.startswith(('http://','https://','#')):continue
            target=(OUT/link.split('#',1)[0]).resolve()
            assert target.is_file(),(name,link)
            links.append(dict(file=name,link=link))
    for name,count in [('PROJECT_80_REVIEW_RU.md',80),('EXTERNAL_80_REVIEW_RU.md',80)]:
        text=(OUT/name).read_text()
        ids=re.findall(r'^\| ((?:project[AB]-Q\d\d)|(?:fastapi|starlette|typer|pydantic|httpx|mkdocs|ruff|uv)-\d\d) \|',text,re.M)
        assert len(ids)==count and len(set(ids))==count,(name,len(ids))
    verification=dict(status='PASS',main_stdio_questions=320,project_lanes=3,external_cases=80,
        grounded_searches=180,context7_queries=10,translation_queries=10,same_call_traces=76,
        preserved_corpus_files=len(copies),reports=reports,local_markdown_links=links,
        production_tracked_diff=[],source_config_unchanged=True,
        note='Artifact/method verification, not new product tests or independent semantic acceptance.')
    save(OUT/'raw/artifact-verification.json',verification)
    inventory=[]
    for file in sorted(OUT.rglob('*')):
        if not file.is_file() or '__pycache__' in file.parts or file.name=='artifact-manifest.json':continue
        if file.suffix=='.json':json.loads(file.read_text())
        blob=file.read_bytes();inventory.append(dict(path=str(file.relative_to(OUT)),bytes=len(blob),sha256=sha(blob)))
    save(OUT/'artifact-manifest.json',dict(files=len(inventory),bytes=sum(r['bytes'] for r in inventory),entries=inventory))
    print(json.dumps(verification,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
