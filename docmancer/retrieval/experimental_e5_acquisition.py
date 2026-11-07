"""Opt-in offline lexical/E5 acquisition, before ordinary source admission.

Vectors are provisioned separately. Reads never build indexes, download models
or write caches. Exact cosine is evaluated over the live metadata-filtered
generation, not over lexical hits. Alternating ranks share the existing total
candidate/token/byte ceiling. Scores and cached vectors grant no source authority.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
from threading import RLock

MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
ASSETS = {
    "model.onnx": "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665",
    "tokenizer.json": "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
}
MAX_CORPUS_ROWS = 50_000
_LOCK = RLock()


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Encoder:
    """Pinned multilingual-e5-small, published prefix/mean-pooling recipe."""

    def __init__(self, directory: Path, threads: int = 4):
        for name, expected in ASSETS.items():
            if digest(directory / name) != expected:
                raise ValueError(f"E5 asset differs from pinned revision: {name}")
        import onnxruntime as ort
        from tokenizers import Tokenizer
        ort.disable_telemetry_events()
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.no_padding()
        self.tokenizer.enable_truncation(max_length=512, direction="right")
        self.pad_id = self.tokenizer.token_to_id("<pad>")
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(directory / "model.onnx"), options,
                                           providers=["CPUExecutionProvider"])
        self.inputs = {item.name for item in self.session.get_inputs()}

    def encode(self, texts: list[str]):
        import numpy as np
        encoded = self.tokenizer.encode_batch(texts)
        width = max(len(item.ids) for item in encoded)
        ids = np.full((len(encoded), width), self.pad_id, dtype=np.int64)
        mask = np.zeros_like(ids)
        types = np.zeros_like(ids)
        for index, item in enumerate(encoded):
            size = len(item.ids)
            ids[index, :size] = item.ids
            mask[index, :size] = item.attention_mask
            types[index, :size] = item.type_ids
        feeds = {key: value for key, value in {
            "input_ids": ids, "attention_mask": mask, "token_type_ids": types,
        }.items() if key in self.inputs}
        hidden = self.session.run(["last_hidden_state"], feeds)[0]
        if hidden.shape != (len(encoded), width, 384):
            raise ValueError("unexpected E5 token-state shape")
        masked = mask[..., None].astype(np.float32)
        pooled = (hidden * masked).sum(axis=1) / masked.sum(axis=1)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        if not np.isfinite(pooled).all() or (norms <= 0).any():
            raise ValueError("invalid E5 vectors")
        return (pooled / norms).astype(np.float32)


@lru_cache(maxsize=2)
def _runtime(model_path: str, cache_path: str):
    import numpy as np
    model, cache = Path(model_path), Path(cache_path)
    if not model.is_absolute() or not cache.is_absolute():
        raise ValueError("E5 model/cache directories must be absolute")
    manifest = json.loads((cache / "manifest.json").read_text())
    if manifest.get("revision") != MODEL_REVISION or manifest.get("recipe") != "retrieval_text:passage:mean:l2:512":
        raise ValueError("E5 cache recipe mismatch")
    if digest(cache / "vectors.npy") != manifest["vectors_sha256"]:
        raise ValueError("E5 cache digest mismatch")
    keys = manifest["keys"]
    if len(keys) > MAX_CORPUS_ROWS or len(set(keys)) != len(keys):
        raise ValueError("E5 cache row limit or duplicate keys")
    matrix = np.load(cache / "vectors.npy", allow_pickle=False)
    if matrix.shape != (len(keys), 384) or matrix.dtype != np.float32 or not np.isfinite(matrix).all():
        raise ValueError("E5 cache vector shape/type/value mismatch")
    if not np.allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-4):
        raise ValueError("E5 cache vectors are not normalized")
    return Encoder(model), matrix, {key: i for i, key in enumerate(keys)}


def hybrid_rows(store, query: str, lexical: list[dict], filters: dict | None, limit: int) -> list[dict]:
    """Round-robin lexical/dense ranks under ONE shared acquisition ceiling."""
    model = os.environ.get("DOCATLAS_EXPERIMENT_E5_MODEL_DIR", "")
    cache = os.environ.get("DOCATLAS_EXPERIMENT_E5_CACHE", "")
    if not model or not cache:
        raise ValueError("E5 hybrid requires explicit local model and prepared cache")
    filter_sql, params = store._metadata_filter_sql(filters, promoted=True)
    with store._connect() as conn:
        generation = store._active_generation_id(conn)
        rows = [dict(row) for row in conn.execute(f"""
            SELECT sections.hydration_id AS id, sections.*,
                   sections.display_text AS text,
                   sections.display_token_estimate AS token_estimate,
                   sections.display_content_hash AS content_hash
            FROM retrieval_children AS sections
            WHERE sections.generation_id = ? {filter_sql}
            ORDER BY sections.source_path, sections.char_start, sections.char_end, sections.stable_chunk_id
            LIMIT ?
        """, (generation, *params, MAX_CORPUS_ROWS + 1))]
    if len(rows) > MAX_CORPUS_ROWS:
        raise ValueError("E5 live corpus exceeds offline research work ceiling")
    if not rows:
        return lexical
    import numpy as np
    with _LOCK:
        engine, matrix, indices = _runtime(model, cache)
        try:
            selected = [indices[text_key(row["retrieval_text"])] for row in rows]
        except KeyError as exc:
            raise ValueError("E5 cache lacks current source text; prepare a new cache explicitly") from exc
        vector = engine.encode(["query: " + query])[0]
        scores = matrix[selected] @ vector
    order = np.argsort(-scores, kind="stable")[:limit]
    dense = [{**rows[int(i)], "rank": 0.0, "_e5_cosine": float(scores[i])} for i in order]
    # Preserve legitimate locator matches for rows shared with the lexical lane.
    lexical_by_id = {row["id"]: row for row in lexical}
    merged, seen = [], set()
    for rank in range(max(len(lexical), len(dense))):
        for lane in (lexical, dense):
            if rank >= len(lane):
                continue
            row = lane[rank]
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            merged.append({**row, **lexical_by_id.get(row["id"], {})})
            if len(merged) == limit:
                return merged
    return merged
