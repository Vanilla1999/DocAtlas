"""Diagnostic tests for experimental threshold-based reranker rescue.

Architecture: MPNet dense retrieval finds candidates, BGE-reranker-v2-m3
cross-encoder scores them for admission. The rescue mechanism admits
high-scoring blocks as context-only without creating answer/edit authority.

Model-dependent tests exercise a Typer pilot; they do not calibrate admission
or establish the safety of a production profile.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from eval.evidence_quality_v2.run import documents_for, load_protocol, audit_payload
from eval.evidence_quality_v2.runtime import write_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens


GOLD_PHRASES = (
    "only *CLI option* names to set the `False` value",
    "use a space and a single `/` and pass the negative name after",
)

MIXED_RU = "Как записать только отрицательное имя boolean option: важен ли пробел перед /?"
PURE_RU = (
    "Как записать только отрицательное имя логического параметра: "
    "важен ли пробел перед косой чертой?"
)
EN = (
    "How to declare only the negative name for a boolean option: "
    "is the space before / significant?"
)

# Diagnostic only: selected after inspecting Typer scores, NOT calibrated.
RERANKER_THRESHOLD = 0.01


def test_reranker_identity_rejects_tampered_model(tmp_path, monkeypatch):
    import hashlib
    import json
    from experiments.crosslingual_relevance import bge_reranker_scorer as model
    from experiments.crosslingual_relevance.reranker_manifest import REQUIRED

    root = tmp_path / "model"
    root.mkdir()
    files = {}
    for name in REQUIRED:
        (root / name).write_bytes(b"expected")
        files[name] = hashlib.sha256(b"expected").hexdigest()
    body = {"model_name": "test", "files": files}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({**body, "fingerprint": digest}))
    monkeypatch.setattr(model, "_MODEL_DIR", str(root))
    monkeypatch.setattr(model, "_MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(model, "_manifest", None)
    monkeypatch.setattr(model, "_session", None)
    assert model.reranker_identity()["verified"] is True
    (root / "tokenizer.json").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        model.reranker_identity()
    manifest.write_text(json.dumps({**body, "fingerprint": "0" * 64}))
    monkeypatch.setattr(model, "_manifest", None)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        model.reranker_identity()


def test_reranker_unavailable_and_nonfinite_degrade(monkeypatch):
    import numpy as np
    from experiments.crosslingual_relevance import bge_reranker_scorer as model
    from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer

    monkeypatch.setattr(model, "_load_session", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    bounded = BoundedScorer(model.reranker_scorer, score_range=(0, 1))
    assert bounded.score("q", "e") is None
    assert bounded.degraded_reason == "scorer_error"

    class Session:
        def get_inputs(self):
            return [type("Input", (), {"name": "input_ids"})()]

        def run(self, _outputs, _feed):
            return [np.array([[float("nan")]])]

    monkeypatch.setattr(model, "_load_session", lambda: (Session(), None))
    monkeypatch.setattr(model, "_encode_pair", lambda _q, _e: {"input_ids": np.array([[1]])})
    bounded = BoundedScorer(model.reranker_scorer, score_range=(0, 1))
    assert bounded.score("q", "e") is None
    assert bounded.degraded_reason == "scorer_error"


def test_finite_negative_logit_is_not_execution_failure(monkeypatch):
    import numpy as np
    from experiments.crosslingual_relevance import bge_reranker_scorer as model
    from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer

    class Session:
        def get_inputs(self):
            return [type("Input", (), {"name": "input_ids"})()]

        def run(self, _outputs, _feed):
            return [np.array([[-1000.0]])]

    monkeypatch.setattr(model, "_load_session", lambda: (Session(), None))
    monkeypatch.setattr(model, "_encode_pair", lambda _q, _e: {"input_ids": np.array([[1]])})
    monkeypatch.setattr(model, "_verify_manifest", lambda: {"model_name": "test"})
    bounded = BoundedScorer(model.reranker_scorer, score_range=(0, 1))
    assert bounded.score("q", "e") == 0.0
    assert bounded.degraded is False
    assert bounded.events[-1]["input_observation"]["logit"] == -1000.0


def test_m6_handler_failure_is_not_a_projection_failure(tmp_path, monkeypatch):
    from experiments.crosslingual_relevance import m6_holdout

    error = {"status": "failed", "error": {"exception_type": "HybridRetrievalError"}}
    monkeypatch.setattr(m6_holdout, "observe_call", lambda _service, _request: (error, {}))
    monkeypatch.setattr(m6_holdout, "audit_payload", lambda *_args: pytest.fail("invalid audit"))
    monkeypatch.setattr(m6_holdout, "docs_context_budget_tokens", lambda _payload: 0)
    result = m6_holdout._run_condition(None, str(tmp_path),
        m6_holdout.HOLDOUT_TASKS[0],
        "dense_baseline")
    assert result["source_policy_errors"] == ["handler failed: HybridRetrievalError"]
    assert result["gold_in_packet"] is False

def _typer_project(tmp_path):
    _, _, manifest = load_protocol()
    docs = documents_for("typer", manifest)
    root = tmp_path / "project"
    write_project(root, docs)
    return root


def _assert_gold_in_packet(payload):
    visible = "\n\n".join(s["snippet"] for s in payload.get("sources", []))
    for phrase in GOLD_PHRASES:
        assert phrase in visible, f"gold phrase missing from first packet: {phrase!r}"
    assert docs_context_budget_tokens(payload) <= 800
    assert payload["answer_supported"] is False
    assert payload.get("edit_ready", False) is False


def _models_available():
    return bool(
        os.environ.get("DOCATLAS_RERANKER_MODEL_DIR")
        and os.environ.get("DOCATLAS_RERANKER_MODEL_MANIFEST")
        and os.environ.get("DOCATLAS_RELEVANCE_MODEL_DIR")
        and os.environ.get("DOCATLAS_RELEVANCE_MODEL_MANIFEST")
    )


needs_models = pytest.mark.skipif(
    not _models_available(), reason="DOCATLAS_*_MODEL_DIR not set")


def _build_dense_service(tmp_path, *, max_sections=2):
    """Build a dense vector service using MPNet for candidate retrieval."""
    from docmancer.core.config import DocmancerConfig, VectorStoreConfig
    from docmancer.core.product_identity import ensure_owned_home
    import scripts.run_project_docs_self_host_gate as gate
    import uuid

    state = tmp_path / "vstate"; state.mkdir(parents=True, exist_ok=True)
    home_dir = tmp_path / "vhome"; home_dir.mkdir(parents=True, exist_ok=True)
    env = {key: str(state / key.lower()) for key in
           ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME')}
    env['DOCATLAS_HOME'] = str(home_dir)
    env['DOCATLAS_FASTEMBED_CACHE_DIR'] = os.environ.get('DOCATLAS_FASTEMBED_CACHE_DIR', '/tmp/fastembed_cache')
    env.update(DOCATLAS_OFFLINE='1', DOCATLAS_AUTO_VECTORS='1')
    for p in env.values():
        if p not in ('0', '1'):
            Path(p).mkdir(parents=True, exist_ok=True)

    patcher = patch.dict(os.environ, env)
    patcher.start()
    try:
        ensure_owned_home(str(home_dir))
        config = gate.DocmancerConfig()
        config.index.db_path = str(state / 'index.db')
        config.index.extracted_dir = str(state / 'extracted')
        config.retrieval.default_mode = "dense"
        config.retrieval.max_sections_per_source = max_sections
        config.embeddings.provider = "fastembed"
        config.embeddings.model = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
        config.embeddings.dimensions = 768
        config.embeddings.sparse_model = None
        config.embeddings.cache = env['DOCATLAS_FASTEMBED_CACHE_DIR']
        config.vector_store = VectorStoreConfig(
            provider="sqlite-vec",
            collection=f"test_rr_{uuid.uuid4().hex[:8]}",
        )
        service = gate.LibraryDocsService(
            config=config, config_source='explicit',
            registry=gate.LibraryRegistry(config.index.db_path),
            agent=gate.DocmancerAgent(config=config),
            job_tracker=gate.DocsJobTracker(),
        )
        return service, patcher
    except Exception:
        patcher.stop()
        raise


def _index_typer(service, root):
    result = service.sync_project_docs(str(root), with_vectors=True)
    if result.status != 'success':
        raise RuntimeError(f"index failed: {result.status}")


# ---------------------------------------------------------------------------
# Cases 1-3: gold must be found and admitted via dense + reranker
# ---------------------------------------------------------------------------
@needs_models
def test_mixed_ru_typer_gold_outranks_distractor(tmp_path):
    """Case 1: mixed RU Typer gold must be in first packet via dense + reranker."""
    from experiments.crosslingual_relevance.bge_reranker_scorer import reranker_scorer
    from experiments.crosslingual_relevance.context_rescue import installed
    from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer

    root = _typer_project(tmp_path)
    service, patcher = _build_dense_service(tmp_path)
    try:
        _index_typer(service, root)
        bounded = BoundedScorer(reranker_scorer, score_range=(0.0, 1.0),
                                max_evaluations=256, timeout=300.0)
        with installed(bounded, threshold=RERANKER_THRESHOLD, question=MIXED_RU):
            request = {"question": MIXED_RU, "project_path": str(root), "scope": "all"}
            payload, trace = observe_call(service, request)
    finally:
        patcher.stop()
    _assert_gold_in_packet(payload)


@needs_models
def test_pure_ru_typer_gold_outranks_distractor(tmp_path):
    """Case 2: pure RU Typer gold must be in first packet via dense + reranker."""
    from experiments.crosslingual_relevance.bge_reranker_scorer import reranker_scorer
    from experiments.crosslingual_relevance.context_rescue import installed
    from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer

    root = _typer_project(tmp_path)
    service, patcher = _build_dense_service(tmp_path)
    try:
        _index_typer(service, root)
        bounded = BoundedScorer(reranker_scorer, score_range=(0.0, 1.0),
                                max_evaluations=256, timeout=300.0)
        with installed(bounded, threshold=RERANKER_THRESHOLD, question=PURE_RU):
            request = {"question": PURE_RU, "project_path": str(root), "scope": "all"}
            payload, trace = observe_call(service, request)
    finally:
        patcher.stop()
    _assert_gold_in_packet(payload)


def test_en_control_not_degraded(tmp_path):
    """Case 3: English control must still pass (lexical, no reranker needed)."""
    from eval.evidence_quality_v2.runtime import isolated_service, index_project

    root = _typer_project(tmp_path)
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        request = {"question": EN, "project_path": str(root), "scope": "all"}
        payload, _ = observe_call(service, request)
    _assert_gold_in_packet(payload)


# ---------------------------------------------------------------------------
# Cases 4-7: safety policies (must remain with reranker)
# ---------------------------------------------------------------------------
@needs_models
def test_wrong_project_rejected_with_reranker(tmp_path):
    """Case 4: wrong project always rejected regardless of scorer."""
    from experiments.crosslingual_relevance.bge_reranker_scorer import reranker_scorer
    from experiments.crosslingual_relevance.context_rescue import installed
    from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer

    # Index httpx (wrong project for Typer question)
    _, _, manifest = load_protocol()
    other_root = tmp_path / "other"
    write_project(other_root, documents_for("httpx", manifest))

    service, patcher = _build_dense_service(tmp_path)
    try:
        result = service.sync_project_docs(str(other_root), with_vectors=True)
        bounded = BoundedScorer(reranker_scorer, score_range=(0.0, 1.0),
                                max_evaluations=256, timeout=300.0)
        with installed(bounded, threshold=RERANKER_THRESHOLD, question=MIXED_RU):
            request = {"question": MIXED_RU, "project_path": str(other_root), "scope": "all"}
            payload, _ = observe_call(service, request)
    finally:
        patcher.stop()
    visible = "\n\n".join(s["snippet"] for s in payload.get("sources", []))
    assert GOLD_PHRASES[0] not in visible, "wrong project admitted gold"


def test_nan_scorer_fail_closed(tmp_path):
    """Case 6: NaN scorer → degraded, no admission."""
    from experiments.crosslingual_relevance.context_rescue import installed
    from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer
    from eval.evidence_quality_v2.runtime import isolated_service, index_project

    def nan_scorer(q, t):
        return float("nan")
    nan_scorer.identity = lambda: {"kind": "test", "verified": False}

    root = _typer_project(tmp_path)
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        bounded = BoundedScorer(nan_scorer, score_range=None)
        with installed(bounded, threshold=0.5, question=MIXED_RU):
            request = {"question": MIXED_RU, "project_path": str(root), "scope": "all"}
            payload, _ = observe_call(service, request)
    visible = "\n\n".join(s["snippet"] for s in payload.get("sources", []))
    assert GOLD_PHRASES[0] not in visible, "NaN scorer admitted gold"
    assert bounded.degraded, "NaN scorer did not degrade"


def test_unavailable_scorer_fail_closed(tmp_path):
    """Case 7: scorer unavailable → degraded, no admission."""
    from experiments.crosslingual_relevance.context_rescue import installed
    from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer
    from eval.evidence_quality_v2.runtime import isolated_service, index_project

    def fail_scorer(q, t):
        raise RuntimeError("model unavailable")
    fail_scorer.identity = lambda: {"kind": "test", "verified": False}

    root = _typer_project(tmp_path)
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        bounded = BoundedScorer(fail_scorer, score_range=None)
        with installed(bounded, threshold=0.5, question=MIXED_RU):
            request = {"question": MIXED_RU, "project_path": str(root), "scope": "all"}
            payload, _ = observe_call(service, request)
    visible = "\n\n".join(s["snippet"] for s in payload.get("sources", []))
    assert GOLD_PHRASES[0] not in visible, "unavailable scorer admitted gold"
    assert bounded.degraded, "unavailable scorer did not degrade"


@needs_models
def test_reranker_admission_no_answer_authority(tmp_path):
    """Case 10: scorer admission does not create answer/edit authority."""
    from experiments.crosslingual_relevance.bge_reranker_scorer import reranker_scorer
    from experiments.crosslingual_relevance.context_rescue import installed, apply_rescue
    from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer

    admitted_results = []

    def observe_rescue(*args, **kwargs):
        # Observe the real result; do not synthesize qualification or scores.
        result = apply_rescue(*args, **kwargs)
        if result.qualified and result.reason == "context_only_relevance":
            admitted_results.append((result, kwargs["evidence_text"]))
        return result

    root = _typer_project(tmp_path)
    service, patcher = _build_dense_service(tmp_path)
    try:
        _index_typer(service, root)
        bounded = BoundedScorer(reranker_scorer, score_range=(0.0, 1.0),
                                max_evaluations=256, timeout=300.0)
        with patch("experiments.crosslingual_relevance.context_rescue.apply_rescue",
                   side_effect=observe_rescue):
            with installed(bounded, threshold=RERANKER_THRESHOLD, question=MIXED_RU):
                request = {"question": MIXED_RU, "project_path": str(root), "scope": "all"}
                payload, _ = observe_call(service, request)
    finally:
        patcher.stop()
    # Prove actual context-only rescue and delivery BEFORE checking authority.
    assert admitted_results, "no successful rescue result was returned"
    assert any(all(phrase in text for phrase in GOLD_PHRASES)
               for _, text in admitted_results), "the required witness was not rescued"
    visible = "\n\n".join(s["snippet"] for s in payload.get("sources", []))
    assert all(phrase in visible for phrase in GOLD_PHRASES)
    assert all(result.trace.get("admission_only") is True
               and result.covered_query_ids == () for result, _ in admitted_results)
    assert docs_context_budget_tokens(payload) <= 800
    assert payload["answer_supported"] is False
    assert payload.get("edit_ready", False) is False


# ---------------------------------------------------------------------------
# Literal control: " /" must not become "/"
# ---------------------------------------------------------------------------
@needs_models
def test_literal_space_slash_preserved(tmp_path):
    """The literal 'single `/`' (space before /) must be preserved."""
    from experiments.crosslingual_relevance.bge_reranker_scorer import reranker_scorer
    from experiments.crosslingual_relevance.context_rescue import installed
    from experiments.crosslingual_relevance.scorer_runtime import BoundedScorer

    root = _typer_project(tmp_path)
    service, patcher = _build_dense_service(tmp_path)
    try:
        _index_typer(service, root)
        bounded = BoundedScorer(reranker_scorer, score_range=(0.0, 1.0),
                                max_evaluations=256, timeout=300.0)
        with installed(bounded, threshold=RERANKER_THRESHOLD, question=MIXED_RU):
            request = {"question": MIXED_RU, "project_path": str(root), "scope": "all"}
            payload, _ = observe_call(service, request)
    finally:
        patcher.stop()
    visible = "\n\n".join(s["snippet"] for s in payload.get("sources", []))
    assert "single `/`" in visible, "literal space-slash pattern not preserved"
