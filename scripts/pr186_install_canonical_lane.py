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
    # Evaluation-only control: freeze the exact pre-cap baseline chunks.  Each
    # counterfactual receives those chunks, with only fresh-index project
    # identity/path rebound to its own isolated corpus.  Raw fresh-index pools
    # are still fingerprinted separately so retrieval drift remains visible.
    fixed_pools: dict[tuple[Any, ...], list[Any]] = globals().setdefault(
        "_SYSTEMIC_FIXED_PRE_CAP_POOLS", {}
    )
    if capture_fixed_pool:
        fixed_pools.clear()
    call_occurrences: Counter[tuple[Any, ...]] = Counter()
    active_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    seen_call_keys: list[tuple[Any, ...]] = []
    original_run = RetrievalDispatcher.run
    original_cap = RetrievalDispatcher._limit_sections_per_source

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

    def rebind_chunk(chunk: Any, filters: dict[str, Any]) -> Any:
        value = deepcopy(chunk)
        if isinstance(value, dict):
            metadata = dict(value.get("metadata") or {})
            project_identity = str(filters.get("project_identity") or "")
            project_path = str(filters.get("project_path") or "")
            if project_identity:
                metadata["project_identity"] = project_identity
                if "repository_identity" in metadata:
                    metadata["repository_identity"] = project_identity
            if project_path:
                metadata["project_path"] = project_path
            value["metadata"] = metadata
            if project_identity and "project_identity" in value:
                value["project_identity"] = project_identity
            return value
        metadata = dict(getattr(value, "metadata", {}) or {})
        project_identity = str(filters.get("project_identity") or "")
        project_path = str(filters.get("project_path") or "")
        if project_identity:
            metadata["project_identity"] = project_identity
            if "repository_identity" in metadata:
                metadata["repository_identity"] = project_identity
        if project_path:
            metadata["project_path"] = project_path
        copier = getattr(value, "model_copy", None)
        if callable(copier):
            return copier(update={"metadata": metadata})
        setattr(value, "metadata", metadata)
        return value

    def observed_run(self: Any, query: str, *args: Any, **kwargs: Any) -> Any:
        scope = retrieval_scope(query, kwargs)
        occurrence = call_occurrences[scope]
        call_occurrences[scope] += 1
        key = (*scope, occurrence)
        filters = kwargs.get("filters") or {}
        filters = dict(filters) if isinstance(filters, dict) else {}
        active_calls.append((key, filters))
        seen_call_keys.append(key)
        try:
            return original_run(self, query, *args, **kwargs)
        finally:
            popped_key, _ = active_calls.pop()
            if popped_key != key:
                raise RuntimeError("retrieval call stack lost deterministic ordering")

    def observed_cap(self: Any, chunks: list[Any], *, limit: int | None = None, expand: str | None = None) -> list[Any]:
        if not active_calls:
            raise RuntimeError("pre-cap pool observed outside RetrievalDispatcher.run")
        key, filters = active_calls[-1]
        raw_fingerprint = _candidate_pool_fingerprint(chunks)
        raw_cap_inputs.append(call_identity(key, raw_fingerprint))
        controlled_chunks = chunks
        if causal_lane:
            if capture_fixed_pool:
                fixed_pools[key] = deepcopy(chunks)
            frozen = fixed_pools.get(key)
            if frozen is None:
                raise RuntimeError(f"counterfactual retrieval call absent from frozen current pool: {key!r}")
            controlled_chunks = [rebind_chunk(chunk, filters) for chunk in frozen]
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
