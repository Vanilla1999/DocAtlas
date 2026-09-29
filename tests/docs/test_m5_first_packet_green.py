"""M5 — GREEN: gold in first packet via real get_docs_context + context rescue.

Proves that the two M0 RED tests (mixed-RU, pure-RU) become GREEN when:
1. Dense retrieval is enabled (finds gold candidates for RU questions)
2. Context-only admission rescue is installed (admits gold rejected by lexical filter)

Four causal combinations on the same corpus and budget:

| Retrieval | Admission  | Expected |
|-----------|-----------|----------|
| lexical   | baseline  | FAIL (M0 RED) |
| lexical   | rescue    | FAIL (no candidates to rescue) |
| dense     | baseline  | FAIL (candidates found, filtered by qualification) |
| dense     | rescue    | PASS (gold in packet, no coverage) |

Also: English control still passes, budget ≤ 800, answer_supported=False.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from eval.evidence_quality_v2.run import documents_for, load_protocol
from eval.evidence_quality_v2.runtime import write_project
from eval.evidence_quality_v2.observer import observe_call
from docmancer.docs.application.model_visible_projection import docs_context_budget_tokens

from experiments.crosslingual_relevance.context_rescue import installed, M2B_THRESHOLD


GOLD_PHRASES = (
    "only *CLI option* names to set the `False` value",
    "use a space and a single `/` and pass the negative name after",
)

MIXED_RU_QUESTION = (
    "Как записать только отрицательное имя boolean option: важен ли пробел перед /?"
)
PURE_RU_QUESTION = (
    "Как записать только отрицательное имя логического параметра: "
    "важен ли пробел перед косой чертой?"
)
EN_QUESTION = (
    "How to declare only the negative name for a boolean option: "
    "is the space before / significant?"
)

DENSE_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DENSE_DIM = 768


def _gold_scorer(question: str, evidence_text: str) -> float:
    """Stub scorer: 0.9 for gold passage, 0.1 for others."""
    if any(phrase in evidence_text for phrase in GOLD_PHRASES):
        return 0.9
    return 0.1


def _typer_project(tmp_path):
    _, _, manifest = load_protocol()
    docs = documents_for("typer", manifest)
    root = tmp_path / "project"
    write_project(root, docs)
    return root


def _build_vector_service(tmp_path):
    """Build a LibraryDocsService with dense retrieval and vectors enabled."""
    import scripts.run_project_docs_self_host_gate as gate
    from docmancer.core.config import VectorStoreConfig
    from docmancer.core.product_identity import ensure_owned_home

    state = tmp_path / "vstate"
    state.mkdir(parents=True, exist_ok=True)
    home_dir = tmp_path / "vhome"
    home_dir.mkdir(parents=True, exist_ok=True)
    env = {key: str(state / key.lower()) for key in
           ('HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME')}
    env['DOCATLAS_HOME'] = str(home_dir)
    env['DOCATLAS_FASTEMBED_CACHE_DIR'] = "/tmp/fastembed_cache"
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
        config.retrieval.max_sections_per_source = 20
        config.embeddings.provider = "fastembed"
        config.embeddings.model = DENSE_MODEL
        config.embeddings.dimensions = DENSE_DIM
        config.embeddings.sparse_model = None
        config.embeddings.cache = "/tmp/fastembed_cache"
        config.vector_store = VectorStoreConfig(
            provider="sqlite-vec",
            collection=f"m5_{uuid.uuid4().hex[:8]}",
        )
        service = gate.LibraryDocsService(
            config=config, config_source='explicit',
            registry=gate.LibraryRegistry(config.index.db_path),
            agent=gate.DocmancerAgent(config=config),
            job_tracker=gate.DocsJobTracker(),
        )
        return service, config, patcher
    except Exception:
        patcher.stop()
        raise


def _index_with_vectors(service, config, root):
    """Index project docs with vectors through the real service."""
    result = service.sync_project_docs(str(root), with_vectors=True)
    if result.status != 'success':
        raise RuntimeError(f"index failed: {result.status}")


def _call(service, root, question):
    request = {"question": question, "project_path": str(root), "scope": "all"}
    payload, trace = observe_call(service, request)
    return payload, trace


def _assert_gold_in_first_packet(payload):
    visible = "\n\n".join(s["snippet"] for s in payload.get("sources", []))
    for phrase in GOLD_PHRASES:
        assert phrase in visible, f"gold phrase missing from first packet: {phrase!r}"
    assert docs_context_budget_tokens(payload) <= 800, "budget exceeds 800 tokens"
    assert payload["answer_supported"] is False, "rescue must not raise answer_supported"
    assert payload.get("edit_ready", False) is False, "rescue must not raise edit_ready"


# ---------------------------------------------------------------------------
# Combination 1: lexical + baseline → FAIL (M0 RED, already proven)
# ---------------------------------------------------------------------------
def test_lexical_baseline_mixed_ru_fails(tmp_path):
    """Lexical retrieval + baseline admission → mixed-RU gold absent."""
    from eval.evidence_quality_v2.runtime import isolated_service, index_project
    root = _typer_project(tmp_path)
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        payload, _trace = _call(service, root, MIXED_RU_QUESTION)
    visible = "\n\n".join(s["snippet"] for s in payload.get("sources", []))
    assert GOLD_PHRASES[0] not in visible, "lexical baseline should not find gold for mixed-RU"


# ---------------------------------------------------------------------------
# Combination 2: lexical + rescue → FAIL (no candidates to rescue)
# ---------------------------------------------------------------------------
def test_lexical_rescue_mixed_ru_fails(tmp_path):
    """Lexical retrieval + rescue → still fails (no gold candidates in pool)."""
    from eval.evidence_quality_v2.runtime import isolated_service, index_project
    root = _typer_project(tmp_path)
    with isolated_service(tmp_path / "state") as (service, config):
        index_project(service, config, root)
        with installed(_gold_scorer, threshold=M2B_THRESHOLD, question=MIXED_RU_QUESTION):
            payload, _trace = _call(service, root, MIXED_RU_QUESTION)
    visible = "\n\n".join(s["snippet"] for s in payload.get("sources", []))
    assert GOLD_PHRASES[0] not in visible, (
        "lexical + rescue should still fail: no gold candidates in pool"
    )


# ---------------------------------------------------------------------------
# Combination 3: dense + baseline → FAIL (candidates found, filtered by qualification)
# ---------------------------------------------------------------------------
def test_dense_baseline_mixed_ru_fails(tmp_path):
    """Dense retrieval + baseline admission → candidates found but filtered out."""
    root = _typer_project(tmp_path)
    service, config, patcher = _build_vector_service(tmp_path)
    try:
        _index_with_vectors(service, config, root)
        payload, trace = _call(service, root, MIXED_RU_QUESTION)
        # Gold should be in retrieved candidates but not in final sources
        rc = trace.get("stages", {}).get("retrieved_candidates", [])
        gold_in_candidates = any(
            any(p in (s.get("snippet") or "") for p in GOLD_PHRASES)
            for e in rc for s in e.get("sources", [])
        )
        visible = "\n\n".join(s["snippet"] for s in payload.get("sources", []))
        assert gold_in_candidates, "dense should find gold in candidates"
        assert GOLD_PHRASES[0] not in visible, (
            "dense + baseline should filter gold out via qualification"
        )
    finally:
        patcher.stop()


# ---------------------------------------------------------------------------
# Combination 4: dense + rescue → PASS (target result)
# ---------------------------------------------------------------------------
def test_dense_rescue_mixed_ru_passes(tmp_path):
    """Dense retrieval + context rescue → gold in first packet, no coverage."""
    root = _typer_project(tmp_path)
    service, config, patcher = _build_vector_service(tmp_path)
    try:
        _index_with_vectors(service, config, root)
        with installed(_gold_scorer, threshold=M2B_THRESHOLD, question=MIXED_RU_QUESTION):
            payload, _trace = _call(service, root, MIXED_RU_QUESTION)
        _assert_gold_in_first_packet(payload)
    finally:
        patcher.stop()


def test_dense_rescue_pure_ru_passes(tmp_path):
    """Dense retrieval + context rescue → pure-RU gold in first packet."""
    root = _typer_project(tmp_path)
    service, config, patcher = _build_vector_service(tmp_path)
    try:
        _index_with_vectors(service, config, root)
        with installed(_gold_scorer, threshold=M2B_THRESHOLD, question=PURE_RU_QUESTION):
            payload, _trace = _call(service, root, PURE_RU_QUESTION)
        _assert_gold_in_first_packet(payload)
    finally:
        patcher.stop()


# ---------------------------------------------------------------------------
# English control still passes with dense + rescue
# ---------------------------------------------------------------------------
def test_dense_rescue_english_control_passes(tmp_path):
    """English control: dense + rescue should not break existing PASS."""
    root = _typer_project(tmp_path)
    service, config, patcher = _build_vector_service(tmp_path)
    try:
        _index_with_vectors(service, config, root)
        with installed(_gold_scorer, threshold=M2B_THRESHOLD, question=EN_QUESTION):
            payload, _trace = _call(service, root, EN_QUESTION)
        _assert_gold_in_first_packet(payload)
    finally:
        patcher.stop()


# ---------------------------------------------------------------------------
# No coverage: rescue does not create answer_supported or covered_query_ids
# ---------------------------------------------------------------------------
def test_dense_rescue_no_coverage(tmp_path):
    """Rescued sources must not create attributable coverage."""
    from docmancer.docs.application.context_selection import attributable_query_ids
    root = _typer_project(tmp_path)
    service, config, patcher = _build_vector_service(tmp_path)
    try:
        _index_with_vectors(service, config, root)
        with installed(_gold_scorer, threshold=M2B_THRESHOLD, question=MIXED_RU_QUESTION):
            payload, trace = _call(service, root, MIXED_RU_QUESTION)
        assert payload["answer_supported"] is False
        assert payload.get("edit_ready", False) is False
        # No covered_query_ids from rescue
        covered = payload.get("covered_query_ids", [])
        assert not covered, f"rescue must not create covered_query_ids; got {covered}"
    finally:
        patcher.stop()
