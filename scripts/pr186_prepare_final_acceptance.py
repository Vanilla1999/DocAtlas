#!/usr/bin/env python3
"""One-shot preparation for PR #186 systemic acceptance.

Repairs the temporary patch carrier, applies it, then makes fixed-pool replay
case/project scoped. Counterfactual lanes therefore receive the same semantic
pre-cap candidates while retaining each fresh index's own chunk identities.
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
state_new = "    fixed_pools: dict[tuple[Any, ...], list[tuple[str, int, str]]] = globals().setdefault(\n"
if script.count(state_old) != 1:
    raise SystemExit("fixed-pool state anchor changed")
script = script.replace(state_old, state_new, 1)

run_block_old = '''    call_occurrences: Counter[str] = Counter()\n    active_call_keys: list[tuple[str, int]] = []\n    seen_call_keys: list[tuple[str, int]] = []\n    original_run = RetrievalDispatcher.run\n    original_cap = RetrievalDispatcher._limit_sections_per_source\n\n    def call_identity(key: tuple[str, int], fingerprint: str) -> str:\n        query_hash = hashlib.sha256(key[0].encode("utf-8")).hexdigest()[:16]\n        return f"{query_hash}:{key[1]}:{fingerprint}"\n\n    def observed_run(self: Any, query: str, *args: Any, **kwargs: Any) -> Any:\n        occurrence = call_occurrences[query]\n        call_occurrences[query] += 1\n        key = (query, occurrence)\n        active_call_keys.append(key)\n        seen_call_keys.append(key)\n        try:\n            return original_run(self, query, *args, **kwargs)\n        finally:\n            popped = active_call_keys.pop()\n            if popped != key:\n                raise RuntimeError("retrieval call stack lost deterministic ordering")\n'''
run_block_new = '''    call_occurrences: Counter[tuple[Any, ...]] = Counter()\n    active_call_keys: list[tuple[Any, ...]] = []\n    seen_call_keys: list[tuple[Any, ...]] = []\n    original_run = RetrievalDispatcher.run\n    original_cap = RetrievalDispatcher._limit_sections_per_source\n\n    def semantic_candidate_key(chunk: Any) -> tuple[str, int, str]:\n        if isinstance(chunk, dict):\n            metadata = chunk.get("metadata") or {}\n            source_path = str(\n                chunk.get("project_doc_path")\n                or chunk.get("source_path")\n                or chunk.get("path")\n                or chunk.get("source")\n                or metadata.get("project_doc_path")\n                or metadata.get("source_path")\n                or metadata.get("canonical_url")\n                or ""\n            )\n            chunk_index = int(chunk.get("chunk_index", -1))\n            body = str(chunk.get("text") or chunk.get("snippet") or "")\n        else:\n            metadata = getattr(chunk, "metadata", {}) or {}\n            source_path = str(\n                metadata.get("project_doc_path")\n                or metadata.get("source_path")\n                or metadata.get("canonical_url")\n                or getattr(chunk, "source", "")\n                or ""\n            )\n            chunk_index = int(getattr(chunk, "chunk_index", -1))\n            body = str(getattr(chunk, "text", "") or "")\n        return (\n            _semantic_source_identity(source_path),\n            chunk_index,\n            hashlib.sha256(body.encode("utf-8")).hexdigest(),\n        )\n\n    def retrieval_scope(query: str, kwargs: dict[str, Any]) -> tuple[Any, ...]:\n        filters = kwargs.get("filters") or {}\n        if not isinstance(filters, dict):\n            filters = {}\n        project = str(\n            filters.get("project_identity")\n            or _semantic_source_identity(filters.get("project_path") or "")\n            or "unknown-project"\n        )\n        return (\n            project,\n            query,\n            str(filters.get("authority") or ""),\n            str(filters.get("source_class") or ""),\n            str(filters.get("doc_scope") or ""),\n            str(kwargs.get("mode") or ""),\n            str(kwargs.get("expand") or ""),\n            int(kwargs.get("limit") or -1),\n            int(kwargs.get("budget") or -1),\n        )\n\n    def call_identity(key: tuple[Any, ...], fingerprint: str) -> str:\n        encoded = json.dumps(key, ensure_ascii=False, separators=(",", ":")).encode("utf-8")\n        return f"{hashlib.sha256(encoded).hexdigest()[:24]}:{fingerprint}"\n\n    def observed_run(self: Any, query: str, *args: Any, **kwargs: Any) -> Any:\n        scope = retrieval_scope(query, kwargs)\n        occurrence = call_occurrences[scope]\n        call_occurrences[scope] += 1\n        key = (*scope, occurrence)\n        active_call_keys.append(key)\n        seen_call_keys.append(key)\n        try:\n            return original_run(self, query, *args, **kwargs)\n        finally:\n            popped = active_call_keys.pop()\n            if popped != key:\n                raise RuntimeError("retrieval call stack lost deterministic ordering")\n'''
if script.count(run_block_old) != 1:
    raise SystemExit("fixed-pool run identity block changed")
script = script.replace(run_block_old, run_block_new, 1)

replay_old = '''        controlled_chunks = chunks\n        if causal_lane:\n            if capture_fixed_pool:\n                fixed_pools[key] = deepcopy(chunks)\n            frozen = fixed_pools.get(key)\n            if frozen is None:\n                raise RuntimeError(f"counterfactual retrieval call absent from frozen current pool: {key!r}")\n            controlled_chunks = deepcopy(frozen)\n        controlled_fingerprint = _candidate_pool_fingerprint(controlled_chunks)\n'''
replay_new = '''        controlled_chunks = chunks\n        if causal_lane:\n            if capture_fixed_pool:\n                fixed_pools[key] = [semantic_candidate_key(chunk) for chunk in chunks]\n            frozen = fixed_pools.get(key)\n            if frozen is None:\n                raise RuntimeError(f"counterfactual retrieval call absent from frozen current pool: {key!r}")\n            buckets: dict[tuple[str, int, str], list[Any]] = defaultdict(list)\n            for chunk in chunks:\n                buckets[semantic_candidate_key(chunk)].append(chunk)\n            remapped: list[Any] = []\n            missing_candidates: list[tuple[str, int, str]] = []\n            for candidate_key in frozen:\n                bucket = buckets.get(candidate_key)\n                if not bucket:\n                    missing_candidates.append(candidate_key)\n                    continue\n                remapped.append(bucket.pop(0))\n            if missing_candidates:\n                raise RuntimeError(\n                    f"fresh lane cannot replay frozen semantic pool for {key!r}: "\n                    f"missing={missing_candidates!r}"\n                )\n            controlled_chunks = remapped\n        controlled_fingerprint = _candidate_pool_fingerprint(controlled_chunks)\n'''
if script.count(replay_old) != 1:
    raise SystemExit("fixed-pool replay anchor changed")
script = script.replace(replay_old, replay_new, 1)
finalizer.write_text(script, encoding="utf-8")

# Successful publication must contain neither temporary patch helper.
Path(__file__).unlink()
