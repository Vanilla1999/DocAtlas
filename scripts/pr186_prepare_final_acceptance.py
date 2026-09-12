#!/usr/bin/env python3
"""One-shot preparation for PR #186 systemic acceptance.

Repairs the temporary patch carrier, applies it, then changes frozen-pool replay
so counterfactual lanes reuse the same semantic candidates while retaining each
fresh index's own chunk objects and source identities.
"""
from __future__ import annotations

from pathlib import Path


candidate = Path("scripts/pr186_patch_candidate_pool.py")
text = candidate.read_text(encoding="utf-8")
opening = "freeze_block = r'''\n"
closing = "\nPY\ngit diff --check\n'''\nscript = script.replace"
if text.count(opening) != 1 or text.count(closing) != 1:
    raise SystemExit("one-shot candidate-pool quoting anchors changed")
text = text.replace(opening, 'freeze_block = r"""\n', 1)
text = text.replace(
    closing,
    '\nPY\ngit diff --check\n"""\nscript = script.replace',
    1,
)
candidate.write_text(text, encoding="utf-8")
compile(text, str(candidate), "exec")
exec(
    compile(text, str(candidate), "exec"),
    {"__name__": "__main__", "__file__": str(candidate)},
)

finalizer = Path("scripts/pr186_finalize.sh")
script = finalizer.read_text(encoding="utf-8")

state_old = "    fixed_pools: dict[tuple[str, int], list[Any]] = globals().setdefault(\n"
state_new = "    fixed_pools: dict[tuple[str, int], list[tuple[str, int, str]]] = globals().setdefault(\n"
if script.count(state_old) != 1:
    raise SystemExit("fixed-pool state anchor changed")
script = script.replace(state_old, state_new, 1)

call_anchor = '''    def call_identity(key: tuple[str, int], fingerprint: str) -> str:\n        query_hash = hashlib.sha256(key[0].encode("utf-8")).hexdigest()[:16]\n        return f"{query_hash}:{key[1]}:{fingerprint}"\n'''
semantic_helper = '''    def semantic_candidate_key(chunk: Any) -> tuple[str, int, str]:\n        if isinstance(chunk, dict):\n            metadata = chunk.get("metadata") or {}\n            source_path = str(\n                chunk.get("project_doc_path")\n                or chunk.get("source_path")\n                or chunk.get("path")\n                or chunk.get("source")\n                or metadata.get("project_doc_path")\n                or metadata.get("source_path")\n                or metadata.get("canonical_url")\n                or ""\n            )\n            chunk_index = int(chunk.get("chunk_index", -1))\n            body = str(chunk.get("text") or chunk.get("snippet") or "")\n        else:\n            metadata = getattr(chunk, "metadata", {}) or {}\n            source_path = str(\n                metadata.get("project_doc_path")\n                or metadata.get("source_path")\n                or metadata.get("canonical_url")\n                or getattr(chunk, "source", "")\n                or ""\n            )\n            chunk_index = int(getattr(chunk, "chunk_index", -1))\n            body = str(getattr(chunk, "text", "") or "")\n        return (\n            _semantic_source_identity(source_path),\n            chunk_index,\n            hashlib.sha256(body.encode("utf-8")).hexdigest(),\n        )\n\n'''
if script.count(call_anchor) != 1:
    raise SystemExit("fixed-pool call identity anchor changed")
script = script.replace(call_anchor, semantic_helper + call_anchor, 1)

replay_old = '''        controlled_chunks = chunks\n        if causal_lane:\n            if capture_fixed_pool:\n                fixed_pools[key] = deepcopy(chunks)\n            frozen = fixed_pools.get(key)\n            if frozen is None:\n                raise RuntimeError(f"counterfactual retrieval call absent from frozen current pool: {key!r}")\n            controlled_chunks = deepcopy(frozen)\n        controlled_fingerprint = _candidate_pool_fingerprint(controlled_chunks)\n'''
replay_new = '''        controlled_chunks = chunks\n        if causal_lane:\n            if capture_fixed_pool:\n                fixed_pools[key] = [semantic_candidate_key(chunk) for chunk in chunks]\n            frozen = fixed_pools.get(key)\n            if frozen is None:\n                raise RuntimeError(f"counterfactual retrieval call absent from frozen current pool: {key!r}")\n            buckets: dict[tuple[str, int, str], list[Any]] = defaultdict(list)\n            for chunk in chunks:\n                buckets[semantic_candidate_key(chunk)].append(chunk)\n            remapped: list[Any] = []\n            missing_candidates: list[tuple[str, int, str]] = []\n            for candidate_key in frozen:\n                bucket = buckets.get(candidate_key)\n                if not bucket:\n                    missing_candidates.append(candidate_key)\n                    continue\n                remapped.append(bucket.pop(0))\n            if missing_candidates:\n                raise RuntimeError(\n                    f"fresh lane cannot replay frozen semantic pool for {key!r}: "\n                    f"missing={missing_candidates!r}"\n                )\n            controlled_chunks = remapped\n        controlled_fingerprint = _candidate_pool_fingerprint(controlled_chunks)\n'''
if script.count(replay_old) != 1:
    raise SystemExit("fixed-pool replay anchor changed")
script = script.replace(replay_old, replay_new, 1)
finalizer.write_text(script, encoding="utf-8")

# Successful publication must contain neither temporary patch helper.
Path(__file__).unlink()
