"""Single-pass offline scoring used by real public experimental selector.

No qualification/retrieval replacement; input is complete captured raw windows.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

os.environ.update(OMP_NUM_THREADS='8', MKL_NUM_THREADS='8', TOKENIZERS_PARALLELISM='false', HF_HUB_OFFLINE='1')
import torch
import transformers
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path('/tmp/opencode/docatlas-review-evidence/admission-full-20261012')
REV = '1427fd652930e4ba29e8149678df786c240d8825'


def main():
    source, target = map(Path, sys.argv[1:3])
    if target.exists():
        raise RuntimeError('Refusing repeated scoring output')
    cases = json.loads(source.read_text())
    if sum(len(row['pool']) for row in cases) > 500:
        raise RuntimeError('Primary forward budget exceeded before inference')
    def sha(data):
        return hashlib.sha256(data).hexdigest()
    receipt = dict(status='STARTED', model_id='cross-encoder/mmarco-mMiniLMv2-L12-H384-v1',
                   revision=REV, device='cpu', dtype='FP32', forwards=0, threads=8,
                   input_sha256=sha(source.read_bytes()), cases=[], transformers=transformers.__version__,
                   torch=torch.__version__, truncation=False, max_length=512)
    def save():
        target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    torch.set_num_threads(8)
    torch.set_num_interop_threads(1)
    start = time.monotonic()
    try:
        manifest = json.loads((ROOT/'C_ASSET_RECEIPT.json').read_text())['models'][1]
        for asset in manifest['files']:
            if sha(Path(asset['path']).read_bytes()) != asset['sha256']:
                raise RuntimeError('Pinned asset bytes differ')
        begin = time.monotonic()
        model_path = ROOT/'model-assets'/'mini'/REV
        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(model_path, local_files_only=True,
                  dtype=torch.float32, attn_implementation='sdpa').eval()
        receipt['cold_load_seconds'] = time.monotonic()-begin
        for case in cases:
            out = {'id':case['id'], 'pool_sha256':case['pool_sha256'], 'rows':[]}
            encoded = []
            for index, row in enumerate(case['pool']):
                inputs = tokenizer(case['question'], row['text'], truncation=False, return_tensors='pt')
                count = inputs['input_ids'].shape[1]
                out['rows'].append(dict(index=index,id=row['id'],tokens=count,score=None,
                                       status='OVERFLOW' if count > 512 else 'PENDING'))
                encoded.append(inputs)
            if any(row['status']=='OVERFLOW' for row in out['rows']):
                out['status']='BLOCKED_FULL_POOL_OVERFLOW'
            else:
                out['status']='SCORED'
                for row, inputs in zip(out['rows'],encoded):
                    begin = time.monotonic()
                    with torch.inference_mode():
                        score = model(**inputs).logits[0,0].float().item()
                    if not torch.isfinite(torch.tensor(score)):
                        raise RuntimeError('Nonfinite score')
                    row.update(score=score,seconds=time.monotonic()-begin,status='SCORED')
                    receipt['forwards'] += 1
                    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 > 12*1024**3:
                        raise RuntimeError('RSS limit')
                out['order']=sorted(range(len(out['rows'])),key=lambda i:(-out['rows'][i]['score'],i))
            receipt['cases'].append(out)
            save()
        receipt['status']='SCORED' if all(c['status']=='SCORED' for c in receipt['cases']) else 'PARTIAL_BLOCKED_OVERFLOW'
    except Exception as exc:
        receipt.update(status='BLOCKED',error=repr(exc))
        raise
    finally:
        receipt['wall_seconds']=time.monotonic()-start
        receipt['rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        save()

if __name__=='__main__':
    main()
