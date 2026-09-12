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


def _run_lane(*, name: str, work: Path, protocol: dict[str, Any], cases: list[dict[str, Any]], manifest: dict[str, Any], cap: str = "bounded", requalification: bool = True, contextualization: bool = True, documents_for: Any | None = None, registry_for: Any | None = None) -> dict[str, Any]:
    output = work / name
    shutil.rmtree(output, ignore_errors=True)
    lane_protocol = _single_variant_protocol(protocol)
    started_cpu = time.process_time()
    started_wall = time.perf_counter()
    with ExitStack() as stack:
        stack.enter_context(patch.object(evidence, "load_protocol", return_value=(lane_protocol, deepcopy(cases), deepcopy(manifest))))
        if cap == "off":
            stack.enter_context(patch.object(RetrievalDispatcher, "_limit_sections_per_source", _no_source_cap))
        elif cap == "strict":
            stack.enter_context(patch.object(RetrievalDispatcher, "_limit_sections_per_source", _strict_source_cap))
        elif cap != "bounded":
            raise ValueError(f"unknown cap mode: {cap}")
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
    return {"name": name, "output": output, "summary": summary, "metrics": metrics, "rows": rows}


def _paired(baseline_rows: list[dict[str, Any]], variant_rows: list[dict[str, Any]], *, seed: int, resamples: int) -> dict[str, Any]:
    baseline = {row["id"]: row for row in baseline_rows}
    variant = {row["id"]: row for row in variant_rows}
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


def _selection_diagnostic(*, cases: list[dict[str, Any]], manifest: dict[str, Any], current_lane: dict[str, Any]) -> dict[str, Any]:
    by_case = {case["id"]: case for case in cases}
    registry_by_project = {project: evidence.registry_for(project, manifest) for project in sorted({case["project_group"] for case in cases})}
    current_rows = {row["id"]: row for row in current_lane["rows"] if row.get("answerability") == "within_budget"}
    results: list[dict[str, Any]] = []
    exact_recoveries: list[str] = []
    beam_recoveries: list[str] = []
    projector_failures = 0
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
                    "sufficient": assessment["context_sufficiency"] == "sufficient" and not safety,
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

        beam_states: list[tuple[int, ...]] = [()]
        beam_success: dict[str, Any] | None = None
        for _depth in range(1, min(SELECTION_PACKAGE_LIMIT, len(pool)) + 1):
            expanded: set[tuple[int, ...]] = set()
            for state in beam_states:
                start = state[-1] + 1 if state else 0
                for index in range(start, len(pool)):
                    expanded.add((*state, index))
            scored = [project(state) for state in sorted(expanded)]
            for candidate in scored:
                if candidate["sufficient"]:
                    beam_success = candidate
                    break
            if beam_success is not None:
                break
            scored.sort(key=lambda item: (tuple(item["proxy"]), -item["tokens"]), reverse=True)
            beam_states = [tuple(item["indices"]) for item in scored[:BEAM_WIDTH]]

        if exact is not None:
            exact_recoveries.append(case_id)
        if beam_success is not None:
            beam_recoveries.append(case_id)
        results.append({"id": case_id, "current_sufficient": False, "pool": _candidate_structure(pool), "exact_recovery": exact, "beam_recovery": beam_success, "enumerated_packages": len(cache)})
    status = "OBSERVED" if exact_recoveries else "NOT_OBSERVED_IN_BOUNDED_POOL"
    return {
        "candidate_pool_limit": SELECTION_POOL_LIMIT,
        "package_source_limit": SELECTION_PACKAGE_LIMIT,
        "beam_width": BEAM_WIDTH,
        "reference": "exhaustive subset replay through unchanged projector; gold is used only to score the oracle, never the beam proxy",
        "selection_bottleneck": status,
        "exact_recoveries": exact_recoveries,
        "beam_recoveries": beam_recoveries,
        "proxy_exact_gap": sorted(set(exact_recoveries) - set(beam_recoveries)),
        "projector_failures": projector_failures,
        "production_selector_decision": "INVESTIGATE_OBSERVED_GAP_BEFORE_PRODUCT_CHANGE" if exact_recoveries else "NOT_JUSTIFIED_BY_THIS_SAMPLE",
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
    for name, cap, requalification, contextualization in lane_specs:
        lanes[name] = _run_lane(name=name, work=work / "causal", protocol=frozen_protocol, cases=causal_cases, manifest=frozen_manifest, cap=cap, requalification=requalification, contextualization=contextualization)

    full80 = _run_lane(name="full80_current", work=work / "acceptance", protocol=frozen_protocol, cases=frozen_cases, manifest=frozen_manifest)
    current = lanes["cap_on_requal_on"]
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

    holdout_cases, holdout_manifest, holdout_documents = _load_holdout()
    documents_for, registry_for = _holdout_adapters(holdout_manifest, holdout_documents)
    holdout_current = _run_lane(name="holdout_current", work=work / "holdout", protocol=frozen_protocol, cases=holdout_cases, manifest=holdout_manifest, documents_for=documents_for, registry_for=registry_for)
    holdout_strict = _run_lane(name="holdout_strict_cap", work=work / "holdout", protocol=frozen_protocol, cases=holdout_cases, manifest=holdout_manifest, cap="strict", documents_for=documents_for, registry_for=registry_for)
    holdout_pair = _paired(holdout_strict["rows"], holdout_current["rows"], seed=seed, resamples=resamples)
    holdout_generalization = "SUPPORTED_ON_POSTHOC_INDEPENDENT_PROJECT_SAMPLE" if holdout_pair["wins"] and not holdout_pair["losses"] else "REGRESSION_OBSERVED" if holdout_pair["losses"] else "NO_REGRESSION_BUT_IMPROVEMENT_NOT_OBSERVED"

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    frozen_current = full80["metrics"]
    full80_valid_rows = [row for row in full80["rows"] if "error" not in row]
    full80_max_tokens = max((int(row.get("size", {}).get("actual_tokens") or 0) for row in full80_valid_rows), default=0)
    report = {
        "schema_version": "systemic-retrieval-plan-acceptance-v1",
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
        },
        "full_frozen_80": {
            **frozen_current,
            "failure_families": _failure_families(full80["rows"]),
            "historical_floor_preserved": frozen_current["within_budget"] == 48 and frozen_current["within_budget_sufficient"] >= HISTORICAL_CURRENT_FLOOR,
            "max_actual_model_visible_tokens": full80_max_tokens,
            "actual_full_dto_budget": full80_max_tokens <= MAX_TOKENS,
        },
        "causal_2x2": {"cells": cells, "paired_against_current": paired, "difference_in_differences_success_rate": interaction, "interpretation": "Counterfactual diagnostic only; no causal claim extends beyond this fixed exposed corpus."},
        "contextualization": {"paired_against_current": paired["contextualization_off"], "compact_and_expanded": compact_expanded},
        "source_policy": {"pre_hydration": {"status": "PRODUCTION_BOUNDARY_TESTED", "test": "tests/test_pre_hydration_source_policy.py", "defense_in_depth_post_hydration_filter_retained": True}, "final_citations": final_policy},
        "selection": selection,
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
    if full80_max_tokens > MAX_TOKENS:
        failures.append("full model-visible DTO exceeded the 800-token ceiling")
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
