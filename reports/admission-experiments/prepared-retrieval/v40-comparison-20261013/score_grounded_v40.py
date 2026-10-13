import json, re, zipfile, os, sys, math, statistics, hashlib
from pathlib import Path
from urllib.parse import urlsplit, unquote
import argparse

GOLD_DATA = '''
B01 the_basics.md 63 65
B02 the_basics.md 86 88
B03 the_basics.md 180 186
B04 the_basics.md 232 237
B05 the_basics.md 329 333
B06 the_basics.md 490 496
B07 file_collection_and_discovery.md 25 30
B08 - 0 0
P01 configuration.md 33 35
P02 configuration.md 122 134
P03 configuration.md 102 114
P04 managing-environments.md 72 76
P05 dependency-specification.md 87 98
P06 managing-environments.md 79 87
P07 - 0 0
P08 - 0 0
T01 reactivity.md 28 36
T02 reactivity.md 66 72
T03 reactivity.md 99 110
T04 reactivity.md 166 173
T05 workers.md 55 64
T06 workers.md 91 94
T07 workers.md 153 159
T08 - 0 0
V01 env-and-mode.md 32 54
V02 env-and-mode.md 73 81
V03 server-options.md 63 68
V04 server-options.md 70 74
V05 assets.md 108 124
V06 server-options.md 379 384
V07 - 0 0
V08 - 0 0
E01 configuration-files.md 19 30
E02 configuration-files.md 782 793
E03 command-line-interface.md 373 381
E04 ignore.md 24 48
E05 configuration-files.md 795 809
E06 command-line-interface.md 1020 1028
E07 - 0 0
E08 - 0 0
'''.strip()
GOLD={"V40-"+v[0]:(v[1],int(v[2]),int(v[3])) for line in GOLD_DATA.splitlines() if (v:=line.split())}
PARTIAL={'V40-B06','V40-B07','V40-P06','V40-T06','V40-T07','V40-V06','V40-E05','V40-E06'}
NEGATIVE={'V40-B08','V40-P07','V40-P08','V40-T08','V40-V07','V40-V08','V40-E07','V40-E08'}
FAMILY={'B':'black','P':'poetry','T':'textual','V':'vite','E':'eslint'}


def normalized(t):
    # Harmless Markdown renderer escaping is not a change to documentary fact.
    t=re.sub(r'\\(?=[\[\]_*`{}()<>#.!-])','',t)
    t=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',t)
    t=t.replace('`','').replace('*','').replace('#','').replace('_','')
    return ' '.join(t.casefold().split())

def matched(lines,combined):
    check=[]
    for s in lines:
        if (not s.strip() or s.strip().startswith('```')
            or re.fullmatch(r'[| :\-]+',s.strip())): continue
        a=normalized(s)
        if not a:continue
        # Heading-only markup is not a fact, still useful in strict score.
        check.append({'line':s.strip(),'core':not s.strip().startswith('#'), 'matched':a in combined})
    strict=bool(check) and all(c['matched'] for c in check)
    core=[c for c in check if c['core']]
    tolerant=bool(core) and sum(c['matched'] for c in core)/len(core)>=0.85
    return strict,tolerant,check

def find_doc(zipf,fam,filename):
    cands=[p for p in zipf.namelist() if p.startswith(f'docs/{fam}/') and p.endswith('/'+filename)]
    return cands[0] if len(cands)==1 else None

def ground_outputs(z,id_,limit,fam):
    data=json.loads(z.read(f'calls/{id_}/{limit}.json'))
    if data['returncode']!=0:return {'error':data.get('stderr','')[-300:]}
    try:
        arr=json.loads(data['stdout'])
        if not isinstance(arr,list):raise ValueError('not array')
    except Exception as e:return {'error':str(e)}
    bypath={}
    for src in arr:
        url=src.get('url','');p=unquote(urlsplit(url).path)
        marker='/docs/'+fam+'/'
        if marker not in p:return {'error':f'foreign source {url[-90:]}'}
        rel=p.split(marker,1)[1]
        bypath.setdefault(rel,[]).append(src.get('content',''))
    return {'path_contents':bypath,'source_count':len(arr),'chars':sum(len(src.get('content','')) for src in arr), 'seconds':data['seconds'], 'sources':[{ 'path':unquote(urlsplit(src['url']).path).split('/docs/'+fam+'/',1)[1], 'chars':len(src.get('content','')), 'score':src.get('score')} for src in arr]}

def atlas_outputs(id_,arm,fam):
    p=DOCATLAS_ROOT/'calls'/id_/arm/'public-payload.json'
    o=json.load(open(p));out={}
    for s in o.get('sources',[]):
        path=s['path_or_url'];out.setdefault(path,[]).append(s['snippet'])
    return {'path_contents':out, 'source_count':len(o.get('sources',[])), 'chars':sum(len(s['snippet']) for s in o.get('sources',[])), 'seconds':json.load(open(p.parent/'metadata.json'))['elapsed_seconds'], 'sources':[{'path':s['path_or_url'],'chars':len(s['snippet'])} for s in o.get('sources',[])]}

def evaluate(rows,fam,need,docs,negative):
    if rows.get('error'):return dict(error=rows['error'],status='ERROR')
    if negative: return {'status':'PASS' if rows['source_count']==0 else 'FAIL','number':rows['source_count'],'chars':rows['chars']}
    filename,a,b=need
    hits=[p for p in docs if p.endswith('/'+filename)]
    assert len(hits)==1,(fam,filename,hits)
    p=hits[0]
    lines=docs[p].splitlines()[a-1:b]
    texts=rows['path_contents'].get(p,[])
    strict,tolerant,check=matched(lines,normalized('\n\n'.join(texts)))
    # Preserve both strict and tolerant, factual verdict requires manual review
    return {'status':'PASS' if strict else 'FAIL', 'tolerant':tolerant, 'matched':sum(c['matched'] for c in check), 'expected_lines':len(check),'core_matched':sum(c['matched'] for c in check if c['core']), 'core_total':sum(c['core'] for c in check), 'unmatched_lines':[c['line'] for c in check if not c['matched']], 'source_matches':len(texts), 'source_count':rows['source_count'],'chars':rows['chars']}

def main(p,output):
    z=zipfile.ZipFile(p); docs={}
    for fam in FAMILY.values():
        docs[fam]={n.split(f'docs/{fam}/',1)[1]:z.read(n).decode('utf-8') for n in z.namelist() if n.startswith(f'docs/{fam}/') and n.endswith('.md')}
    metrics={arm:{'P':0,'PART':0,'N':0,'strict_pass':0,'tolerant_pass':0,'chars':0,'sources':0,'seconds':[]} for arm in ('G2','G5','Dold','Dnew')}
    rows=[]
    for id_,need in GOLD.items():
        fam=FAMILY[id_.split('-')[1][0]]
        category='N' if id_ in NEGATIVE else 'PART' if id_ in PARTIAL else 'P'
        row={'id':id_,'category':category,'results':{}}
        for arm in metrics:
            v=ground_outputs(z,id_,2 if arm=='G2' else 5,fam) if arm.startswith('G') else atlas_outputs(id_,'legacy' if arm=='Dold' else 'prepared_parent_v1',fam)
            e=evaluate(v,fam,need,docs[fam],category=='N')
            row['results'][arm]=e
            if e.get('status')=='PASS':metrics[arm][category]+=1;metrics[arm]['strict_pass']+=1
            if e.get('tolerant'):metrics[arm]['tolerant_pass']+=1
            metrics[arm]['sources']+=v.get('source_count',0);metrics[arm]['chars']+=v.get('chars',0);metrics[arm]['seconds'].append(v.get('seconds',0))
        rows.append(row)
    for arm,v in metrics.items():
        v['median_seconds']=round(statistics.median(v.pop('seconds')),3)
    out={'method':'source-bound exact normalized line inclusion (strict); >=85% core lines tolerant; no model answers', 'metrics':metrics,'cases':rows}
    output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print('METRICS')
    for arm,v in metrics.items():print(arm,v)
    print('\nCASE COMPARISON')
    for row in rows:
        vals=[row['results'][a].get('status') for a in ('Dnew','G2','G5')]
        print(row['id'],row['category'],*vals, 'core',*(row['results'][a].get('tolerant') for a in ('Dnew','G2','G5')),
              'char',*(row['results'][a].get('chars') for a in ('Dnew','G2','G5')))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description='Recalculate historical V40 Grounded/DocAtlas evidence coverage')
    ap.add_argument('--grounded-zip',type=Path,required=True)
    ap.add_argument('--docatlas-dir',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    DOCATLAS_ROOT=args.docatlas_dir
    main(args.grounded_zip,args.output)
