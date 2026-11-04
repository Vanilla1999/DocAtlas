"""Explicit model setup outside requests and outside the measured memory group.

The official chat weight is pinned in code. The third-party RANK conversion is
resolved to an immutable commit and LFS digest BEFORE any inference; its full
manifest is saved. Reproduce using --manifest, not a future moving main branch.
Only inert GGUF data is fetched; no downloaded Python/model code is executed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

MODELS = {
 'qwen-select': {'repo':'Qwen/Qwen3-0.6B-GGUF',
                 'revision':'1eaf4d9657fe65ad10a51eab76a8db5b363bddaa',
                 'filename':'Qwen3-0.6B-Q8_0.gguf',
                 'sha256':'9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031',
                 'size':639446688},
 'qwen-rerank': {'repo':'gorse-io/Qwen3-Reranker-0.6B-GGUF',
                 'revision':None, 'filename':'Qwen3-Reranker-0.6B-Q4_K_M.gguf'}
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group',choices=list(MODELS),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path)
    args=parser.parse_args()
    spec=json.loads(args.manifest.read_text()) if args.manifest else dict(MODELS[args.group])
    if spec['revision'] is None:
        url='https://huggingface.co/api/models/'+spec['repo']+'?blobs=true'
        with urllib.request.urlopen(url,timeout=90) as r:
            info=json.load(r)
        spec['revision']=info['sha']
        f=next(f for f in info['siblings'] if f['rfilename']==spec['filename'])
        spec.update(sha256=f['lfs']['sha256'],size=f['lfs']['size'])
    assert len(spec['revision'])==40 and len(spec['sha256'])==64 and spec['size']<800_000_000
    args.output.parent.mkdir(parents=True,exist_ok=True)
    manifest=args.output.with_suffix('.manifest.json')
    manifest.write_text(json.dumps(spec,indent=2)+'\n')  # Freeze before file load/inference.
    url='https://huggingface.co/'+spec['repo']+'/resolve/'+spec['revision']+'/'+spec['filename']
    size=0; digest=hashlib.sha256()
    temporary=args.output.with_suffix('.partial')
    with urllib.request.urlopen(url,timeout=90) as r, temporary.open('wb') as f:
        if not r.geturl().startswith('https://'):
            raise RuntimeError('HTTPS required')
        while block:=r.read(1024*1024):
            size+=len(block)
            if size>spec['size']:
                raise RuntimeError('oversized model')
            digest.update(block); f.write(block)
    if size!=spec['size'] or digest.hexdigest()!=spec['sha256']:
        raise RuntimeError('model checksum mismatch')
    temporary.replace(args.output)
    print(json.dumps(spec))


if __name__=='__main__':main()
