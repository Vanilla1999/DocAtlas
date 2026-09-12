#!/usr/bin/env python3
"""Install the canonical fixed-pool causal lane into the one-shot finalizer."""
from __future__ import annotations

from pathlib import Path


finalizer = Path("scripts/pr186_finalize.sh")
script = finalizer.read_text(encoding="utf-8")
anchor = "python -m compileall -q docmancer tests scripts eval/systemic_retrieval_plan\n"
if script.count(anchor) != 1:
    raise SystemExit("final compile anchor changed")

repair = r"""python - <<'PY_CANONICAL_LANE'
from pathlib import Path

path = Path('scripts/run_systemic_retrieval_plan_gate.py')
text = path.read_text(encoding='utf-8')
start = text.find('def _run_lane(')
end = text.find('\n\ndef _paired(', start)
if start < 0 or end < 0:
    raise SystemExit('run-lane function boundaries changed')
replacement = r'''def _run_lane(*, name: str, work: Path, protocol: dict[str, Any], cases: list[dict[str, Any]], manifest: dict[str, Any], cap: str = "bounded", requalification: bool = True, contextualization: bool = True, documents_for: Any | None = None, registry_for: Any | None = None) -> dict[str, Any]:
    output = work / name
    shutil.rmtree(output, ignore_errors=True)
    lane_protocol = _single_variant_protocol(protocol)
    cap_inputs: list[str] = []
    raw_cap_inputs: list[str] = []
    causal_lane = name in {
        "cap_on_requal_on", "cap_off_requal_on",
        "cap_on_requal_off", "cap_off_requal_off", "contextualization_off",
    }
    capture_fixed_pool = name == "cap_on_requal_on"
    fixed_pools: dict[tuple[Any, ...], list[tuple[str, int, str]]] = globals().setdefault(
        "_SYSTEMIC_FIXED_PRE_CAP_POOLS", {}
    )
    if capture_fixed_pool:
        fixed_pools.clear()
    call_occurrences: Counter[tuple[Any, ...]] = Counter()
    active_call_keys: list[tuple[Any, ...]] = []
    seen_call_keys: list[tuple[Any, ...]] = []
    original_run = RetrievalDispatcher.run
    original_cap = RetrievalDispatcher._limit_sections_per_source

    def semantic_candidate_key(chunk: Any) -> tuple[str, int, str]:
        if isinstance(chunk, dict):
            metadata = chunk.get("metadata") or {}
            source_path = str(
                chunk.get("project_doc_path")
                or chunk.get("source_path")
                or chunk.get("path")
                or chunk.get("source")
                or metadata.get("project_doc_path")
                or metadata.get("source_path")
                or metadata.get("canonical_url")
                or ""
            )
            chunk_index = int(chunk.get("chunk_index", -1))
            body = str(chunk.get("text") or chunk.get("snippet") or "")
        else:
            metadata = getattr(chunk, "metadata", {}) or {}
            source_path = str(
                metadata.get("project_doc_path")
                or metadata.get("source_path")
                or metadata.get("canonical_url")
                or getattr(chunk, "source", "")
                or ""
            )
            chunk_index = int(getattr(chunk, "chunk_index", -1))
            body = str(getattr(chunk, "text", "") or "")
        return (
            _semantic_source_identity(source_path),
            chunk_index,
            hashlib.sha256(body.encode("utf-8")).hexdigest(),
        )

    def retrieval_scope(query: str, kwargs: dict[str, Any]) -> tuple[Any, ...]:
        filters = kwargs.get("filters") or {}
        if not isinstance(filters, dict):
            filters = {}
        project_path = str(filters.get("project_path") or "")
        project = Path(project_path).name if project_path else "unknown-project"
        return (
            project,
            query,
            str(filters.get("authority") or ""),
            str(filters.get("source_class") or ""),
            str(filters.get("doc_scope") or ""),
            str(kwargs.get("mode") or ""),
            str(kwargs.get("expand") or ""),
            int(kwargs.get("limit") or -1),
            int(kwargs.get("budget") or -1),
        )

    def call_identity(key: tuple[Any, ...], fingerprint: str) -> str:
        encoded = json.dumps(key, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return f"{hashlib.sha256(encoded).hexdigest()[:24]}:{fingerprint}"

    def observed_run(self: Any, query: str, *args: Any, **kwargs: Any) -> Any:
        scope = retrieval_scope(query, kwargs)
        occurrence = call_occurrences[scope]
        call_occurrences[scope] += 1
        key = (*scope, occurrence)
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
                fixed_pools[key] = [semantic_candidate_key(chunk) for chunk in chunks]
            frozen = fixed_pools.get(key)
            if frozen is None:
                raise RuntimeError(f"counterfactual retrieval call absent from frozen current pool: {key!r}")
            buckets: dict[tuple[str, int, str], list[Any]] = defaultdict(list)
            for chunk in chunks:
                buckets[semantic_candidate_key(chunk)].append(chunk)
            remapped: list[Any] = []
            missing_candidates: list[tuple[str, int, str]] = []
            for candidate_key in frozen:
                bucket = buckets.get(candidate_key)
                if not bucket:
                    missing_candidates.append(candidate_key)
                    continue
                remapped.append(bucket.pop(0))
            if missing_candidates:
                raise RuntimeError(
                    f"fresh lane cannot replay frozen semantic pool for {key!r}: missing={missing_candidates!r}"
                )
            controlled_chunks = remapped
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
        if not requalification:
            stack.enter_context(patch.object(projection, "_requalify_visible_source", _trust_inherited_requalification))
        if not contextualization:
            stack.enter_context(patch.object(projection, "_expand_selected_snippets", _no_contextualization))
        if documents_for is not None:
            stack.enter_context(patch.object(evidence, "documents_for", documents_for))
        if registry_for is not None:
            stack.enter_context(patch.object(evidence, "registry_for", registry_for))
        summary = evidence.run(output)
    cpu = time.process_time() - started_cpu
    wall = time.perf_counter() - started_wall
    rows = json.loads((output / "rows.json").read_text(encoding="utf-8"))
    metrics = deepcopy(summary["variants"]["A-current"])
    metrics["process_cpu_seconds"] = round(cpu, 6)
    metrics["wall_seconds"] = round(wall, 6)
    metrics["cpu_seconds_per_case"] = round(cpu / max(1, len(rows)), 6)
    if causal_lane and set(seen_call_keys) != set(fixed_pools):
        missing = sorted(set(fixed_pools) - set(seen_call_keys))
        extra = sorted(set(seen_call_keys) - set(fixed_pools))
        raise RuntimeError(f"fixed-pool retrieval topology changed: missing={missing!r} extra={extra!r}")
    return {
        "name": name,
        "output": output,
        "summary": summary,
        "metrics": metrics,
        "rows": rows,
        "cap_inputs": cap_inputs,
        "raw_cap_inputs": raw_cap_inputs,
        "fixed_pool_calls": len(fixed_pools) if causal_lane else 0,
    }
'''
path.write_text(text[:start] + replacement + text[end:], encoding='utf-8')
PY_CANONICAL_LANE
"""
script = script.replace(anchor, repair + anchor, 1)
finalizer.write_text(script, encoding="utf-8")

Path(__file__).unlink()
