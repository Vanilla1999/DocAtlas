"""Content-addressed manifest for the bge-reranker-v2-m3 ONNX model."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
from pathlib import Path

RERANKER_NAME = "BAAI/bge-reranker-v2-m3"
RERANKER_ONNX_SOURCE = "EmbeddedLLM/bge-reranker-v2-m3-onnx-o3-cpu"
REQUIRED = {
    "config.json", "model.onnx", "model.onnx.data", "tokenizer.json",
    "tokenizer_config.json", "special_tokens_map.json", "sentencepiece.bpe.model",
}
DEPENDENCIES = ("onnxruntime", "tokenizers", "numpy")


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inventory(root: Path) -> dict[str, str]:
    root = root.resolve(strict=True)
    paths = {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}
    if not REQUIRED <= paths.keys():
        raise ValueError(f"missing model files: {sorted(REQUIRED - paths.keys())}")
    if any(not p.resolve().is_relative_to(root) for p in paths.values()):
        raise ValueError("export model symlinks as files before creating inventory")
    return {name: file_digest(path) for name, path in sorted(paths.items())}


def build_reranker_manifest(root: Path) -> dict:
    body = {
        "schema_version": 1,
        "model_name": RERANKER_NAME,
        "onnx_source": RERANKER_ONNX_SOURCE,
        "files": _inventory(root),
        "versions": {name: importlib.metadata.version(name) for name in DEPENDENCIES},
        "inference": {
            "provider": "CPUExecutionProvider",
            "threads": 1,
            "scoring": "cross-encoder-logit-float32",
            "expected_dimensions": None,
        },
        "calibration_transfer_validated": False,
    }
    fingerprint = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                   allow_nan=False).encode()
    ).hexdigest()
    return {**body, "fingerprint": fingerprint}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.model_dir.resolve()):
        parser.error("manifest must be outside the model directory")
    manifest = build_reranker_manifest(args.model_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(manifest["fingerprint"])


if __name__ == "__main__":
    main()
