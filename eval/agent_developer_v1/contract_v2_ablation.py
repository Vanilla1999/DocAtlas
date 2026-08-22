from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROTOCOL = "agent-contract-v2-ablation-v1"
SCHEMA_VERSION = 1
EXPECTED_TASK_COUNT = 11
EXPECTED_PRIMARY_COUNTS = {
    "question_specificity_mismatch": 2,
    "required_scope_sequence_mismatch": 1,
    "selector_cardinality_invalid": 8,
}


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _primary_counts(atlas: dict[str, Any]) -> Counter[str]:
    tasks = atlas.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != EXPECTED_TASK_COUNT:
        raise ValueError("P1.3 requires the complete 11-task P1.2 atlas")
    counts = Counter(
        str((row.get("first_divergence") or {}).get("failure_class") or "")
        for row in tasks
        if isinstance(row, dict)
    )
    if dict(sorted(counts.items())) != EXPECTED_PRIMARY_COUNTS:
        raise ValueError(f"P1.2 class distribution drift: {dict(counts)!r}")
    return counts


def _candidate(
    *,
    candidate_id: str,
    description: str,
    addressed_classes: tuple[str, ...],
    counts: Counter[str],
    context_owner: str,
    public_contract_change: bool,
    server_authority_expansion: bool,
    new_state_surface: bool,
    decision: str,
    decision_reason: str,
) -> dict[str, Any]:
    addressed = sum(int(counts.get(name, 0)) for name in addressed_classes)
    return {
        "id": candidate_id,
        "description": description,
        "addressed_primary_classes": list(addressed_classes),
        "counterfactual_primary_divergences_addressed": addressed,
        "counterfactual_residual_primary_divergences": EXPECTED_TASK_COUNT - addressed,
        "context_owner": context_owner,
        "public_contract_change": public_contract_change,
        "server_authority_expansion": server_authority_expansion,
        "new_state_surface": new_state_surface,
        "same_frozen_tasks": True,
        "same_historical_model_report": True,
        "same_call_budgets": True,
        "live_model_effect_measured": False,
        "false_support_delta_measured": False,
        "contamination_delta_measured": False,
        "decision": decision,
        "decision_reason": decision_reason,
    }


def build_ablation(atlas: dict[str, Any]) -> dict[str, Any]:
    counts = _primary_counts(atlas)
    source = atlas.get("source") if isinstance(atlas.get("source"), dict) else {}
    candidates = [
        _candidate(
            candidate_id="current_contract",
            description="Historical model-visible contract and planner behavior.",
            addressed_classes=(),
            counts=counts,
            context_owner="unchanged",
            public_contract_change=False,
            server_authority_expansion=False,
            new_state_surface=False,
            decision="baseline",
            decision_reason="Reference condition; retains all observed primary divergences.",
        ),
        _candidate(
            candidate_id="working_path_visible",
            description=(
                "Expose working_path to the model without adding any selector "
                "normalization or server inference."
            ),
            addressed_classes=(),
            counts=counts,
            context_owner="host",
            public_contract_change=False,
            server_authority_expansion=False,
            new_state_surface=False,
            decision="reject_as_redundant",
            decision_reason=(
                "The historical public tasks already exposed working_path, so this "
                "candidate has zero incremental evidence coverage."
            ),
        ),
        _candidate(
            candidate_id="host_selector_normalization",
            description=(
                "The host derives an exact module_path from the already supplied "
                "working_path, clears module, and validates the normalized call."
            ),
            addressed_classes=("selector_cardinality_invalid",),
            counts=counts,
            context_owner="host",
            public_contract_change=False,
            server_authority_expansion=False,
            new_state_surface=False,
            decision="accept_for_next_live_ablation",
            decision_reason=(
                "It targets the dominant 8/11 pre-MCP failure without granting the "
                "server new scope authority or changing the public three-tool schema."
            ),
        ),
        _candidate(
            candidate_id="server_owned_scope_module_inference",
            description=(
                "The server infers module scope/module_path when the model supplies "
                "an incomplete or contradictory selector."
            ),
            addressed_classes=("selector_cardinality_invalid",),
            counts=counts,
            context_owner="server",
            public_contract_change=True,
            server_authority_expansion=True,
            new_state_surface=False,
            decision="reject",
            decision_reason=(
                "It has no broader counterfactual coverage than host normalization "
                "but can silently choose scope before evidence adjudication."
            ),
        ),
        _candidate(
            candidate_id="opaque_continuation_token",
            description=(
                "Return an opaque lifecycle token that the model replays on a later "
                "tool call."
            ),
            addressed_classes=(),
            counts=counts,
            context_owner="server",
            public_contract_change=True,
            server_authority_expansion=False,
            new_state_surface=True,
            decision="reject",
            decision_reason=(
                "All observed first divergences occur before a successful lifecycle "
                "handoff could issue a continuation token."
            ),
        ),
    ]
    composite_controls = [
        {
            "id": "host_planning_profile_control",
            "description": (
                "Selector normalization plus exact-identity question guidance plus "
                "the frozen module-before-dependency sequence."
            ),
            "addressed_primary_classes": sorted(EXPECTED_PRIMARY_COUNTS),
            "counterfactual_primary_divergences_addressed": EXPECTED_TASK_COUNT,
            "counterfactual_residual_primary_divergences": 0,
            "public_contract_change": False,
            "production_feature_approved": False,
            "purpose": (
                "Positive-control profile for a future provider-backed run; not a "
                "claim that the historical model would follow the repaired plan."
            ),
        }
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "protocol": PROTOCOL,
        "source": {
            "p1_2_atlas_sha256": sha256_json(atlas),
            "historical_model_report_sha256": str(source.get("report_sha256") or ""),
            "provider_id": str(source.get("provider_id") or ""),
            "model": str(source.get("model") or ""),
            "task_count": EXPECTED_TASK_COUNT,
            "fresh_provider_run_available": False,
            "fresh_provider_blocker": str(source.get("fresh_run_blocker") or ""),
        },
        "method": {
            "kind": "first-divergence counterfactual ablation",
            "same_frozen_tasks": True,
            "same_historical_model_report": True,
            "same_call_budgets": True,
            "runtime_or_public_schema_modified": False,
            "live_model_effect_measured": False,
        },
        "observed_primary_failure_counts": dict(sorted(counts.items())),
        "candidates": candidates,
        "composite_controls": composite_controls,
        "decision": {
            "accepted_for_next_live_ablation": ["host_selector_normalization"],
            "accepted_public_contract_changes": [],
            "rejected": [
                "working_path_visible",
                "server_owned_scope_module_inference",
                "opaque_continuation_token",
            ],
            "public_agent_contract_v2": "no_change",
            "reason": (
                "P1.2 supports a host-owned normalization experiment, not a public "
                "working_path field, server-owned inference, or continuation state."
            ),
        },
        "safety": {
            "historical_false_supported": int(
                (atlas.get("summary") or {}).get("false_supported") or 0
            ),
            "historical_forbidden_source_contamination": int(
                (atlas.get("summary") or {}).get(
                    "forbidden_source_contamination"
                )
                or 0
            ),
            "candidate_false_support_delta_claimed": False,
            "candidate_contamination_delta_claimed": False,
            "live_confirmation_required_before_product_change": True,
        },
        "claim_boundary": {
            "p1_3_ablation_complete": True,
            "provider_backed_candidate_effect_proven": False,
            "public_api_change_authorized": False,
            "autonomous_agent_truth_closed": False,
            "product_maturity": "Beta",
        },
    }
    validate_ablation(report)
    return report


def validate_ablation(report: dict[str, Any]) -> None:
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("P1.3 schema version mismatch")
    if report.get("protocol") != PROTOCOL:
        raise ValueError("P1.3 protocol mismatch")
    counts = report.get("observed_primary_failure_counts")
    if counts != EXPECTED_PRIMARY_COUNTS:
        raise ValueError("P1.3 source distribution mismatch")
    candidates = report.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 5:
        raise ValueError("P1.3 must compare exactly five primary candidates")
    by_id = {
        str(row.get("id") or ""): row
        for row in candidates
        if isinstance(row, dict)
    }
    expected_ids = {
        "current_contract",
        "working_path_visible",
        "host_selector_normalization",
        "server_owned_scope_module_inference",
        "opaque_continuation_token",
    }
    if set(by_id) != expected_ids:
        raise ValueError("P1.3 candidate identities differ")
    if by_id["working_path_visible"].get(
        "counterfactual_primary_divergences_addressed"
    ) != 0:
        raise ValueError("working_path visibility cannot claim incremental gain")
    if by_id["host_selector_normalization"].get(
        "counterfactual_primary_divergences_addressed"
    ) != 8:
        raise ValueError("host normalization coverage drift")
    if by_id["server_owned_scope_module_inference"].get("decision") != "reject":
        raise ValueError("server-owned inference must remain rejected")
    if by_id["opaque_continuation_token"].get(
        "counterfactual_primary_divergences_addressed"
    ) != 0:
        raise ValueError("continuation token cannot claim observed first-divergence gain")
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    if decision.get("accepted_public_contract_changes") != []:
        raise ValueError("P1.3 cannot approve a public contract change")
    if decision.get("public_agent_contract_v2") != "no_change":
        raise ValueError("P1.3 public Agent Contract decision drift")
    safety = report.get("safety") if isinstance(report.get("safety"), dict) else {}
    if safety.get("candidate_false_support_delta_claimed") is not False:
        raise ValueError("P1.3 cannot claim unmeasured false-support safety")
    if safety.get("candidate_contamination_delta_claimed") is not False:
        raise ValueError("P1.3 cannot claim unmeasured contamination safety")
    boundary = (
        report.get("claim_boundary")
        if isinstance(report.get("claim_boundary"), dict)
        else {}
    )
    if boundary.get("public_api_change_authorized") is not False:
        raise ValueError("P1.3 cannot authorize a public API change")
    if boundary.get("autonomous_agent_truth_closed") is not False:
        raise ValueError("P1.3 cannot close Autonomous Agent Truth")
    if boundary.get("product_maturity") != "Beta":
        raise ValueError("P1.3 cannot promote product maturity")


def render_markdown(report: dict[str, Any]) -> str:
    validate_ablation(report)
    lines = [
        "# P1.3 — Agent Contract v2 ablation",
        "",
        "## Method and evidence boundary",
        "",
        "This is a counterfactual first-divergence ablation over the exact P1.2 "
        "atlas. It holds the frozen tasks, historical model report, and call budgets "
        "constant. It does not claim that a real model was rerun under a candidate.",
        "",
        "| Candidate | Primary divergences addressed | Residual | Decision |",
        "|---|---:|---:|---|",
    ]
    for candidate in report["candidates"]:
        lines.append(
            f"| `{candidate['id']}` | "
            f"{candidate['counterfactual_primary_divergences_addressed']}/11 | "
            f"{candidate['counterfactual_residual_primary_divergences']} | "
            f"`{candidate['decision']}` |"
        )
    lines.extend(
        [
            "",
            "## Findings",
            "",
            "1. `working_path` was already model-visible in the historical tasks, so "
            "merely exposing it again addresses **0/11** first divergences.",
            "2. Host-owned selector normalization addresses the dominant **8/11** "
            "pre-MCP failures without changing the public MCP schema.",
            "3. Server-owned inference has the same counterfactual coverage but grants "
            "the server authority to choose scope/module silently; it is rejected.",
            "4. A continuation token addresses **0/11** observed first divergences "
            "because every primary failure precedes lifecycle continuation.",
            "5. A host-only positive-control profile could cover all three observed "
            "classes, but it still requires a real provider-backed confirmation run.",
            "",
            "## Decision",
            "",
            "No public Agent Contract v2 change is approved. The only accepted next "
            "experiment is host-side selector normalization in a future live ablation. "
            "Public `working_path`, server-owned scope inference, and opaque continuation "
            "state remain rejected by the available evidence.",
            "",
            "## Claim boundary",
            "",
            "- P1.3 ablation work item: complete.",
            "- Provider-backed candidate effect: not proven.",
            "- False-support/contamination delta: not measured and not claimed.",
            "- Autonomous Agent Truth: not closed.",
            "- Product maturity: Beta.",
            "",
        ]
    )
    return "\n".join(lines)
