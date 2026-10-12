"""Optional local ranking of already admitted native windows.

The ranker changes membership only. It cannot qualify a source, grant query
credit or establish sufficiency. Model assets are prepared by the host before
serving queries; this module never downloads them.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any


MINI_MODEL_ID = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
MINI_REVISION = "1427fd652930e4ba29e8149678df786c240d8825"
MINI_WEIGHTS_SHA256 = "5daeca2481a76b5976a2bdc32f0a78532b6716da4f8cd3ff59460ef8d2f359b4"
MINI_ASSET_SHA256 = {
    "model.safetensors": MINI_WEIGHTS_SHA256,
    "config.json": "cc2cfe51aa3fd759d21d21acf5dfd6994aa67a3c9210636d22e143699d336c77",
    "tokenizer.json": "62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626",
    "tokenizer_config.json": "e7fbfbfa6347b4e414c1cee50d142e2c2f9a895dad68b068ae83a8b564c3837e",
    "special_tokens_map.json": "378eb3bf733eb16e65792d7e3fda5b8a4631387ca04d2015199c4d4f22ae554d",
    "sentencepiece.bpe.model": "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865",
}
MINI_MAX_LENGTH = 512


@dataclass(frozen=True)
class SelectorConfig:
    mode: str
    top_k: int = 2
    model_path: str | None = None


class SelectorExecutionError(RuntimeError):
    """The configured model failed; the receipt counts attempted work."""

    def __init__(self, message: str, receipt: dict[str, Any]):
        super().__init__(message)
        self.receipt = receipt


def configured_selector(settings: tuple[str | None, str | None, str | None] | None) -> SelectorConfig | None:
    if settings is None or settings[0] is None:
        return None
    mode, raw_k, model_path = settings
    mode = mode.strip()
    if mode not in {"budget", "mini"}:
        raise ValueError("DOCATLAS_EXPERIMENT_SELECTOR must be budget or mini")
    value = "2" if raw_k is None else raw_k.strip()
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 20:
        raise ValueError("DOCATLAS_EXPERIMENT_SELECTOR_TOP_K must be an integer from 1 to 20")
    if mode == "mini" and (not model_path or not Path(model_path).is_absolute()):
        raise ValueError("DOCATLAS_EXPERIMENT_MINI_PATH must name an absolute local model directory")
    return SelectorConfig(mode, int(value), model_path if mode == "mini" else None)


@dataclass
class _MiniRuntime:
    path: str
    tokenizer: Any
    model: Any
    torch: Any
    provenance: dict[str, Any]


_RUNTIME_LOCK = RLock()
_RUNTIME: _MiniRuntime | None = None


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_mini(path: str, receipt: dict[str, Any]) -> _MiniRuntime:
    """Called under the shared load/inference lock, once per resident path."""
    global _RUNTIME
    directory = Path(path).resolve(strict=True)
    if _RUNTIME is not None and _RUNTIME.path == str(directory):
        receipt["model"] = deepcopy(_RUNTIME.provenance)
        return _RUNTIME
    load_started = perf_counter()
    receipt["model_load_attempts"] = 1
    try:
        if not directory.is_dir():
            raise ValueError("Mini asset path is not a directory")
        verify_started = perf_counter()
        asset_hashes = {}
        for name, expected in MINI_ASSET_SHA256.items():
            asset_hashes[name] = _file_sha256(directory / name)
            if asset_hashes[name] != expected:
                raise ValueError("Mini asset does not match the pinned V2 revision: " + name)
        receipt["asset_verification_seconds"] = perf_counter() - verify_started
        import_started = perf_counter()
        try:
            import torch
            import transformers
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("Mini requires the optional reranker-mini dependencies in the host environment") from exc
        receipt["model_import_seconds"] = perf_counter() - import_started
        # This provider's CPU profile is fixed; process interop scheduling is
        # host-owned and is reported without resetting a shared thread pool.
        torch.set_num_threads(8)
        tokenizer = AutoTokenizer.from_pretrained(
            directory, local_files_only=True, trust_remote_code=False, use_fast=True,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            directory, local_files_only=True, trust_remote_code=False,
            use_safetensors=True, dtype=torch.float32, attn_implementation="sdpa",
        ).to(device="cpu", dtype=torch.float32).eval()
        provenance = {
            "model_id": MINI_MODEL_ID, "revision": MINI_REVISION,
            "assets_sha256": asset_hashes, "device": "cpu", "dtype": "FP32",
            "torch": torch.__version__, "transformers": transformers.__version__,
            "threads": torch.get_num_threads(), "interop_threads": torch.get_num_interop_threads(),
            "max_length": MINI_MAX_LENGTH, "truncation": False,
            "score": "raw_logits[0,0]", "tie_break": "original_pool_index",
        }
        _RUNTIME = _MiniRuntime(str(directory), tokenizer, model, torch, provenance)
        receipt["model"] = deepcopy(provenance)
        receipt["model_loads"] = 1
        return _RUNTIME
    finally:
        receipt["model_load_seconds"] = perf_counter() - load_started


def preload_mini_runtime(model_path: str) -> dict[str, Any]:
    """Explicit host preparation, with its cost separate from query execution.

    This loads only the pinned local ranker. It performs no retrieval or model
    forward and does not create a source, permission or admission cache.
    """
    config = configured_selector(("mini", "2", model_path))
    started = perf_counter()
    receipt: dict[str, Any] = {
        "schema_version": 1, "operation": "preload_mini_runtime", "status": "preparing",
        "model_load_attempts": 0, "model_loads": 0, "model_load_seconds": 0.0,
        "model_import_seconds": 0.0, "asset_verification_seconds": 0.0,
        "model_forward_attempts": 0, "model_forwards": 0,
    }
    try:
        with _RUNTIME_LOCK:
            receipt["lock_wait_seconds"] = perf_counter() - started
            _load_mini(config.model_path, receipt)
        receipt["status"] = "prepared"
        return receipt
    except Exception as exc:
        receipt.update(status="error", error_type=type(exc).__name__, error=str(exc))
        raise SelectorExecutionError("Mini preparation failed: " + str(exc), receipt) from exc
    finally:
        receipt["total_seconds"] = perf_counter() - started


def choose_configured_candidates(question: str, pool: tuple[Any, ...], config: SelectorConfig) -> tuple[tuple[int, ...], dict[str, Any]]:
    """Rank complete native windows, or record a whole-pool overflow fallback."""
    started = perf_counter()
    budget_order = tuple(range(min(config.top_k, len(pool))))
    receipt: dict[str, Any] = {
        "schema_version": 1, "mode": config.mode, "top_k": config.top_k,
        "candidate_count": len(pool), "status": "budget",
        "model_forward_attempts": 0, "model_forwards": 0, "model_input_tokens": 0,
        "tokenized_input_tokens": 0,
        "model_load_attempts": 0, "model_loads": 0, "model_load_seconds": 0.0,
        "model_import_seconds": 0.0, "asset_verification_seconds": 0.0,
        "tokenization_seconds": 0.0, "inference_seconds": 0.0,
        "lock_wait_seconds": 0.0, "rows": [],
    }
    if config.mode == "budget" or len(pool) <= config.top_k:
        if config.mode == "mini":
            receipt["status"] = "not_needed"
        receipt.update(selected_indices=list(budget_order), total_seconds=perf_counter() - started)
        return budget_order, receipt
    try:
        lock_started = perf_counter()
        with _RUNTIME_LOCK:
            receipt["lock_wait_seconds"] = perf_counter() - lock_started
            runtime = _load_mini(config.model_path, receipt)
            tokenization_started = perf_counter()
            encoded = []
            for index, chunk in enumerate(pool):
                inputs = runtime.tokenizer(question, chunk.text, truncation=False, return_tensors="pt")
                count = int(inputs["input_ids"].shape[1])
                encoded.append(inputs)
                receipt["rows"].append({"index": index, "tokens": count, "score": None})
                receipt["tokenized_input_tokens"] += count
            receipt["tokenization_seconds"] = perf_counter() - tokenization_started
            overflow = [row["index"] for row in receipt["rows"] if row["tokens"] > MINI_MAX_LENGTH]
            if overflow:
                receipt.update(status="budgetfallback_overflow", overflow_indices=overflow,
                               fallback_reason="complete_question_window_exceeds_512_tokens",
                               selected_indices=list(budget_order))
                return budget_order, receipt
            for row, inputs in zip(receipt["rows"], encoded):
                forward_started = perf_counter()
                receipt["model_forward_attempts"] += 1
                receipt["model_input_tokens"] += row["tokens"]
                try:
                    with runtime.torch.inference_mode():
                        logits = runtime.model(**inputs).logits
                    receipt["model_forwards"] += 1
                    score = float(logits[0, 0].float().item())
                finally:
                    seconds = perf_counter() - forward_started
                    receipt["inference_seconds"] += seconds
                    row["seconds"] = seconds
                if not math.isfinite(score):
                    raise ValueError("Mini produced a nonfinite score")
                row["score"] = score
            order = sorted(range(len(pool)), key=lambda index: (-receipt["rows"][index]["score"], index))
            indices = tuple(order[:config.top_k])
            receipt.update(status="ranked", ranked_indices=order, selected_indices=list(indices))
            return indices, receipt
    except Exception as exc:
        receipt.update(status="error", error_type=type(exc).__name__, error=str(exc))
        raise SelectorExecutionError("Configured Mini selection failed: " + str(exc), receipt) from exc
    finally:
        receipt["total_seconds"] = perf_counter() - started
