"""Isolated experiment injection: index and scorer share checked model bytes.

Not a production activation or a new provider registry. Other threads do not
inherit this request's provider. A concurrent/nested experiment fails closed.
"""
from contextlib import contextmanager
import threading
import numpy as np
from unittest.mock import patch
from .mpnet_scorer import _get_model, model_identity, MODEL_NAME

_LOCK=threading.Lock()

@contextmanager
def pinned_embeddings():
    if not _LOCK.acquire(blocking=False):
        raise RuntimeError('pinned embedding experiment is already active')
    try:
        model=_get_model()
        identity=model_identity()
        if not identity.get('verified'):
            raise RuntimeError('model identity not verified')
        import docmancer.embeddings as embedding_api
        from docmancer.embeddings.fastembed_provider import FastEmbedProvider
        original=embedding_api.get_embeddings_provider
        owner=threading.get_ident()
        def factory(config):
            if threading.get_ident()!=owner or config.provider!='fastembed' or config.model!=MODEL_NAME:
                return original(config)
            provider=FastEmbedProvider(config)
            provider._dense=model
            # Production provider tolerates a failed dimension probe. This
            # experiment must fail closed rather than retain a config hint.
            vectors=list(model.embed(['dim-probe']))
            if len(vectors)!=1:
                raise ValueError('pinned model did not produce one probe vector')
            vector=np.asarray(vectors[0],dtype=np.float32)
            if vector.shape!=(768,) or not np.all(np.isfinite(vector)) or not np.linalg.norm(vector)>0:
                raise ValueError('invalid pinned embedding probe')
            provider.dimensions=768
            provider._dimensions_resolved=True
            return provider
        with patch.object(embedding_api,'get_embeddings_provider',factory):
            yield identity
    finally:
        _LOCK.release()
