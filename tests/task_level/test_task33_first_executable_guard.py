from __future__ import annotations

from eval.task_level.evaluators.contract import _evaluate_task33_cross_module_gate
from eval.task_level.hidden_tests.decisive_nbo_cross_module_gate_large_001.test_hidden_cross_module_gate_large import (
    _blocks_missing_immediate,
    _delegates_and_requires_allow,
    _method_body,
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



