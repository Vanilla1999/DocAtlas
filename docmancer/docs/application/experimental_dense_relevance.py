"""Research flag: dense (bi-encoder) relevance of already admitted rows.

Context7-style "vectorize" path for the joint selector, off by default. A
local multilingual-E5 checkpoint embeds every checked row ("passage: ") and
each explicit query ("query: ") with mean pooling and L2 normalization, the
published E5 recipe (Wang et al. 2024, arXiv:2402.05672). Row vectors depend
only on row text, so an index can compute them once; the optional on-disk
cache (DOCATLAS_EXPERIMENT_DENSE_CACHE) plays that role in replays. Cosine
similarities are min-max normalized per query over the checked pool (Lee 1997)
so they share the [0, 1] scale of the lexical lane. Like the cross-encoder,
the ranker changes membership only and never grants coverage. This module
never downloads model assets (results: STEP7_CONTEXT7_PATH_RU.md).
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any

from .experimental_selection_modes import JointSemanticRelevanceError


DENSE_MAX_LENGTH = 512  # the checkpoint's own position limit
_QUERY_PREFIX, _PASSAGE_PREFIX = "query: ", "passage: "


@dataclass
class _DenseRuntime:
    path: str
    tokenizer: Any
    model: Any
    torch: Any
    weights_sha256: str


_LOCK = RLock()
_RUNTIME: _DenseRuntime | None = None
_VECTORS: dict[tuple[str, str], list[float]] = {}


def _load(path: str) -> _DenseRuntime:
    global _RUNTIME
    directory = Path(path).resolve(strict=True)
    if _RUNTIME is not None and _RUNTIME.path == str(directory):
        return _RUNTIME
    if not directory.is_dir():
        raise ValueError("dense model path is not a directory")
    import torch
    from transformers import AutoModel, AutoTokenizer
    digest = hashlib.sha256()
    with (directory / "model.safetensors").open("rb") as weights:
        for block in iter(lambda: weights.read(1 << 20), b""):
            digest.update(block)
    tokenizer = AutoTokenizer.from_pretrained(directory, local_files_only=True, trust_remote_code=False)
    model = AutoModel.from_pretrained(directory, local_files_only=True, trust_remote_code=False,
                                      use_safetensors=True).to(device="cpu", dtype=torch.float32).eval()
    _RUNTIME = _DenseRuntime(str(directory), tokenizer, model, torch, digest.hexdigest())
    return _RUNTIME


def _embed(runtime: _DenseRuntime, texts: list[str], receipt: dict[str, Any]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), 16):
        inputs = runtime.tokenizer(texts[start:start + 16], truncation=True, max_length=DENSE_MAX_LENGTH,
                                   padding=True, return_tensors="pt")
        started = perf_counter()
        with runtime.torch.inference_mode():
            hidden = runtime.model(**inputs).last_hidden_state
            mask = inputs["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1.0)
            pooled = runtime.torch.nn.functional.normalize(pooled, p=2, dim=1)
        receipt["inference_seconds"] += perf_counter() - started
        receipt["model_forwards"] += 1
        vectors.extend(pooled.tolist())
    return vectors


def _cached_rows(runtime: _DenseRuntime, rows: list[dict], receipt: dict[str, Any]) -> list[list[float]]:
    cache_dir = os.environ.get("DOCATLAS_EXPERIMENT_DENSE_CACHE")
    folder = Path(cache_dir) / runtime.weights_sha256[:16] if cache_dir else None
    keys = [hashlib.sha256(row["snippet"].encode("utf-8")).hexdigest() for row in rows]
    missing = []
    for key in dict.fromkeys(keys):
        if (runtime.weights_sha256, key) in _VECTORS:
            continue
        stored = folder / f"{key}.f32" if folder is not None else None
        if stored is not None and stored.is_file():
            import array
            values = array.array("f")
            values.frombytes(stored.read_bytes())
            _VECTORS[(runtime.weights_sha256, key)] = values.tolist()
            receipt["rows_from_cache"] += 1
        else:
            missing.append(key)
    if missing:
        texts = {key: row["snippet"] for key, row in zip(keys, rows)}
        embedded = _embed(runtime, [_PASSAGE_PREFIX + texts[key] for key in missing], receipt)
        receipt["rows_embedded"] += len(missing)
        for key, vector in zip(missing, embedded):
            _VECTORS[(runtime.weights_sha256, key)] = vector
            if folder is not None:
                import array
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"{key}.f32").write_bytes(array.array("f", vector).tobytes())
    return [_VECTORS[(runtime.weights_sha256, key)] for key in keys]


def score_joint_dense(queries: dict, rows: list[dict], model_path: str) -> tuple[dict[str, list[float]], dict]:
    """Per query: min-max normalized cosine similarity of every checked row."""
    receipt: dict[str, Any] = {"model_forwards": 0, "inference_seconds": 0.0,
                               "rows_embedded": 0, "rows_from_cache": 0}
    try:
        if not model_path or not Path(model_path).is_absolute():
            raise ValueError("DOCATLAS_EXPERIMENT_DENSE_PATH must name an absolute local model directory")
        with _LOCK:
            runtime = _load(model_path)
            receipt["model"] = {"path": runtime.path, "weights_sha256": runtime.weights_sha256,
                                "pooling": "mean", "normalized": True, "max_length": DENSE_MAX_LENGTH}
            row_vectors = _cached_rows(runtime, rows, receipt)
            keys = list(queries)
            query_vectors = _embed(runtime, [_QUERY_PREFIX + queries[key]["text"] for key in keys], receipt)
        scores: dict[str, list[float]] = {}
        for key, query in zip(keys, query_vectors):
            raw = [sum(a * b for a, b in zip(query, row)) for row in row_vectors]
            if not all(math.isfinite(value) for value in raw):
                raise ValueError("dense model produced a nonfinite score")
            low, high = min(raw, default=0.0), max(raw, default=0.0)
            scores[key] = [(value - low) / (high - low) if high > low else 1.0 for value in raw]
        return scores, receipt
    except Exception as exc:
        receipt.update(status="error", error_type=type(exc).__name__, error=str(exc))
        raise JointSemanticRelevanceError("Joint semantic relevance failed: " + str(exc), receipt) from exc
