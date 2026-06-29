# Scan Flow Permission Contract

The scan flow has stricter hardware timing than browser, but it uses the same flow-entry permission contract. `ScanPermissionGate` should call `PermissionService.evaluateFlowEntry` and allow entry only when the decision is `PermissionDecision.allow`.

The scan gate must not maintain a parallel list of critical permissions. When the permission module changes the immediate-entry set, scan must pick up that behavior through the shared service.

Public scan tests focus on allowed paths, but hidden cross-module tests assert that partial/degraded permission results block scan entry too. This is not an oracle-only requirement: it follows from this document and the architecture document.
