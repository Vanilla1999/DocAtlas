"""Existing real/oracle entry points must not silently exchange their meaning."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from experiments.crosslingual_relevance import m6_holdout as m6
from experiments.crosslingual_relevance import mpnet_scorer as mp


def test_default_m6_path_does_not_construct_gold_oracle(monkeypatch, tmp_path):
    def forbidden(task):
        raise AssertionError('gold oracle used by default real-model path')
    monkeypatch.setattr(m6, '_gold_scorer_factory', forbidden)
    monkeypatch.setattr(m6, 'observe_call', lambda *a,**k: ({'sources':[]}, {'snapshot':{}}))
    monkeypatch.setattr('eval.evidence_quality_v2.run.audit_payload',lambda *a,**k: [])
    result = m6._run_condition(object(),str(tmp_path),m6.HOLDOUT_TASKS[0],'dense_rescue')
    assert result['gold_oracle_used'] is False
    assert result['evaluation_kind'] == 'real_model_replay'


def test_real_model_without_pinned_local_artifacts_fails_before_loading(monkeypatch):
    monkeypatch.delenv('DOCATLAS_RELEVANCE_MODEL_MANIFEST',raising=False)
    monkeypatch.delenv('DOCATLAS_RELEVANCE_MODEL_DIR',raising=False)
    monkeypatch.setattr(mp,'_model',None)
    calls=[]
    monkeypatch.setattr('fastembed.TextEmbedding',lambda *a,**k: calls.append(k) or object())
    with pytest.raises((ValueError,RuntimeError)):
        mp._get_model()
    assert calls == []


def test_unloaded_model_is_not_advertised_as_pinned(monkeypatch):
    monkeypatch.setattr(mp,'_model',None)
    result=mp.model_identity()
    assert result.get('verified') is False
    assert result.get('fingerprint') is None


def test_zero_embedding_is_not_a_valid_cosine_observation(monkeypatch):
    fake=SimpleNamespace(embed=lambda inputs:[np.zeros(768,dtype=np.float32)])
    monkeypatch.setattr(mp,'_get_model',lambda:fake)
    with pytest.raises(ValueError):
        mp._embed('Some complete evidence.')
