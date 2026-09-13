"""Restore captured inputs for offline score evaluation; never downloads weights."""
import json,lzma,gzip,base64
from pathlib import Path
root=Path(__file__).resolve().parent
h1=json.loads(lzma.decompress((root.parent/'semantic-selection/results/raw-results.json.xz').read_bytes()))
p=Path('/tmp/docatlas-h1-baseline');p.mkdir(exist_ok=True)
(p/'baselines.json').write_text(json.dumps(h1['baseline'],ensure_ascii=False)+'\n')
for cid,t in h1['traces']['A'].items():(p/(cid+'.trace.json.gz')).write_bytes(gzip.compress(json.dumps(t,ensure_ascii=False).encode(),mtime=0))
archive=json.loads(lzma.decompress((root/'results/raw-results.json.xz').read_bytes()))
for name,value in archive['files'].items():
 p=Path('/tmp')/name;p.parent.mkdir(parents=True,exist_ok=True)
 if isinstance(value,dict) and 'base64' in value:p.write_bytes(base64.b64decode(value['base64']))
 else:p.write_text(json.dumps(value,ensure_ascii=False)+'\n')
for d in archive['files']['docatlas-research-input/documents.json']:
 p=Path('/tmp/docatlas-continued-systemic/acceptance/full80_current/corpus')/d['library']/d['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(d['text'])
print('Restored frozen source corpus, model inputs, scores and projector traces.')
