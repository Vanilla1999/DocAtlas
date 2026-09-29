"""BGE-reranker-v2-m3 cross-encoder scorer for relevance ranking.

Loads the local ONNX model directly via onnxruntime + tokenizers.
Computes a relevance score for a (question, evidence) pair as a sigmoid(logit).

BoundedScorer handles score caching and fail-closed errors.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path

import numpy as np

_MODEL_DIR: str | None = None
_MANIFEST_PATH: str | None = None
_session = None
_tokenizer = None
_manifest = None
_last_score_observation: dict | None = None


def _config():
    global _MODEL_DIR, _MANIFEST_PATH
    if _MODEL_DIR is None:
        _MODEL_DIR = os.environ.get("DOCATLAS_RERANKER_MODEL_DIR", "")
    if _MANIFEST_PATH is None:
        _MANIFEST_PATH = os.environ.get("DOCATLAS_RERANKER_MODEL_MANIFEST", "")
    return _MODEL_DIR, _MANIFEST_PATH


def _verify_manifest() -> dict:
    global _manifest
    if _manifest is not None:
        return _manifest
    _, manifest_path = _config()
    if not manifest_path or not Path(manifest_path).exists():
        raise ValueError("reranker manifest not found")
    body = json.loads(Path(manifest_path).read_text())
    fingerprint = body.get("fingerprint")
    content = {key: value for key, value in body.items() if key != "fingerprint"}
    actual = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if fingerprint != actual:
        raise ValueError("reranker manifest fingerprint mismatch")
    _manifest = body
    return _manifest


def _load_session():
    global _session, _tokenizer
    if _session is not None and _tokenizer is not None:
        return _session, _tokenizer
    model_dir, _ = _config()
    if not model_dir or not Path(model_dir).exists():
        raise ValueError("reranker model dir not found")
    model_dir = Path(model_dir)
    import onnxruntime as ort

    _verify_model_files(model_dir)

    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_dir / "model.onnx"),
        sess_options=so,
        providers=["CPUExecutionProvider"],
    )

    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
    _session, _tokenizer = session, tokenizer
    return _session, _tokenizer


def _verify_model_files(model_dir: Path) -> None:
    from .reranker_manifest import REQUIRED, file_digest
    files = _verify_manifest().get("files")
    if not isinstance(files, dict) or not REQUIRED <= files.keys():
        raise ValueError("incomplete reranker model manifest")
    for name, expected_hash in files.items():
        p = model_dir / name
        if not p.is_file() or not p.resolve().is_relative_to(model_dir.resolve()):
            raise ValueError(f"missing or external model file: {name}")
        if file_digest(p) != expected_hash:
            raise ValueError(f"model file hash mismatch: {name}")


def _encode_pair(question: str, evidence: str) -> dict:
    session, tokenizer = _load_session()
    enc = tokenizer.encode(question, evidence)
    input_ids = np.array([enc.ids], dtype=np.int64)
    attention_mask = np.array([enc.attention_mask], dtype=np.int64)
    token_type_ids = np.array([enc.type_ids], dtype=np.int64)
    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "token_type_ids": token_type_ids,
    }


def reranker_scorer(question: str, evidence_text: str) -> float:
    """Cross-encoder relevance score: sigmoid(logit) in [0, 1].

    Errors propagate to BoundedScorer which marks degraded and returns None.
    NaN/inf are rejected by BoundedScorer's score_range or nonfinite checks.
    """
    session, _ = _load_session()
    inputs = _encode_pair(question, evidence_text)

    input_names = [i.name for i in session.get_inputs()]
    feed = {}
    for key, val in inputs.items():
        for name in input_names:
            if key == name and name not in feed:
                feed[name] = val
                break

    outputs = session.run(None, feed)
    logit = float(np.asarray(outputs[0]).flatten()[0])

    if not math.isfinite(logit):
        raise ValueError(f"nonfinite logit: {logit}")

    if logit >= 0:
        score = 1.0 / (1.0 + math.exp(-logit))
    else:
        exp_logit = math.exp(logit)
        score = exp_logit / (1.0 + exp_logit)
    if not math.isfinite(score) or score < 0.0 or score > 1.0:
        raise ValueError(f"sigmoid out of range: {score}")

    global _last_score_observation
    _last_score_observation = {"logit": logit, "score": score, "model_name": _verify_manifest()["model_name"]}
    return score


def reranker_identity() -> dict:
    model_dir, _ = _config()
    if not model_dir or not Path(model_dir).is_dir():
        raise ValueError("reranker model dir not found")
    if _session is None:
        _verify_model_files(Path(model_dir))
    manifest = _verify_manifest()
    return {
        "model_name": manifest["model_name"],
        "onnx_source": manifest.get("onnx_source", ""),
        "fingerprint": manifest["fingerprint"],
        "verified": True,
        "scoring": "cross-encoder-sigmoid-float32",
    }


def _last_observation() -> dict | None:
    return _last_score_observation


# Attach identity and observation hooks so BoundedScorer can verify the model.
reranker_scorer.identity = reranker_identity  # type: ignore[attr-defined]
reranker_scorer.last_observation = _last_observation  # type: ignore[attr-defined]


def main():
    """Quick smoke test on known gold/non-gold pairs."""
    import sys

    model_dir, manifest_path = _config()
    if not model_dir:
        print("DOCATLAS_RERANKER_MODEL_DIR not set")
        sys.exit(1)

    print(f"Model dir: {model_dir}")
    print(f"Identity: {reranker_identity()}")

    gold = (
        "## Only names for `False`\n\n"
        "If you want to (although it might not be a good idea), you can declare "
        "only *CLI option* names to set the `False` value.\n\n"
        "To do that, use a space and a single `/` and pass the negative name after that."
    )
    nongold = (
        "# Boolean CLI Options\n\n"
        "We have seen some examples of *CLI options* with `bool`..."
    )

    questions = [
        ("mixed_ru", "Как записать только отрицательное имя boolean option: важен ли пробел перед /?"),
        ("pure_ru", "Как записать только отрицательное имя логического параметра: важен ли пробел перед косой чертой?"),
        ("en", "How to declare only the negative name for a boolean option: is the space before / significant?"),
    ]

    t0 = time.time()
    for label, q in questions:
        s_gold = reranker_scorer(q, gold)
        s_nongold = reranker_scorer(q, nongold)
        print(f"  {label}: gold={s_gold:.4f} nongold={s_nongold:.4f} gap={s_gold - s_nongold:.4f}")
    print(f"  elapsed: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
