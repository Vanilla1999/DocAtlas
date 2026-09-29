"""Local model adapter contracts; fake vectors test plumbing, not model quality."""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from docmancer.core.config import EmbeddingsConfig
from experiments.crosslingual_relevance import pinned_embedding_session as session
from experiments.crosslingual_relevance.model_manifest import (
    REQUIRED, MODEL_NAME, build_manifest, canonical_digest, verify_manifest,
)
from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer


def test_self_consistent_but_unsupported_inference_lock_is_rejected(tmp_path):
    for name in REQUIRED:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('dummy artifact for manifest-only test')
    manifest = build_manifest(tmp_path)
    manifest['inference']['pooling'] = 'invented-pooling'
    manifest['fingerprint'] = canonical_digest({k:v for k,v in manifest.items() if k != 'fingerprint'})
    with pytest.raises(ValueError, match='inference'):
        verify_manifest(tmp_path, manifest)


def prepare(monkeypatch, model):
    monkeypatch.setattr(session, '_get_model', lambda:model)
    monkeypatch.setattr(session, 'model_identity', lambda:{'verified':True,'fingerprint':'a'*64})
    return EmbeddingsConfig(provider='fastembed', model=MODEL_NAME, dimensions=768)


def test_real_provider_reuses_exact_checked_model_object(monkeypatch):
    import docmancer.embeddings as api
    model = SimpleNamespace(embed=lambda inputs, **kwargs:[np.ones(768,dtype=np.float32) for _ in inputs])
    config = prepare(monkeypatch, model)
    before = api.get_embeddings_provider
    with session.pinned_embeddings():
        provider = api.get_embeddings_provider(config)
        assert provider._dense is model
        assert len(provider.embed_query('a real query string')) == 768
    assert api.get_embeddings_provider is before


def test_invalid_provider_probe_cannot_silently_keep_declared_dimensions(monkeypatch):
    import docmancer.embeddings as api
    def broken(inputs):
        raise ValueError('broken inference')
    config = prepare(monkeypatch, SimpleNamespace(embed=broken))
    with session.pinned_embeddings():
        with pytest.raises(ValueError):
            api.get_embeddings_provider(config)


def test_token_telemetry_failure_fails_closed():
    def scorer(q,t):
        return .9
    def broken():
        raise RuntimeError('cannot observe tokenizer')
    scorer.last_observation = broken
    bounded = BoundedScorer(scorer)
    assert bounded.score('q','text') is None
    assert bounded.degraded_reason == 'scorer_telemetry_error'
