#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


runner = Path("scripts/run_systemic_retrieval_plan_gate.py")
text = runner.read_text(encoding="utf-8")
anchor = "\ndef _candidate_pool_fingerprint(pool: list[Any]) -> str:\n"
if anchor not in text:
    raise SystemExit("candidate fingerprint anchor missing")

if "def _semantic_source_identity(" not in text:
    helper = r'''

def _semantic_source_identity(value: Any) -> str:
    """Remove only the eval lane root from isolated corpus source paths."""
    normalized = str(value or "").replace("\\", "/")
    parts = [part for part in normalized.split("/") if part and part != "."]
    corpus_positions = [index for index, part in enumerate(parts) if part == "corpus"]
    if corpus_positions:
        suffix = parts[corpus_positions[-1] + 1 :]
        if len(suffix) >= 2:
            return "/".join(suffix)
    return normalized
'''
    text = text.replace(anchor, helper + anchor, 1)

old = '''        canonical.append(
            {
                "path": path,
                "chunk_index": chunk_index,
                "text_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            }
        )
'''
new = '''        canonical.append(
            {
                "path": _semantic_source_identity(path),
                "chunk_index": chunk_index,
                "text_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            }
        )
'''
if old not in text:
    raise SystemExit("candidate fingerprint canonicalization anchor missing")
text = text.replace(old, new, 1)
runner.write_text(text, encoding="utf-8")

# The first lane is the factual current run. Counterfactual lanes must receive
# the exact same pre-cap candidates, rather than relying on independently
# rebuilt fresh indexes to happen to produce an identical pool. Raw fresh-run
# drift remains measured separately for diagnostics.
finalizer = Path("scripts/pr186_finalize.sh")
script = finalizer.read_text(encoding="utf-8")
insertion_anchor = "\n\npython -m pytest -q \\\n"
if insertion_anchor not in script:
    raise SystemExit("finalizer targeted-test insertion anchor missing")
freeze_block = r'''

python - <<'PY'
from pathlib import Path

path = Path('scripts/run_systemic_retrieval_plan_gate.py')
text = path.read_text(encoding='utf-8')
old = '''    cap_inputs: list[str] = []
    original_cap = RetrievalDispatcher._limit_sections_per_source

    def observed_cap(self: Any, chunks: list[Any], *, limit: int | None = None, expand: str | None = None) -> list[Any]:
        cap_inputs.append(_candidate_pool_fingerprint(chunks))
        if cap == "off":
            return _no_source_cap(self, chunks, limit=limit, expand=expand)
        if cap == "strict":
            return _strict_source_cap(self, chunks, limit=limit, expand=expand)
        if cap == "bounded":
            return original_cap(self, chunks, limit=limit, expand=expand)
        raise ValueError(f"unknown cap mode: {cap}")

    started_cpu = time.process_time()
    started_wall = time.perf_counter()
    with ExitStack() as stack:
        stack.enter_context(patch.object(evidence, "load_protocol", return_value=(lane_protocol, deepcopy(cases), deepcopy(manifest))))
        stack.enter_context(patch.object(RetrievalDispatcher, "_limit_sections_per_source", observed_cap))
'''
new = '''    cap_inputs: list[str] = []
    raw_cap_inputs: list[str] = []
    causal_lane = name in {
        "cap_on_requal_on", "cap_off_requal_on",
        "cap_on_requal_off", "cap_off_requal_off", "contextualization_off",
    }
    capture_fixed_pool = name == "cap_on_requal_on"
    fixed_pools: dict[tuple[str, int], list[Any]] = globals().setdefault(
        "_SYSTEMIC_FIXED_PRE_CAP_POOLS", {}
    )
    if capture_fixed_pool:
        fixed_pools.clear()
    call_occurrences: Counter[str] = Counter()
    active_call_keys: list[tuple[str, int]] = []
    seen_call_keys: list[tuple[str, int]] = []
    original_run = RetrievalDispatcher.run
    original_cap = RetrievalDispatcher._limit_sections_per_source

    def call_identity(key: tuple[str, int], fingerprint: str) -> str:
        query_hash = hashlib.sha256(key[0].encode("utf-8")).hexdigest()[:16]
        return f"{query_hash}:{key[1]}:{fingerprint}"

    def observed_run(self: Any, query: str, *args: Any, **kwargs: Any) -> Any:
        occurrence = call_occurrences[query]
        call_occurrences[query] += 1
        key = (query, occurrence)
        active_call_keys.append(key)
        seen_call_keys.append(key)
        try:
            return original_run(self, query, *args, **kwargs)
        finally:
            popped = active_call_keys.pop()
            if popped != key:
                raise RuntimeError("retrieval call stack lost deterministic ordering")

    def observed_cap(self: Any, chunks: list[Any], *, limit: int | None = None, expand: str | None = None) -> list[Any]:
        if not active_call_keys:
            raise RuntimeError("pre-cap pool observed outside RetrievalDispatcher.run")
        key = active_call_keys[-1]
        raw_fingerprint = _candidate_pool_fingerprint(chunks)
        raw_cap_inputs.append(call_identity(key, raw_fingerprint))
        controlled_chunks = chunks
        if causal_lane:
            if capture_fixed_pool:
                fixed_pools[key] = deepcopy(chunks)
            frozen = fixed_pools.get(key)
            if frozen is None:
                raise RuntimeError(f"counterfactual retrieval call absent from frozen current pool: {key!r}")
            controlled_chunks = deepcopy(frozen)
        controlled_fingerprint = _candidate_pool_fingerprint(controlled_chunks)
        cap_inputs.append(call_identity(key, controlled_fingerprint))
        if cap == "off":
            return _no_source_cap(self, controlled_chunks, limit=limit, expand=expand)
        if cap == "strict":
            return _strict_source_cap(self, controlled_chunks, limit=limit, expand=expand)
        if cap == "bounded":
            return original_cap(self, controlled_chunks, limit=limit, expand=expand)
        raise ValueError(f"unknown cap mode: {cap}")

    started_cpu = time.process_time()
    started_wall = time.perf_counter()
    with ExitStack() as stack:
        stack.enter_context(patch.object(evidence, "load_protocol", return_value=(lane_protocol, deepcopy(cases), deepcopy(manifest))))
        stack.enter_context(patch.object(RetrievalDispatcher, "run", observed_run))
        stack.enter_context(patch.object(RetrievalDispatcher, "_limit_sections_per_source", observed_cap))
'''
if text.count(old) != 1:
    raise SystemExit('instrumented run-lane block changed before fixed-pool replay')
text = text.replace(old, new, 1)

old = '''    return {"name": name, "output": output, "summary": summary, "metrics": metrics, "rows": rows, "cap_inputs": cap_inputs}
'''
new = '''    if causal_lane and set(seen_call_keys) != set(fixed_pools):
        missing = sorted(set(fixed_pools) - set(seen_call_keys))
        extra = sorted(set(seen_call_keys) - set(fixed_pools))
        raise RuntimeError(f"fixed-pool retrieval topology changed: missing={missing!r} extra={extra!r}")
    return {
        "name": name, "output": output, "summary": summary, "metrics": metrics,
        "rows": rows, "cap_inputs": cap_inputs, "raw_cap_inputs": raw_cap_inputs,
        "fixed_pool_calls": len(fixed_pools) if causal_lane else 0,
    }
'''
if text.count(old) != 1:
    raise SystemExit('instrumented lane return changed before fixed-pool replay')
text = text.replace(old, new, 1)

old = '''            "ordered_same_as_current": lane["cap_inputs"] == current["cap_inputs"],
'''
new = '''            "ordered_same_as_current": lane["cap_inputs"] == current["cap_inputs"],
            "raw_same_as_current": Counter(lane["raw_cap_inputs"]) == Counter(current["raw_cap_inputs"]),
            "raw_ordered_same_as_current": lane["raw_cap_inputs"] == current["raw_cap_inputs"],
            "frozen_calls": lane["fixed_pool_calls"],
'''
if text.count(old) != 1:
    raise SystemExit('fixed-pool report anchor changed')
text = text.replace(old, new, 1)

old = '"interpretation": "Counterfactual diagnostic only; no causal claim extends beyond this fixed exposed corpus."'
new = '"interpretation": "Counterfactual lanes replay the frozen current pre-cap pools; raw fresh-index drift is reported separately. No causal claim extends beyond this fixed exposed corpus."'
if text.count(old) != 1:
    raise SystemExit('causal interpretation anchor changed')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
PY
git diff --check
'''
script = script.replace(insertion_anchor, freeze_block + insertion_anchor, 1)
finalizer.write_text(script, encoding="utf-8")

# This is a one-shot branch finalization helper; a successful acceptance commit
# must not retain the carrier script itself.
Path(__file__).unlink()
