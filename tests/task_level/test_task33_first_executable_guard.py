from __future__ import annotations

from eval.task_level.evaluators.contract import _evaluate_task33_cross_module_gate
from eval.task_level.hidden_tests.decisive_nbo_cross_module_gate_large_001.test_hidden_cross_module_gate_large import (
    _blocks_missing_immediate,
    _delegates_and_requires_allow,
    _method_body,
)


def test_task33_missing_permission_guard_must_be_first_executable_statement():
    guard = (
        "if (result.hasMissingImmediatePermission) {\n"
        "  return PermissionDecision.block;\n"
        "}"
    )

    assert _blocks_missing_immediate("\n  " + guard + "\n  return PermissionDecision.allow;")
    assert not _blocks_missing_immediate(
        "if (allowOfflineFallback) {\n  " + guard + "\n}"
    )
    assert not _blocks_missing_immediate(
        "if (allowOfflineFallback)\n  " + guard
    )
    assert not _blocks_missing_immediate(
        "final audit = recordAttempt();\n" + guard
    )


def test_task33_method_body_binds_to_typed_declaration_not_call_site_decoy(tmp_path):
    service = tmp_path / "permission_service.dart"
    service.write_text(
        "/* outer comment\n"
        "  /* nested comment */\n"
        "  class CommentDecoy { PermissionDecision evaluateFlowEntry(PermissionResult result) {\n"
        "    if (result.hasMissingImmediatePermission) { return PermissionDecision.block; }\n"
        "  }}\n"
        "*/\n"
        "class DecoyService {\n"
        "  PermissionDecision evaluateFlowEntry(PermissionResult result) {\n"
        "    if (result.hasMissingImmediatePermission) {\n"
        "      return PermissionDecision.block;\n"
        "    }\n"
        "    return PermissionDecision.allow;\n"
        "  }\n"
        "}\n"
        "class PermissionService {\n"
        "  void installDecoy() {\n"
        "    evaluateFlowEntry(result) {\n"
        "      if (result.hasMissingImmediatePermission) {\n"
        "        return PermissionDecision.block;\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "  PermissionDecision evaluateFlowEntry(PermissionResult result) {\n"
        "    return PermissionDecision.deferFollowUp;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    body = _method_body(service, "PermissionService", "evaluateFlowEntry")

    assert "return PermissionDecision.deferFollowUp;" in body
    assert "return PermissionDecision.block;" not in body


def test_task33_gate_receivers_are_canonical_instances_only():
    assert _delegates_and_requires_allow(
        "return _permissionService.evaluateFlowEntry(result) "
        "== PermissionDecision.allow;"
    )
    assert _delegates_and_requires_allow(
        "return this._permissionService.evaluateFlowEntry(result) "
        "== PermissionDecision.allow;"
    )
    assert not _delegates_and_requires_allow(
        "return PermissionService.evaluateFlowEntry(result) "
        "== PermissionDecision.allow;"
    )
    assert not _delegates_and_requires_allow(
        "return rogue.evaluateFlowEntry(result) "
        "== PermissionDecision.allow;"
    )


def _host_files(
    service_body: str,
    *,
    browser_receiver: str = "_permissionService",
    browser_field_type: str = "PermissionService",
) -> dict[str, str]:
    def gate(class_name: str, method: str, receiver: str, fallback: str = "", field_type: str = "PermissionService") -> str:
        return (
            f"class {class_name} {{\n"
            f"  {field_type} _permissionService;\n"
            f"  bool {method}(PermissionResult result) {{\n"
            f"    return {receiver}.evaluateFlowEntry(result{fallback}) "
            "== PermissionDecision.allow;\n"
            "  }\n"
            "}\n"
        )

    return {
        "lib/modules/permission/application/permission_service.dart": service_body,
        "lib/modules/browser/application/browser_permission_gate.dart": gate(
            "BrowserPermissionGate",
            "canEnter",
            browser_receiver,
            ", allowOfflineFallback: true",
            browser_field_type,
        ),
        "lib/modules/scan/application/scan_permission_gate.dart": gate(
            "ScanPermissionGate",
            "canEnter",
            "_permissionService",
        ),
        "lib/modules/sync/application/offline_sync_gate.dart": gate(
            "OfflineSyncGate",
            "canAcceptQueuedWork",
            "_permissionService",
            ", allowOfflineFallback: false",
        ),
    }


def test_task33_host_evaluator_rejects_call_site_decoy():
    files = _host_files(
        "class DecoyService {\n"
        "  PermissionDecision evaluateFlowEntry(PermissionResult result) {\n"
        "    if (result.hasMissingImmediatePermission) { return PermissionDecision.block; }\n"
        "    return PermissionDecision.allow;\n"
        "  }\n"
        "}\n"
        "class PermissionService {\n"
        "  void installDecoy() {\n"
        "    evaluateFlowEntry(result) {\n"
        "      if (result.hasMissingImmediatePermission) {\n"
        "        return PermissionDecision.block;\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "  PermissionDecision evaluateFlowEntry(PermissionResult result) {\n"
        "    return PermissionDecision.deferFollowUp;\n"
        "  }\n"
        "}\n"
    )

    result = _evaluate_task33_cross_module_gate("", files)

    assert "shared_entry_decision" in result.missing_requirements


def test_task33_host_evaluator_rejects_class_receiver_and_late_guard():
    files = _host_files(
        "class PermissionService {\n"
        "  PermissionDecision evaluateFlowEntry(PermissionResult result) {\n"
        "    final audit = recordAttempt();\n"
        "    if (result.hasMissingImmediatePermission) {\n"
        "      return PermissionDecision.block;\n"
        "    }\n"
        "  }\n"
        "}\n",
        browser_receiver="PermissionService",
    )

    result = _evaluate_task33_cross_module_gate("", files)

    assert "shared_entry_decision" in result.missing_requirements
    assert "browser_gate_delegates" in result.missing_requirements

    spoofed = _host_files(
        "class PermissionService {\n"
        "  PermissionDecision evaluateFlowEntry(PermissionResult result) {\n"
        "    if (result.hasMissingImmediatePermission) { return PermissionDecision.block; }\n"
        "    return PermissionDecision.allow;\n"
        "  }\n"
        "}\n",
        browser_field_type="RoguePermissionService",
    )
    spoofed["lib/modules/browser/application/browser_permission_gate.dart"] += (
        "bool duplicateInterpretation(result) => result.hasMissingImmediatePermission;\n"
    )
    spoofed_result = _evaluate_task33_cross_module_gate("", spoofed)
    assert "shared_service_dependencies" in spoofed_result.missing_requirements
    assert "no_duplicate_flow_interpretation" in spoofed_result.missing_requirements
