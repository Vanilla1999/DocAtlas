#!/usr/bin/env python3
"""Finalize the selector decision with a blind, bounded singleton control."""
from __future__ import annotations

from pathlib import Path

path = Path("scripts/run_systemic_retrieval_plan_gate.py")
text = path.read_text(encoding="utf-8")
start = text.find("def _selection_diagnostic(")
end = text.find("\n\ndef _load_holdout(", start)
if start < 0 or end < 0:
    raise SystemExit("selection diagnostic boundaries changed")

replacement = r'''def _selection_diagnostic(*, cases: list[dict[str, Any]], manifest: dict[str, Any], current_lane: dict[str, Any]) -> dict[str, Any]:
    """Measure an oracle gap separately from a production-blind selector.

    The oracle may use evaluator sufficiency only after enumeration.  The blind
    singleton control chooses solely from model-visible query overlap, source
    diversity/count and token cost, then gold is consulted only to score that
    already-fixed choice.  This keeps the product decision independent of the
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
        blind_choice = max(
            singleton_candidates,
            key=lambda item: (tuple(item["proxy"]), -item["tokens"], tuple(-index for index in item["indices"])),
            default=None,
        )
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
'''

path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
Path(__file__).unlink()
