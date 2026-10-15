"""Source acquisition and action packet integration; helpers remain shared."""
from tests.docs import _shared_test_action_packet as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})
from docmancer.docs.domain.patch_request_plan import build_patch_request_plan, PatchRequestPlan, PatchTarget
from docmancer.docs.domain.mutation_intent import MutationIntentContract, RequestedTarget

PERMISSION_PATCH_QUERY = (
    "Fix partial permission handling across BrowserPermissionGate, ScanPermissionGate, "
    "OfflineSyncGate, and PermissionService."
)


def test_patch_request_plan_separates_mutation_and_preserve_targets():
    from pathlib import Path
    from docmancer.docs.domain.source_map import build_project_source_evidence
    from docmancer.docs.domain.source_boundary import SourceBoundary

    question = (
        "Fix partial permission handling in BrowserPermissionGate, ScanPermissionGate, "
        "OfflineSyncGate, and PermissionService without changing permission_result.freezed.dart."
    )
    # Original prose stays unresolved; the SDK consumer receives an explicit
    # authored operation/target/preserve DTO, never an inferred permission.
    # user_request records these exact original spans; explicit_task_contract
    # is reserved here for extra SDK paths absent from the question (-1 spans).
    prose_plan = build_patch_request_plan(question)
    assert prose_plan.operation == "none" and not prose_plan.mutation_targets
    assert prose_plan.unresolved_parts == ("unsupported_patch_surface",)
    mutate = ("BrowserPermissionGate", "ScanPermissionGate", "OfflineSyncGate", "PermissionService")
    preserve = "permission_result.freezed.dart"
    def target(value, role):
        start = question.index(value)
        return PatchTarget(value, "path" if role == "preserve" else "symbol",
                           start, start + len(value), role, role,
                           provenance="user_request")
    plan = PatchRequestPlan("modify", tuple(target(value, "mutate") for value in mutate),
                            preserve_targets=(target(preserve, "preserve"),),
                            surface_id="explicit_task_contract")
    contract = MutationIntentContract("modify", "source", tuple(
        RequestedTarget(value, "symbol", question.index(value), question.index(value) + len(value),
                        provenance="user_request") for value in mutate
    ), request_plan=plan)
    assert [item.value for item in contract.requested_targets] == list(mutate)
    assert [item.value for item in plan.preserve_targets] == [preserve]
    assert all(question[item.query_span_start:item.query_span_end] == item.value
               for item in (*plan.mutation_targets, *plan.preserve_targets))

    root = Path("eval/task_level/fixtures/templates/decisive_nbo_cross_module_gate_large_001")
    declared_paths = (
        "lib/modules/browser/application/browser_permission_gate.dart",
        "lib/modules/scan/application/scan_permission_gate.dart",
        "lib/modules/sync/application/offline_sync_gate.dart",
        "lib/modules/permission/application/permission_service.dart",
        "lib/modules/permission/domain/permission_result.freezed.dart",
    )
    # The SDK host supplies these exact fixture members. A question alone
    # cannot authorize source enumeration, including generated preserve files.
    assert build_project_source_evidence(root, question=question) == []
    evidence = build_project_source_evidence(
        root, question=question, requirements=[*mutate, preserve],
        source_boundary=SourceBoundary(code_files=declared_paths),
        include_generated=True, max_items=12, token_budget=1400,
    )
    assert {row["path"] for row in evidence if row.get("matched") is True} == set(declared_paths)
    evidence.append({
        "path": "docs/permission-architecture.md", "source_class": "project_doc",
        "authority": "canonical", "content": "Partial permission handling spans all permission gates.",
    })
    from docmancer.docs.application.action_packet import evidence_identity_for_item
    identify = lambda item: evidence_identity_for_item(item)[0]
    resolved = resolve_mutation_targets(contract, evidence, evidence_id_for_item=identify)
    assert evaluate_mutation_readiness(resolved).ready is True
    assert {item.requested_value for item in resolved.resolved_targets} == set(mutate)
    assert resolved.preserved_targets[0].path.endswith(preserve)
    packet = build_action_packet(question=question, context_pack=evidence,
                                 mutation_intent_contract=resolved)
    assert validate_action_packet(packet, evidence_items=evidence,
                                  mutation_intent_contract=resolved) == []
    assert packet["result"] == "data" and packet["edit_ready"] is False
    assert packet["mutation_intent"]["contract_hash"] == resolved.contract_hash
    assert packet["mutation_intent"]["request_plan"]["preserve_targets"][0]["value"] == preserve
    visible_paths = {row["path"] for row in packet["sources"]}
    assert {item.path for item in (*resolved.resolved_targets, *resolved.preserved_targets)}.issubset(visible_paths)

    missing_question = "Fix BrowserPermissionGate without changing missing_result.freezed.dart."
    missing_name = "missing_result.freezed.dart"
    missing_start = missing_question.index(missing_name)
    missing_target = PatchTarget(missing_name, "path", missing_start, missing_start + len(missing_name),
                                 "preserve", "preserve", provenance="user_request")
    mutation_name = "BrowserPermissionGate"
    mutation_start = missing_question.index(mutation_name)
    mutation_target = PatchTarget(mutation_name, "symbol", mutation_start, mutation_start + len(mutation_name),
                                  "mutate", "mutate", provenance="user_request")
    missing_plan = PatchRequestPlan("modify", (mutation_target,),
                                    preserve_targets=(missing_target,), surface_id="explicit_task_contract")
    missing_contract = MutationIntentContract("modify", "source", (
        RequestedTarget(mutation_name, "symbol", mutation_start, mutation_start + len(mutation_name),
                        provenance="user_request"),
    ), request_plan=missing_plan)
    assert all(missing_question[item.query_span_start:item.query_span_end] == item.value
               for item in (*missing_plan.mutation_targets, *missing_plan.preserve_targets))
    unresolved = resolve_mutation_targets(missing_contract, evidence, evidence_id_for_item=identify)
    readiness = evaluate_mutation_readiness(unresolved)
    assert readiness.ready is False and "preserve_target_not_resolved" in readiness.missing
    missing_packet = build_action_packet(question=missing_question, context_pack=evidence,
                                         mutation_intent_contract=unresolved)
    assert missing_packet["edit_ready"] is False and missing_packet["completeness"] == "partial"
    missing_preserve_ids = {row["requirement_id"] for row in missing_packet["requirements"]
                            if row["kind"] == "preserve_declaration" and row["value"] == missing_name}
    assert missing_preserve_ids and missing_preserve_ids.issubset(set(missing_packet["missing"]))


def test_named_permission_patch_resolves_all_decisive_fixture_targets_without_formatter_loss():
    from pathlib import Path
    from docmancer.docs.domain.source_boundary import SourceBoundary
    from docmancer.docs.domain.source_map import build_project_source_evidence
    from docmancer.docs.application.action_packet import evidence_identity_for_item

    names = ("BrowserPermissionGate", "ScanPermissionGate", "OfflineSyncGate", "PermissionService")
    paths = (
        "lib/modules/browser/application/browser_permission_gate.dart",
        "lib/modules/scan/application/scan_permission_gate.dart",
        "lib/modules/sync/application/offline_sync_gate.dart",
        "lib/modules/permission/application/permission_service.dart",
    )
    root = Path("eval/task_level/fixtures/templates/decisive_nbo_cross_module_gate_large_001")
    assert build_project_source_evidence(root, question=PERMISSION_PATCH_QUERY) == []
    evidence = build_project_source_evidence(
        root, question=PERMISSION_PATCH_QUERY, requirements=names,
        source_boundary=SourceBoundary(code_files=paths), max_items=12, token_budget=1400,
    )
    contract = MutationIntentContract("modify", "source", tuple(
        RequestedTarget(name, "symbol", PERMISSION_PATCH_QUERY.index(name),
                        PERMISSION_PATCH_QUERY.index(name) + len(name), provenance="user_request")
        for name in names
    ))
    resolved = resolve_mutation_targets(
        contract, evidence, evidence_id_for_item=lambda row: evidence_identity_for_item(row)[0],
    )
    assert evaluate_mutation_readiness(resolved).ready is True
    assert {row.requested_value: row.path for row in resolved.resolved_targets} == dict(zip(names, paths))
    packet = build_action_packet(
        question=PERMISSION_PATCH_QUERY, context_pack=evidence, mutation_intent_contract=resolved,
    )
    assert packet["result"] == "data" and packet["edit_ready"] is False
    assert {row["path"] for row in packet["sources"]}.issuperset(paths)
    assert not any(reason.startswith("invalid_display_span:") for reason in packet.get("missing", []))
    assert validate_action_packet(packet, evidence_items=evidence, mutation_intent_contract=resolved) == []
