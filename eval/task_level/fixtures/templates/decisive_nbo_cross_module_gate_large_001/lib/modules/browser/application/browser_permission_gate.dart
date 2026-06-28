import '../../permission/application/permission_service.dart';
import '../../permission/domain/permission_result.dart';

class BrowserPermissionGate {
  BrowserPermissionGate(this._permissionService);

  final PermissionService _permissionService;

  bool canEnter(PermissionResult result) {
    final decision = _permissionService.evaluateFlowEntry(
      result,
      allowOfflineFallback: true,
    );
    return decision != PermissionDecision.block;
  }

  String blockedReason(PermissionResult result) {
    final decision = _permissionService.evaluateFlowEntry(result);
    return decision == PermissionDecision.block ? 'permission-required' : 'ready';
  }
}
