"""Real MPNet cosine scorer with pinned local files and actual input telemetry.

Cosine is in [-1, 1], NOT a probability. The archived 0.7453 threshold is not
changed or declared transferable. New fingerprints cannot retrospectively prove
which model bytes produced historical M2 scores.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import threading
import numpy as np

from .model_manifest import MODEL_NAME, canonical_digest, verify_manifest

_MODEL_NAME=MODEL_NAME
_model=None
_identity=None
_loaded_key=None
_observation=threading.local()


def _get_model():
    global _model, _identity, _loaded_key
    directory=os.environ.get('DOCATLAS_RELEVANCE_MODEL_DIR')
    manifest_path=os.environ.get('DOCATLAS_RELEVANCE_MODEL_MANIFEST')
    if not directory or not manifest_path:
        raise RuntimeError('Pinned local model required: set DOCATLAS_RELEVANCE_MODEL_DIR and DOCATLAS_RELEVANCE_MODEL_MANIFEST')
    root=Path(directory).resolve(strict=True)
    manifest_bytes=Path(manifest_path).read_bytes()
    key=(str(root),hashlib.sha256(manifest_bytes).hexdigest())
    if _model is not None:
        if key!=_loaded_key:
            raise RuntimeError('model lock changed inside a process; start a new experiment')
        return _model
    manifest=verify_manifest(root,json.loads(manifest_bytes))
    from fastembed import TextEmbedding
    model=TextEmbedding(model_name=MODEL_NAME,specific_model_path=str(root),
        local_files_only=True,providers=['CPUExecutionProvider'],threads=1)
    tokenizer=model.model.tokenizer
    if tokenizer is None:
        raise RuntimeError('loaded scorer has no tokenizer')
    identity={**manifest,'verified':True,'model_dir':str(root),
              'runtime_tokenizer_sha256':hashlib.sha256(tokenizer.to_str().encode()).hexdigest(),
              'runtime_truncation':tokenizer.truncation,'runtime_padding':tokenizer.padding,
              'loaded_backend':type(model.model).__name__}
    # Bind runtime tokenization/pooling state as well as the actual weight bytes.
    identity['artifact_fingerprint']=manifest['fingerprint']
    identity['fingerprint']=canonical_digest({k:v for k,v in identity.items() if k not in {'model_dir','fingerprint'}})
    _model,_identity,_loaded_key=model,identity,key
    return _model


def token_observation(tokenizer, text: str) -> dict:
    """Inspect the same tokenizer input, retaining a separate untruncated count."""
    from tokenizers import Tokenizer
    used=tokenizer.encode(text)
    unbounded=Tokenizer.from_str(tokenizer.to_str())
    unbounded.no_truncation();unbounded.no_padding()
    full=unbounded.encode(text)
    active=[(i,o) for i,o,m in zip(used.ids,used.offsets,used.attention_mask) if m]
    return {'input_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'full_token_count':len(full.ids),'used_token_count':len(active),
            'truncated':len(active)<len(full.ids),'truncation':tokenizer.truncation,
            'consumed_ids':[i for i,_ in active], 'consumed_offsets':[list(o) for _,o in active]}


def _embed(text: str) -> np.ndarray:
    model=_get_model()
    vector=np.asarray(list(model.embed([text]))[0],dtype=np.float32)
    if vector.ndim!=1 or len(vector)!=768 or not np.all(np.isfinite(vector)):
        raise ValueError('invalid model embedding shape or finite values')
    norm=float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm<=0:
        raise ValueError('zero or invalid embedding norm')
    return vector/norm


def mpnet_scorer(question: str, evidence_text: str) -> float:
    model=_get_model()
    _observation.value={'question':token_observation(model.model.tokenizer,question),
                        'evidence':token_observation(model.model.tokenizer,evidence_text)}
    score=float(np.dot(_embed(question),_embed(evidence_text)))
    if not np.isfinite(score):
        raise ValueError('nonfinite cosine')
    # Only numerical roundoff of normalized float32 vectors is clipped.
    if not -1.000001 <= score <= 1.000001:
        raise ValueError('invalid cosine range')
    return float(np.clip(score,-1,1))


def model_identity() -> dict:
    if _model is None or _identity is None:
        return {'model_name':MODEL_NAME,'verified':False,'fingerprint':None,
                'reason':'not_loaded_or_manifest_not_verified'}
    return deepcopy(_identity)


def last_observation() -> dict:
    return deepcopy(getattr(_observation,'value',{}))


mpnet_scorer.identity=model_identity
mpnet_scorer.last_observation=last_observation
