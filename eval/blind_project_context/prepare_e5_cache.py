"""Explicit offline preparation for the opt-in live E5 acquisition experiment.

Usage: python prepare_e5_cache.py --db MEMBERS_DB [--db ...] --model-dir MODEL --out CACHE
No oracle/questions are loaded. Existing output is never overwritten.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import time

from docmancer.retrieval.experimental_e5_acquisition import Encoder, MODEL_REVISION, digest, text_key


def main():
    import numpy as np
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, action="append", required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    texts = {}
    for db in args.db:
        with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as conn:
            for (text,) in conn.execute("""SELECT retrieval_text FROM retrieval_children
                WHERE generation_id=(SELECT active_generation_id FROM index_state WHERE singleton=1)"""):
                texts[text_key(text)] = text
    keys = sorted(texts)
    engine = Encoder(args.model_dir, args.threads)
    # Length ordering reduces padding; the mapping back to hash keys is exact.
    order = sorted(range(len(keys)), key=lambda i: len(texts[keys[i]]))
    vectors = np.zeros((len(keys), 384), dtype=np.float32)
    start = time.monotonic()
    for offset in range(0, len(order), 16):
        indices = order[offset:offset + 16]
        vectors[indices] = engine.encode(["passage: " + texts[keys[i]] for i in indices])
        if offset % 512 == 0:
            print(f"{offset}/{len(keys)} passages, {time.monotonic()-start:.1f}s", flush=True)
    np.save(args.out / "vectors.npy", vectors, allow_pickle=False)
    manifest = {"revision": MODEL_REVISION, "recipe": "retrieval_text:passage:mean:l2:512",
                "keys": keys, "vectors_sha256": digest(args.out / "vectors.npy"),
                "databases": {str(db): digest(db) for db in args.db},
                "seconds": time.monotonic() - start, "threads": args.threads}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Complete: {len(keys)} passages, {manifest['seconds']:.1f}s", flush=True)


if __name__ == "__main__":
    main()
