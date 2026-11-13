import gzip
import hashlib
import json
import shutil
from pathlib import Path

src=Path('/tmp/opencode/terra-step8')
dest=Path('/home/viadmin/StudioProjects/DocAtlas/eval/blind_project_context/step8-terra-review')
dest.mkdir(parents=True,exist_ok=False)
for name in ['plan.json','cases.json','summary.json','manual-review.json','analysis.json','answers-and-flow.md','wheel-provenance.json','continuation-window-checks.json','corpus-integrity.json']:
    shutil.copy2(src/name,dest/name)
configs={str(p.parent.relative_to(src)):json.loads(p.read_text()) for p in src.glob('*/*/opencode.json')}
(dest/'configs.json').write_text(json.dumps(configs,ensure_ascii=False,indent=2))
receipts=[]
for p in sorted(src.glob('*/*/*.receipt.json')):
    record=json.loads(p.read_text())
    base=p.name.removesuffix('.receipt.json')
    record['session_state']=json.loads((p.parent/(base+'.session.json')).read_text())['data']
    receipts.append(record)
(dest/'receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2))
with (dest/'raw-sessions.jsonl.gz').open('wb') as handle:
    with gzip.GzipFile(fileobj=handle,mode='wb',mtime=0) as gz:
        for p in sorted(src.glob('*/*/*.jsonl')):
            if not p.with_suffix('.receipt.json').exists():continue
            record={'path':str(p.relative_to(src)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'events':[json.loads(line) for line in p.read_text().splitlines()]}
            gz.write((json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n').encode())
scripts=dest/'scripts';scripts.mkdir()
for name in ['setup_terra_review.py','run_terra_review.py','run_terra_corrected.py','analyze_terra_review.py','summarize_terra_review.py','archive_terra_review.py']:
    shutil.copy2(Path('/tmp/opencode')/name,scripts/name)
hashes={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.rglob('*')) if p.is_file()}
(dest/'sha256.json').write_text(json.dumps(hashes,indent=2))
print('Archived',len(receipts),'sessions;',sum(p.stat().st_size for p in dest.rglob('*') if p.is_file()),'bytes')
