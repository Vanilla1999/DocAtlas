"""Package exact inputs, scores, contexts, payloads and snapshots; omit model weights."""
import json,lzma,hashlib,shutil
from pathlib import Path
root=Path(__file__).resolve().parent;out=root/'results';out.mkdir(exist_ok=True)
folders=['docatlas-research-input','docatlas-xprovence-output-v2','docatlas-embedding-output-v2','docatlas-contextual-final','docatlas-context-embedding-final','docatlas-research-final-eval']
files={}
for folder in folders:
 for p in sorted(Path('/tmp',folder).glob('*.json')):files[folder+'/'+p.name]=json.loads(p.read_text())
assert len(files['docatlas-contextual-final/contexts.json'])==353
assert len(files['docatlas-embedding-output-v2/rankings.json'])==80
assert len(files['docatlas-context-embedding-final/rankings.json'])==80
rows=files['docatlas-research-final-eval/rows.json'];assert len(rows)==960
assert not any(r['replay_errors'] or r['packet_errors'] for r in rows)
assert all('replay_snapshot' in r and 'packet_snapshot' in r for r in rows)
files['docatlas-research-index-coverage.json']=json.loads(Path('/tmp/docatlas-research-index-coverage.json').read_text())
blob=json.dumps({'format':1,'files':files},ensure_ascii=False,separators=(',',':')).encode();packed=lzma.compress(blob,preset=9)
(out/'raw-results.json.xz').write_bytes(packed)
for name in ['summary.json','paired.json','x_compression.json']:shutil.copyfile(Path('/tmp/docatlas-research-final-eval',name),out/name)
for folder,name in [('docatlas-xprovence-output-v2','xprovence-environment'),('docatlas-embedding-output-v2','embeddings-environment'),('docatlas-contextual-final','contextualization-environment'),('docatlas-context-embedding-final','context-embeddings-environment')]:shutil.copyfile(Path('/tmp',folder,'environment.json'),out/(name+'.json'))
identity={'archive_sha256':hashlib.sha256(packed).hexdigest(),'uncompressed_bytes':len(blob),'compressed_bytes':len(packed),'files':{k:hashlib.sha256(json.dumps(v,ensure_ascii=False,separators=(',',':')).encode()).hexdigest() for k,v in files.items()},'vector_arrays_included':False,'scores_and_full_rankings_included':True,'frozen80':80,'weak_answer_model_tested':False}
(out/'identity.json').write_text(json.dumps(identity,indent=2)+'\n');print(json.dumps({k:v for k,v in identity.items() if k!='files'}))
