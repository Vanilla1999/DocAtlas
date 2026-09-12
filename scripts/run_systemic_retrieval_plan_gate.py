#!/usr/bin/env python3
"""Reproducible acceptance for the systemic retrieval mechanics change.

Counterfactuals are evaluation-only: they patch production boundaries in-process,
run against fresh isolated indexes, and never alter the public runtime contract.
Raw traces stay outside the checkout; only the compact acceptance summary may be
written to the repository.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path
import random
import shutil
import subprocess
import time
from typing import Any
from unittest.mock import patch

from eval.evidence_quality_v2 import run as evidence
from eval.evidence_quality_v2.cost import count_input, model_visible_text
from eval.evidence_quality_v2.semantic import assess_context
from docmancer.docs.application import docs_context_projection as projection
from docmancer.retrieval.dispatch import RetrievalDispatcher

REPO = Path(__file__).resolve().parents[1]
HOLDOUT = REPO / "eval" / "systemic_retrieval_plan" / "holdout"
DEFAULT_REPORT = REPO / "experiments" / "finalization" / "PR186_SYSTEMIC_RETRIEVAL_ACCEPTANCE.json"

MAX_TOKENS = 800
SELECTION_POOL_LIMIT = 8
SELECTION_PACKAGE_LIMIT = 3
BEAM_WIDTH = 4
PRIMARY_OUTCOME = "within_budget_sufficient"
HISTORICAL_CURRENT_FLOOR = 28
HISTORICAL_NO_CONTEXT_FLOOR = 18


def _ok(row: dict[str, Any]) -> bool:
    return bool(
        "error" not in row
        and row.get("assessment", {}).get("context_sufficiency") == "sufficient"
        and not row.get("safety_errors")
    )


def _single_variant_protocol(base: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(base)
    value["variants"] = ["A-current"]
    return value


def _no_source_cap(self: Any, chunks: list[Any], *, limit: int | None = None, expand: str | None = None) -> list[Any]:
    if (expand or "").lower() in {"adjacent", "page"}:
        return chunks
    return chunks[:limit] if limit is not None else chunks


def _strict_source_cap(self: Any, chunks: list[Any], *, limit: int | None = None, expand: str | None = None) -> list[Any]:
    if (expand or "").lower() in {"adjacent", "page"}:
        return chunks
    max_per_source = getattr(self.config.retrieval, "max_sections_per_source", None)
    if not max_per_source:
        return chunks[:limit] if limit is not None else chunks
    counts: dict[str, int] = {}
    selected: list[Any] = []
    for chunk in chunks:
        metadata = getattr(chunk, "metadata", {}) or {}
        source = str(metadata.get("canonical_url") or getattr(chunk, "source", "") or "")
        if counts.get(source, 0) >= int(max_per_source):
            continue
        counts[source] = counts.get(source, 0) + 1
        selected.append(chunk)
        if limit is not None and len(selected) >= limit:
            break
    return selected


def _trust_inherited_requalification(source: dict[str, Any], *, query_text: dict[str, str]) -> dict[str, Any]:
    del query_text
    value = deepcopy(source)
    matches = {
        str(query_id): dict(trace)
        for query_id, trace in (value.get("retrieval_query_matches") or {}).items()
        if isinstance(trace, dict)
    }
    value["retrieval_query_matches"] = matches
    value["retrieval_query_ids"] = [
        query_id for query_id, trace in matches.items() if trace.get("qualified") is True
    ]
    return value


def _no_contextualization(sources: list[dict[str, Any]], **_: Any) -> list[dict[str, Any]]:
    return deepcopy(sources)


class _FrozenCasePools:
    """Evaluation-only baseline discovery support, isolated by whole question.

    A counterfactual may consume fewer/repeated routes. Unseen routes have no
    candidates in this fixed-support estimand; natural end-to-end runs remain
    separate. Pools and runtime IDs belong to the same unchanged fixture DB.
    """

    def __init__(self) -> None:
        self.cases: dict[tuple[str, str], dict[tuple[Any, ...], list[Any]]] = {}

    def capture(self, case: tuple[str, str], route: tuple[Any, ...], chunks: list[Any]) -> None:
        routes = self.cases.setdefault(case, {})
        if route in routes and _candidate_pool_fingerprint(routes[route]) != _candidate_pool_fingerprint(chunks):
            raise RuntimeError("baseline route changed within one case")
        routes[route] = deepcopy(chunks)

    def replay(self, case: tuple[str, str], route: tuple[Any, ...]) -> list[Any]:
        return deepcopy(self.cases[case].get(route, []))

    def fingerprint(self, case: tuple[str, str]) -> str:
        entries = [(repr(route), _candidate_pool_fingerprint(chunks))
                   for route, chunks in self.cases[case].items()]
        return hashlib.sha256(json.dumps(sorted(entries)).encode()).hexdigest()


def _run_lane(*, name: str, work: Path, protocol: dict[str, Any], cases: list[dict[str, Any]], manifest: dict[str, Any], cap: str = "bounded", requalification: bool = True, contextualization: bool = True, documents_for: Any | None = None, registry_for: Any | None = None, pools: _FrozenCasePools | None = None, fixture_output: Path | None = None) -> dict[str, Any]:
    output = work / name
    shutil.rmtree(output, ignore_errors=True)
    lane_protocol = _single_variant_protocol(protocol)
    capturing = pools is not None and fixture_output is None
    active_case: tuple[str, str] | None = None
    active_routes: list[tuple[Any, ...]] = []
    seen_cases: set[tuple[str, str]] = set()
    consumed: list[str] = []
    unsupported: list[dict[str, Any]] = []
    original_run = RetrievalDispatcher.run
    original_cap = RetrievalDispatcher._limit_sections_per_source
    original_observe = evidence.observe_call

    def observed_call(service: Any, arguments: dict[str, Any]) -> Any:
        nonlocal active_case
        active_case = (Path(arguments["project_path"]).name, arguments["question"])
        seen_cases.add(active_case)
        if capturing:
            pools.cases.setdefault(active_case, {})
        try:
            return original_observe(service, arguments)
        finally:
            active_case = None

    def observed_run(self: Any, query: str, *args: Any, **kwargs: Any) -> Any:
        # Case identity carries the project. Keep all policy/requirements input
        # in the route key; no global occurrence counter couples different cases.
        route = (query, json.dumps(kwargs, sort_keys=True, default=str))
        active_routes.append(route)
        try:
            return original_run(self, query, *args, **kwargs)
        finally:
            active_routes.pop()

    def observed_cap(self: Any, chunks: list[Any], *, limit: int | None = None, expand: str | None = None) -> list[Any]:
        controlled = chunks
        if pools is not None:
            if active_case is None or not active_routes:
                raise RuntimeError("pre-cap pool outside a case retrieval")
            route = (*active_routes[-1], limit, expand)
            if capturing:
                pools.capture(active_case, route, chunks)
            elif route not in pools.cases[active_case]:
                unsupported.append({"case": active_case, "query": active_routes[-1][0]})
            controlled = pools.replay(active_case, route)
            consumed.append(_candidate_pool_fingerprint(controlled))
        if cap == "off":
            return _no_source_cap(self, controlled, limit=limit, expand=expand)
        if cap == "strict":
            return _strict_source_cap(self, controlled, limit=limit, expand=expand)
        if cap == "bounded":
            return original_cap(self, controlled, limit=limit, expand=expand)
        raise ValueError(f"unknown cap mode: {cap}")

    started_cpu = time.process_time()
    started_wall = time.perf_counter()
    with ExitStack() as stack:
        stack.enter_context(patch.object(evidence, "load_protocol", return_value=(lane_protocol, deepcopy(cases), deepcopy(manifest))))
        stack.enter_context(patch.object(evidence, "observe_call", observed_call))
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
        summary = evidence.run(output, fixture_output=fixture_output)
    cpu = time.process_time() - started_cpu
    wall = time.perf_counter() - started_wall
    rows = json.loads((output / "rows.json").read_text(encoding="utf-8"))
    metrics = deepcopy(summary["variants"]["A-current"])
    metrics["process_cpu_seconds"] = round(cpu, 6)
    metrics["wall_seconds"] = round(wall, 6)
    metrics["cpu_seconds_per_case"] = round(cpu / max(1, len(rows)), 6)
    available = {repr(case): pools.fingerprint(case) for case in sorted(seen_cases)} if pools is not None else {}
    return {
        "name": name, "output": output, "summary": summary, "metrics": metrics,
        "rows": rows, "available_case_pools": available, "consumed_pools": consumed,
        "unsupported_routes": unsupported,
    }


def _paired(baseline_rows: list[dict[str, Any]], variant_rows: list[dict[str, Any]], *, seed: int, resamples: int) -> dict[str, Any]:
    baseline = {row["id"]: row for row in baseline_rows}
    variant = {row["id"]: row for row in variant_rows}
    if len(baseline) != len(baseline_rows) or len(variant) != len(variant_rows) or baseline.keys() != variant.keys():
        raise ValueError("paired case inventory changed or contains duplicates")
    ids = sorted(set(baseline).intersection(variant))
    wins = [case_id for case_id in ids if _ok(variant[case_id]) and not _ok(baseline[case_id])]
    losses = [case_id for case_id in ids if _ok(baseline[case_id]) and not _ok(variant[case_id])]
    groups: dict[str, list[int]] = defaultdict(list)
    family_delta: dict[str, list[int]] = defaultdict(list)
    for case_id in ids:
        before = baseline[case_id]
        after = variant[case_id]
        delta = int(_ok(after)) - int(_ok(before))
        groups[str(before.get("project") or "")].append(delta)
        family_delta[str(before.get("family") or "")].append(delta)
    project_deltas = [sum(values) / len(values) for values in groups.values() if values]
    bootstrap: list[float] = []
    if project_deltas:
        rng = random.Random(seed)
        for _ in range(max(1, resamples)):
            sample = rng.choices(project_deltas, k=len(project_deltas))
            bootstrap.append(sum(sample) / len(sample))
        bootstrap.sort()
        lower = bootstrap[int(len(bootstrap) * 0.025)]
        upper = bootstrap[min(len(bootstrap) - 1, int(len(bootstrap) * 0.975))]
    else:
        lower = upper = None
    return {
        "pairs": len(ids), "wins": wins, "losses": losses,
        "ties": len(ids) - len(wins) - len(losses),
        "project_groups": len(project_deltas),
        "mean_project_delta": (sum(project_deltas) / len(project_deltas) if project_deltas else None),
        "cluster_bootstrap_95": [lower, upper],
        "family_delta": {family: {"n": len(values), "net": sum(values)} for family, values in sorted(family_delta.items())},
    }


def _failure_families(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get("family") or "unknown") for row in rows if not _ok(row)).items()))


def _compact_expanded_observation(output: Path) -> dict[str, Any]:
    calls = before_sources = after_sources = changed = lost = 0
    examples: list[dict[str, Any]] = []
    trace_root = output / "traces" / "A-current"
    for path in sorted(trace_root.glob("*.json")):
        trace = json.loads(path.read_text(encoding="utf-8"))
        for call in trace.get("stages", {}).get("expansions", []):
            calls += 1
            before = call.get("before") or []
            after = call.get("after") or []
            before_sources += len(before)
            after_sources += len(after)
            after_by_id = {str(row.get("evidence_id") or ""): row for row in after if row.get("evidence_id")}
            for row in before:
                evidence_id = str(row.get("evidence_id") or "")
                if not evidence_id:
                    continue
                final = after_by_id.get(evidence_id)
                if final is None:
                    lost += 1
                    continue
                before_text = str(row.get("snippet") or "")
                after_text = str(final.get("snippet") or "")
                if after_text != before_text:
                    changed += 1
                    if len(examples) < 8:
                        examples.append({"case": path.stem, "evidence_id": evidence_id, "compact_chars": len(before_text), "expanded_chars": len(after_text)})
    return {"calls": calls, "compact_sources_observed": before_sources, "expanded_sources_observed": after_sources, "changed_spans": changed, "lost_evidence_identities": lost, "examples": examples}


def _final_citation_policy(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    checked = 0
    registry_by_project = {project: evidence.registry_for(project, manifest) for project in sorted({str(row.get("project") or "") for row in rows})}
    for row in rows:
        registry = registry_by_project.get(str(row.get("project") or ""), {})
        for source in row.get("payload", {}).get("sources") or []:
            checked += 1
            path = str(source.get("path_or_url") or "")
            metadata = registry.get(path)
            if not isinstance(metadata, dict):
                violations.append({"case": row["id"], "path": path, "reason": "unregistered"})
                continue
            if metadata.get("authority") != "source_of_truth":
                violations.append({"case": row["id"], "path": path, "reason": "authority"})
            if metadata.get("lifecycle") not in {"active", "current"}:
                violations.append({"case": row["id"], "path": path, "reason": "lifecycle"})
            if metadata.get("scope") != "project":
                violations.append({"case": row["id"], "path": path, "reason": "scope"})
        for rejected in row.get("assessment", {}).get("rejected_sources") or []:
            violations.append({"case": row["id"], "path": str(rejected.get("evidence_id") or ""), "reason": str(rejected.get("reason") or "policy_rejection")})
    return {"checked_final_citations": checked, "violations": violations, "status": "PASS" if not violations else "FAIL"}




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

def _candidate_pool_fingerprint(pool: list[Any]) -> str:
    """Hash semantic ranked candidates while ignoring fresh-index identities."""
    canonical: list[dict[str, Any]] = []
    for row in pool:
        if isinstance(row, dict):
            metadata = row.get("metadata") or {}
            path = str(
                row.get("project_doc_path")
                or row.get("source_path")
                or row.get("path")
                or row.get("source")
                or metadata.get("project_doc_path")
                or metadata.get("source_path")
                or metadata.get("canonical_url")
                or ""
            )
            chunk_index = row.get("chunk_index")
            body = str(row.get("text") or row.get("snippet") or "")
        else:
            metadata = getattr(row, "metadata", {}) or {}
            path = str(
                metadata.get("project_doc_path")
                or metadata.get("source_path")
                or metadata.get("canonical_url")
                or getattr(row, "source", "")
                or ""
            )
            chunk_index = getattr(row, "chunk_index", None)
            body = str(getattr(row, "text", "") or "")
        canonical.append(
            {
                "path": _semantic_source_identity(path),
                "chunk_index": chunk_index,
                "text_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            }
        )
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def _candidate_structure(pool: list[dict[str, Any]]) -> dict[str, Any]:
    sources: list[str] = []
    parents: list[str] = []
    for row in pool:
        sources.append(str(row.get("path") or row.get("source") or row.get("source_path") or ""))
        parents.append(str(row.get("parent_logical_id") or ""))
    parent_counts = Counter(value for value in parents if value)
    return {
        "candidate_count": len(pool),
        "unique_sources": len({value for value in sources if value}),
        "candidates_with_parent": sum(bool(value) for value in parents),
        "unique_parents": len(parent_counts),
        "same_parent_pairs": sum(count * (count - 1) // 2 for count in parent_counts.values()),
    }


def _visible_proxy(payload: dict[str, Any], question: str, tokens: int) -> tuple[int, int, int, int]:
    query_terms = {term.casefold() for term in question.replace("`", " ").replace("_", " ").split() if len(term) >= 4}
    overlap: set[str] = set()
    paths: set[str] = set()
    for source in payload.get("sources") or []:
        paths.add(str(source.get("path_or_url") or ""))
        text = str(source.get("snippet") or "").casefold()
        overlap.update(term for term in query_terms if term in text)
    return (len(overlap), len(paths), len(payload.get("sources") or []), -tokens)


def _proxy_choice(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select without reading gold sufficiency/support labels."""
    feasible = [c for c in candidates if not c.get("error") and not c.get("safety_errors")
                and c["tokens"] <= MAX_TOKENS and 0 < c["sources"] <= SELECTION_PACKAGE_LIMIT]
    return max(feasible, key=lambda c: (tuple(c["proxy"]), tuple(-i for i in c["indices"])), default=None)


def _selection_diagnostic(*, cases: list[dict[str, Any]], manifest: dict[str, Any], current_lane: dict[str, Any]) -> dict[str, Any]:
    by_case = {case["id"]: case for case in cases}
    registry_by_project = {project: evidence.registry_for(project, manifest) for project in sorted({case["project_group"] for case in cases})}
    current_rows = {row["id"]: row for row in current_lane["rows"] if row.get("answerability") == "within_budget"}
    results: list[dict[str, Any]] = []
    exact_recoveries: list[str] = []
    simple_recoveries: list[str] = []
    beam_recoveries: list[str] = []
    projector_failures = 0
    proxy_recoveries: list[str] = []
    started_cpu = time.process_time()
    for case_id, row in sorted(current_rows.items()):
        if _ok(row):
            continue
        case = by_case[case_id]
        trace_path = current_lane["output"] / "traces" / "A-current" / f"{case_id}.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        projector_inputs = trace.get("stages", {}).get("projector_inputs") or []
        if len(projector_inputs) != 1:
            results.append({"id": case_id, "status": "UNOBSERVED", "reason": "projector_input_count"})
            continue
        retrieval = projector_inputs[0]
        pool = list(retrieval.get("context_pack") or ())[:SELECTION_POOL_LIMIT]
        root = current_lane["output"] / "corpus" / case["project_group"]
        registry = registry_by_project[case["project_group"]]
        cache: dict[tuple[int, ...], dict[str, Any]] = {}

        def project(indices: tuple[int, ...]) -> dict[str, Any]:
            nonlocal projector_failures
            if indices in cache:
                return cache[indices]
            candidate = deepcopy(retrieval)
            candidate["context_pack"] = [deepcopy(pool[index]) for index in indices]
            try:
                payload, snapshot = projection.project_docs_context(retrieval=candidate, max_tokens=MAX_TOKENS)
                assessment = assess_context(case, payload, registry)
                safety = evidence.audit_payload(payload, snapshot, root)
                size = count_input(model_visible_text({"structuredContent": payload}, "structured"))
                value = {
                    "indices": list(indices),
                    "sufficient": assessment["context_sufficiency"] == "sufficient" and not safety and size["actual_tokens"] <= MAX_TOKENS,
                    "required_supported": assessment["required_supported"],
                    "required_count": assessment["required_count"],
                    "tokens": size["actual_tokens"],
                    "sources": len(payload.get("sources") or []),
                    "proxy": list(_visible_proxy(payload, case["question"], size["actual_tokens"])),
                    "safety_errors": safety,
                }
            except Exception as exc:
                projector_failures += 1
                value = {"indices": list(indices), "sufficient": False, "required_supported": 0, "required_count": len(case["required_claims"]), "tokens": MAX_TOKENS + 1, "sources": 0, "proxy": [0, 0, 0, -(MAX_TOKENS + 1)], "error": f"{type(exc).__name__}: {exc}"}
            cache[indices] = value
            return value

        exact_candidates: list[dict[str, Any]] = []
        for size in range(1, min(SELECTION_PACKAGE_LIMIT, len(pool)) + 1):
            for indices in itertools.combinations(range(len(pool)), size):
                candidate = project(indices)
                if candidate["sufficient"]:
                    exact_candidates.append(candidate)
        exact = min(exact_candidates, key=lambda item: (item["tokens"], item["sources"], item["indices"]), default=None)

        exact_proxy = _proxy_choice(list(cache.values()))
        simple_success = _proxy_choice([
            project(tuple(range(size)))
            for size in range(1, min(SELECTION_PACKAGE_LIMIT, len(pool)) + 1)
        ])
        beam_states: list[tuple[int, ...]] = [()]
        beam_visited: list[dict[str, Any]] = []
        for _depth in range(1, min(SELECTION_PACKAGE_LIMIT, len(pool)) + 1):
            expanded = {(*state, index) for state in beam_states
                        for index in range(state[-1] + 1 if state else 0, len(pool))}
            scored = [project(state) for state in sorted(expanded)]
            beam_visited.extend(scored)
            # Invalid partial packages can still have feasible continuations.
            scored.sort(key=lambda item: (tuple(item["proxy"]), tuple(-i for i in item["indices"])), reverse=True)
            beam_states = [tuple(item["indices"]) for item in scored[:BEAM_WIDTH]]
        beam_success = _proxy_choice(beam_visited)
        if exact_proxy is not None and exact_proxy["sufficient"]:
            proxy_recoveries.append(case_id)
        if exact is not None:
            exact_recoveries.append(case_id)
        if simple_success is not None and simple_success["sufficient"]:
            simple_recoveries.append(case_id)
        if beam_success is not None and beam_success["sufficient"]:
            beam_recoveries.append(case_id)
        results.append({"id": case_id, "current_sufficient": False, "pool": _candidate_structure(pool), "exact_oracle_recovery": exact, "exact_proxy_choice": exact_proxy, "simple_choice": simple_success, "beam_choice": beam_success, "enumerated_packages": len(cache)})
    status = "OBSERVED" if exact_recoveries else "NOT_OBSERVED_IN_BOUNDED_POOL"
    return {
        "candidate_pool_limit": SELECTION_POOL_LIMIT,
        "package_source_limit": SELECTION_PACKAGE_LIMIT,
        "beam_width": BEAM_WIDTH,
        "reference": "exhaustive subsets through unchanged projector; oracle feasibility is separate from gold-blind exact-proxy/simple/beam selection",
        "exact_proxy_recoveries": proxy_recoveries,
        "process_cpu_seconds": time.process_time() - started_cpu,
        "selection_bottleneck": status,
        "exact_recoveries": exact_recoveries,
        "simple_recoveries": simple_recoveries,
        "beam_recoveries": beam_recoveries,
        "exact_simple_gap": sorted(set(exact_recoveries) - set(simple_recoveries)),
        "oracle_beam_sufficiency_gap": sorted(set(exact_recoveries) - set(beam_recoveries)),
        "proxy_objective_gap_cases": [r["id"] for r in results if r.get("exact_proxy_choice") and (not r.get("beam_choice") or r["beam_choice"]["proxy"] < r["exact_proxy_choice"]["proxy"])],
        "projector_failures": projector_failures,
        "production_selector_decision": "DEFER_NO_GOLD_BLIND_RECOVERY" if exact_recoveries and not proxy_recoveries else "REQUIRES_INDEPENDENT_VALIDATION" if exact_recoveries else "NOT_JUSTIFIED_BY_THIS_SAMPLE",
        "cases": results,
    }


def _singleton_diagnostic(*, cases: list[dict[str, Any]], manifest: dict[str, Any], current_lane: dict[str, Any]) -> dict[str, Any]:
    """Measure an oracle gap separately from a production-blind selector.

    The oracle may use evaluator sufficiency only after enumeration. The blind
    singleton control chooses solely from model-visible query overlap, source
    diversity/count and token cost, then gold is consulted only to score that
    already-fixed choice. This keeps the product decision independent of the
    benchmark answer key.
    """
    by_case = {case["id"]: case for case in cases}
    registry_by_project = {
        project: evidence.registry_for(project, manifest)
        for project in sorted({case["project_group"] for case in cases})
    }
    current_rows = {
        row["id"]: row for row in current_lane["rows"]
        if row.get("answerability") == "within_budget"
    }
    results: list[dict[str, Any]] = []
    exact_recoveries: list[str] = []
    simple_recoveries: list[str] = []
    blind_singleton_recoveries: list[str] = []
    blind_singleton_losses: list[str] = []
    blind_singleton_changes: list[str] = []
    projector_failures = 0

    for case_id, row in sorted(current_rows.items()):
        case = by_case[case_id]
        trace_path = current_lane["output"] / "traces" / "A-current" / f"{case_id}.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        projector_inputs = trace.get("stages", {}).get("projector_inputs") or []
        if len(projector_inputs) != 1:
            results.append({"id": case_id, "status": "UNOBSERVED", "reason": "projector_input_count"})
            continue
        retrieval = projector_inputs[0]
        pool = list(retrieval.get("context_pack") or ())[:SELECTION_POOL_LIMIT]
        root = current_lane["output"] / "corpus" / case["project_group"]
        registry = registry_by_project[case["project_group"]]
        cache: dict[tuple[int, ...], dict[str, Any]] = {}

        def project(indices: tuple[int, ...]) -> dict[str, Any]:
            nonlocal projector_failures
            if indices in cache:
                return cache[indices]
            candidate = deepcopy(retrieval)
            candidate["context_pack"] = [deepcopy(pool[index]) for index in indices]
            try:
                payload, snapshot = projection.project_docs_context(
                    retrieval=candidate, max_tokens=MAX_TOKENS
                )
                assessment = assess_context(case, payload, registry)
                safety = evidence.audit_payload(payload, snapshot, root)
                size = count_input(
                    model_visible_text({"structuredContent": payload}, "structured")
                )
                value = {
                    "indices": list(indices),
                    "sufficient": assessment["context_sufficiency"] == "sufficient" and not safety and size["actual_tokens"] <= MAX_TOKENS,
                    "required_supported": assessment["required_supported"],
                    "required_count": assessment["required_count"],
                    "tokens": size["actual_tokens"],
                    "sources": len(payload.get("sources") or []),
                    "proxy": list(_visible_proxy(payload, case["question"], size["actual_tokens"])),
                    "safety_errors": safety,
                }
            except Exception as exc:
                projector_failures += 1
                value = {
                    "indices": list(indices), "sufficient": False,
                    "required_supported": 0,
                    "required_count": len(case["required_claims"]),
                    "tokens": MAX_TOKENS + 1, "sources": 0,
                    "proxy": [0, 0, 0, -(MAX_TOKENS + 1)],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            cache[indices] = value
            return value

        current_tokens = int(row.get("size", {}).get("actual_tokens") or MAX_TOKENS + 1)
        current_proxy = list(_visible_proxy(
            row.get("payload") or {}, case["question"], current_tokens,
        ))
        current_sufficient = _ok(row)

        singleton_candidates = [project((index,)) for index in range(len(pool))]
        blind_choice = _proxy_choice(singleton_candidates)
        use_blind_choice = bool(
            blind_choice is not None and tuple(blind_choice["proxy"]) > tuple(current_proxy)
        )
        blind_sufficient = (
            bool(blind_choice["sufficient"])
            if use_blind_choice and blind_choice is not None
            else current_sufficient
        )
        if use_blind_choice:
            blind_singleton_changes.append(case_id)
        if blind_sufficient and not current_sufficient:
            blind_singleton_recoveries.append(case_id)
        if current_sufficient and not blind_sufficient:
            blind_singleton_losses.append(case_id)

        exact = None
        simple_success = None
        if not current_sufficient:
            exact_candidates: list[dict[str, Any]] = []
            for size in range(1, min(SELECTION_PACKAGE_LIMIT, len(pool)) + 1):
                for indices in itertools.combinations(range(len(pool)), size):
                    candidate = project(indices)
                    if candidate["sufficient"]:
                        exact_candidates.append(candidate)
            exact = min(
                exact_candidates,
                key=lambda item: (item["tokens"], item["sources"], item["indices"]),
                default=None,
            )
            for size in range(1, min(SELECTION_PACKAGE_LIMIT, len(pool)) + 1):
                candidate = project(tuple(range(size)))
                if candidate["sufficient"]:
                    simple_success = candidate
                    break
            if exact is not None:
                exact_recoveries.append(case_id)
            if simple_success is not None:
                simple_recoveries.append(case_id)

        results.append({
            "id": case_id,
            "current_sufficient": current_sufficient,
            "current_proxy": current_proxy,
            "pool": _candidate_structure(pool),
            "exact_recovery": exact,
            "simple_recovery": simple_success,
            "blind_singleton_choice": blind_choice,
            "blind_singleton_used": use_blind_choice,
            "blind_singleton_sufficient": blind_sufficient,
            "enumerated_packages": len(cache),
        })

    bottleneck = "OBSERVED" if exact_recoveries else "NOT_OBSERVED_IN_BOUNDED_POOL"
    oracle_gap = sorted(set(exact_recoveries) - set(simple_recoveries))
    blind_gap = sorted(set(exact_recoveries) - set(blind_singleton_recoveries))
    if not exact_recoveries:
        decision = "NOT_JUSTIFIED_BY_THIS_SAMPLE"
    elif not blind_gap and not blind_singleton_losses:
        decision = "BOUNDED_SINGLETON_RESCUE_JUSTIFIED_ON_EXPOSED_SAMPLE"
    else:
        decision = "NO_PRODUCTION_SELECTOR_VALIDATED"
    return {
        "candidate_pool_limit": SELECTION_POOL_LIMIT,
        "package_source_limit": SELECTION_PACKAGE_LIMIT,
        "blind_singleton_candidate_limit": SELECTION_POOL_LIMIT,
        "reference": (
            "exact oracle enumerates bounded subsets with evaluator sufficiency; "
            "blind singleton choice is fixed only by model-visible proxy before gold scoring"
        ),
        "selection_bottleneck": bottleneck,
        "exact_recoveries": exact_recoveries,
        "simple_recoveries": simple_recoveries,
        "exact_simple_gap": oracle_gap,
        "blind_singleton_recoveries": blind_singleton_recoveries,
        "blind_singleton_losses": blind_singleton_losses,
        "blind_singleton_changes": blind_singleton_changes,
        "blind_proxy_exact_gap": blind_gap,
        "projector_failures": projector_failures,
        "production_selector_decision": decision,
        "cases": results,
    }



def _load_holdout() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    cases_doc = json.loads((HOLDOUT / "cases.json").read_text(encoding="utf-8"))
    manifest = json.loads((HOLDOUT / "source-manifest.json").read_text(encoding="utf-8"))
    documents: dict[str, str] = {}
    for row in manifest["sources"]:
        key = f"{row['project']}:{row['path']}"
        path = HOLDOUT / "sources" / row["project"] / row["path"]
        data = path.read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        if actual != row["sha256"]:
            raise RuntimeError(f"holdout source hash mismatch: {key}")
        documents[key] = data.decode("utf-8")
    return cases_doc["cases"], manifest, documents


def _holdout_adapters(manifest: dict[str, Any], documents: dict[str, str]):
    def documents_for(project: str, _manifest: dict[str, Any]) -> dict[str, str]:
        return {row["path"]: documents[f"{project}:{row['path']}"] for row in manifest["sources"] if row["project"] == project}

    def registry_for(project: str, _manifest: dict[str, Any]) -> dict[str, Any]:
        return {row["path"]: {"project_group": project, "version": row["ref"], "scope": "project", "authority": "source_of_truth", "lifecycle": "active"} for row in manifest["sources"] if row["project"] == project}

    return documents_for, registry_for


def _source_manifest_identity(manifest: dict[str, Any]) -> str:
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("/tmp/docatlas-systemic-plan"))
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    work = args.work.resolve()
    if work.is_relative_to(REPO.resolve()):
        raise SystemExit("--work must be outside the repository checkout")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    frozen_protocol, frozen_cases, frozen_manifest = evidence.load_protocol()
    causal_cases = [case for case in frozen_cases if case["answerability"] == "within_budget"]
    if len(causal_cases) != 48:
        raise SystemExit(f"expected frozen 48 within-budget cases, got {len(causal_cases)}")
    seed = int(frozen_protocol["bootstrap"]["seed"])
    resamples = int(frozen_protocol["bootstrap"]["resamples"])

    lanes: dict[str, dict[str, Any]] = {}
    lane_specs = (
        ("cap_on_requal_on", "bounded", True, True),
        ("cap_off_requal_on", "off", True, True),
        ("cap_on_requal_off", "bounded", False, True),
        ("cap_off_requal_off", "off", False, True),
        ("contextualization_off", "bounded", True, False),
    )
    pools = _FrozenCasePools()
    fixture_output = None
    for name, cap, requalification, contextualization in lane_specs:
        lanes[name] = _run_lane(name=name, work=work / "causal", protocol=frozen_protocol, cases=causal_cases, manifest=frozen_manifest, cap=cap, requalification=requalification, contextualization=contextualization, pools=pools, fixture_output=fixture_output)
        fixture_output = lanes["cap_on_requal_on"]["output"]

    full80 = _run_lane(name="full80_current", work=work / "acceptance", protocol=frozen_protocol, cases=frozen_cases, manifest=frozen_manifest)
    current = lanes["cap_on_requal_on"]
    fixed_pool = {
        name: {
            "cases": len(lane["available_case_pools"]),
            "same_as_current": lane["available_case_pools"] == current["available_case_pools"],
            "available_case_fingerprints": lane["available_case_pools"],
            "consumed_calls": len(lane["consumed_pools"]),
            "unsupported_routes": lane["unsupported_routes"],
        }
        for name, lane in lanes.items()
    }
    paired = {name: _paired(current["rows"], lane["rows"], seed=seed, resamples=resamples) for name, lane in lanes.items() if name != "cap_on_requal_on"}
    cells = {name: {**lane["metrics"], "failure_families": _failure_families(lane["rows"])} for name, lane in lanes.items()}
    current_rate = cells["cap_on_requal_on"]["within_budget_sufficient"] / 48
    no_cap_rate = cells["cap_off_requal_on"]["within_budget_sufficient"] / 48
    no_requal_rate = cells["cap_on_requal_off"]["within_budget_sufficient"] / 48
    neither_rate = cells["cap_off_requal_off"]["within_budget_sufficient"] / 48
    interaction = (neither_rate - no_requal_rate) - (no_cap_rate - current_rate)

    compact_expanded = _compact_expanded_observation(current["output"])
    final_policy = _final_citation_policy(current["rows"], frozen_manifest)
    selection = _selection_diagnostic(cases=causal_cases, manifest=frozen_manifest, current_lane=current)

    singleton = _singleton_diagnostic(cases=causal_cases, manifest=frozen_manifest, current_lane=current)
    holdout_cases, holdout_manifest, holdout_documents = _load_holdout()
    documents_for, registry_for = _holdout_adapters(holdout_manifest, holdout_documents)
    holdout_current = _run_lane(name="holdout_current", work=work / "holdout", protocol=frozen_protocol, cases=holdout_cases, manifest=holdout_manifest, documents_for=documents_for, registry_for=registry_for)
    holdout_strict = _run_lane(name="holdout_strict_cap", work=work / "holdout", protocol=frozen_protocol, cases=holdout_cases, manifest=holdout_manifest, cap="strict", documents_for=documents_for, registry_for=registry_for)
    holdout_pair = _paired(holdout_strict["rows"], holdout_current["rows"], seed=seed, resamples=resamples)
    holdout_generalization = "SUPPORTED_ON_POSTHOC_INDEPENDENT_PROJECT_SAMPLE" if holdout_pair["wins"] and not holdout_pair["losses"] else "REGRESSION_OBSERVED" if holdout_pair["losses"] else "NO_REGRESSION_BUT_IMPROVEMENT_NOT_OBSERVED"

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    frozen_current = full80["metrics"]
    full80_valid_rows = [row for row in full80["rows"] if "error" not in row]
    full80_budget_rows = [row for row in full80_valid_rows if row.get("answerability") == "within_budget"]
    full80_budget_max_tokens = max((int(row.get("size", {}).get("actual_tokens") or 0) for row in full80_budget_rows), default=0)
    full80_all_valid_max_tokens = max((int(row.get("size", {}).get("actual_tokens") or 0) for row in full80_valid_rows), default=0)
    report = {
        "schema_version": "systemic-retrieval-plan-acceptance-v2",
        "generated_from_head": head,
        "frozen_configuration": {
            "primary_outcome": PRIMARY_OUTCOME,
            "utility_function": "1 iff context_sufficiency is sufficient and safety_errors is empty; otherwise 0",
            "max_model_visible_tokens": MAX_TOKENS,
            "selection_candidate_pool": SELECTION_POOL_LIMIT,
            "selection_package_sources": SELECTION_PACKAGE_LIMIT,
            "beam_width": BEAM_WIDTH,
            "historical_current_floor": HISTORICAL_CURRENT_FLOOR,
            "historical_no_context_floor": HISTORICAL_NO_CONTEXT_FLOOR,
            "counterfactual_cap": "bounded structural overflow vs no per-source cap",
            "counterfactual_requalification": "visible-text requalification vs inherited retrieval qualification",
            "contextualization_control": "same end-to-end call with final snippet expansion disabled",
            "performance_metrics_frozen": ["process_cpu_seconds", "cpu_seconds_per_case", "latency_seconds.p95"],
        },
        "full_frozen_80": {
            **frozen_current,
            "failure_families": _failure_families(full80["rows"]),
            "historical_floor_preserved": frozen_current["within_budget"] == 48 and frozen_current["within_budget_sufficient"] >= HISTORICAL_CURRENT_FLOOR,
            "within_budget_max_actual_model_visible_tokens": full80_budget_max_tokens,
            "all_valid_max_actual_model_visible_tokens_diagnostic": full80_all_valid_max_tokens,
            "actual_full_dto_budget": full80_budget_max_tokens <= MAX_TOKENS,
        },
        "causal_2x2": {"cells": cells, "paired_against_current": paired, "fixed_pre_cap_candidate_pool": fixed_pool, "difference_in_differences_success_rate": interaction, "interpretation": "Counterfactual lanes replay the frozen current pre-cap pools; raw fresh-index drift is reported separately. No causal claim extends beyond this fixed exposed corpus."},
        "contextualization": {"paired_against_current": paired["contextualization_off"], "compact_and_expanded": compact_expanded},
        "source_policy": {"pre_hydration": {"status": "PRODUCTION_BOUNDARY_TESTED", "test": "tests/test_pre_hydration_source_policy.py", "defense_in_depth_post_hydration_filter_retained": True}, "final_citations": final_policy},
        "selection": selection,
        "singleton_control": singleton,
        "independent_project_sample": {
            "state": "POSTHOC_NOT_HIDDEN_OR_PREREGISTERED",
            "projects": sorted({case["project_group"] for case in holdout_cases}),
            "cases": len(holdout_cases),
            "source_manifest_sha256": _source_manifest_identity(holdout_manifest),
            "current": holdout_current["metrics"],
            "historical_strict_cap_counterfactual": holdout_strict["metrics"],
            "paired_current_vs_strict_cap": holdout_pair,
            "generalization_result": holdout_generalization,
            "claim_boundary": "Independent projects are measured, but this is a post-hoc sample and not external hidden validation.",
        },
        "claim_boundaries": {"live_agent_end_to_end": "NOT_MEASURED", "total_task_token_savings": "NOT_MEASURED", "market_or_unseen_distribution_generalization": "NOT_CLAIMED", "production_selector": selection["production_selector_decision"]},
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "head": head,
        "frozen_80": {"within_budget": frozen_current["within_budget"], "within_budget_sufficient": frozen_current["within_budget_sufficient"], "operational_errors": frozen_current["operational_errors"], "integrity_violations": frozen_current["source_integrity_or_contract_violations"]},
        "causal_cells": {name: value["within_budget_sufficient"] for name, value in cells.items()},
        "selection": {"status": selection["selection_bottleneck"], "exact_recoveries": selection["exact_recoveries"], "beam_recoveries": selection["beam_recoveries"]},
        "holdout": {"current": holdout_current["metrics"]["within_budget_sufficient"], "strict": holdout_strict["metrics"]["within_budget_sufficient"], "comparison": holdout_generalization},
    }, indent=2, ensure_ascii=False))

    failures: list[str] = []
    for name, lane in lanes.items():
        if lane["metrics"]["cases"] != 48 or lane["metrics"]["operational_errors"]:
            failures.append(f"{name}: incomplete causal case inventory or operational errors")
        if lane["metrics"]["source_integrity_or_contract_violations"]:
            failures.append(f"{name}: source integrity or contract violations")
    if selection["projector_failures"]:
        failures.append("selection diagnostic has projector exceptions")
    if frozen_current["cases"] != 80:
        failures.append("frozen case inventory changed")
    if frozen_current["within_budget"] != 48:
        failures.append("frozen within-budget inventory changed")
    if frozen_current["within_budget_sufficient"] < HISTORICAL_CURRENT_FLOOR:
        failures.append("historical 28/48 floor regressed")
    if frozen_current["operational_errors"]:
        failures.append("current frozen run has operational errors")
    if frozen_current["source_integrity_or_contract_violations"]:
        failures.append("current frozen run has source integrity violations")
    if current["metrics"]["within_budget_sufficient"] < HISTORICAL_CURRENT_FLOOR:
        failures.append("causal current lane regressed below 28/48")
    if lanes["contextualization_off"]["metrics"]["within_budget_sufficient"] < HISTORICAL_NO_CONTEXT_FLOOR:
        failures.append("no-contextualization floor regressed below 18/48")
    if len(full80_budget_rows) != 48:
        failures.append("within-budget valid DTO inventory changed")
    if full80_budget_max_tokens > MAX_TOKENS:
        failures.append("within-budget full model-visible DTO exceeded the 800-token ceiling")
    if not all(value["same_as_current"] for value in fixed_pool.values()):
        failures.append("2x2/contextualization lanes did not share the same case-level pre-cap support")
    if compact_expanded["lost_evidence_identities"]:
        failures.append("contextualization lost compact evidence identities")
    if final_policy["violations"]:
        failures.append("final citation source policy violation")
    if holdout_current["metrics"]["operational_errors"]:
        failures.append("independent sample has operational errors")
    if holdout_current["metrics"]["source_integrity_or_contract_violations"]:
        failures.append("independent sample has source integrity violations")
    if holdout_pair["losses"]:
        failures.append("independent sample regressed against strict-cap counterfactual")
    if failures:
        raise SystemExit("; ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
