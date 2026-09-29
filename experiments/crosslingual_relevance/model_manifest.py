"""Content-addressed LOCAL model inventory. No model download or freeze override."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath

MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2'
REQUIRED = {'config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','onnx/model.onnx'}
DEPENDENCIES = ('fastembed','onnxruntime','tokenizers','numpy')
INFERENCE = {'provider':'CPUExecutionProvider','threads':1,'pooling':'mean',
             'scoring':'normalized-cosine-float32','expected_dimensions':768}


def file_digest(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _inventory(root: Path) -> dict[str,str]:
    root=root.resolve(strict=True)
    paths={p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file()}
    if not REQUIRED <= paths.keys():
        raise ValueError(f'missing model files: {sorted(REQUIRED-paths.keys())}')
    if len(paths)>256:
        raise ValueError('model inventory exceeds 256 files')
    if any(not p.resolve().is_relative_to(root) for p in paths.values()):
        raise ValueError('export model symlinks as files before creating inventory')
    return {name:file_digest(path) for name,path in sorted(paths.items())}


def build_manifest(root: Path, revision: str | None = None) -> dict:
    if revision is not None and (len(revision)!=40 or any(c not in '0123456789abcdef' for c in revision)):
        raise ValueError('revision must be an immutable commit SHA, not a repository name')
    body={'schema_version':1,'model_name':MODEL_NAME,'hub_revision':revision,
          'files':_inventory(root),
          'versions':{name:importlib.metadata.version(name) for name in DEPENDENCIES},
          'inference':dict(INFERENCE),
          'calibration_transfer_validated':False}
    return {**body,'fingerprint':canonical_digest(body)}


def verify_manifest(root: Path, manifest: dict) -> dict:
    if manifest.get('schema_version')!=1 or manifest.get('model_name')!=MODEL_NAME:
        raise ValueError('unsupported model manifest')
    if manifest.get('inference') != INFERENCE:
        raise ValueError('unsupported inference contract')
    revision=manifest.get('hub_revision')
    if revision is not None and (not isinstance(revision,str) or len(revision)!=40
        or any(c not in '0123456789abcdef' for c in revision)):
        raise ValueError('invalid immutable model revision')
    body={k:v for k,v in manifest.items() if k!='fingerprint'}
    if canonical_digest(body)!=manifest.get('fingerprint'):
        raise ValueError('model manifest fingerprint mismatch')
    if _inventory(root)!=manifest.get('files'):
        raise ValueError('model file bytes do not match manifest')
    if manifest.get('versions')!={name:importlib.metadata.version(name) for name in DEPENDENCIES}:
        raise ValueError('model runtime versions do not match manifest')
    return dict(manifest)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--revision')
    args=parser.parse_args()
    if args.output.resolve().is_relative_to(args.model_dir.resolve()):
        parser.error('manifest must be outside the model directory')
    manifest=build_manifest(args.model_dir,args.revision)
    from .evaluation_v2 import save_new_report
    save_new_report(args.output,manifest)
    print(manifest['fingerprint'])


if __name__=='__main__':
    main()
