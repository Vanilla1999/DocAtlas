import '../../permission/application/permission_service.dart';
import '../../permission/domain/permission_result.dart';

class OfflineSyncGate {
  OfflineSyncGate(this._permissionService);

  final PermissionService _permissionService;

  bool canAcceptQueuedWork(PermissionResult result) {
    final decision = _permissionService.evaluateFlowEntry(
      result,
      allowOfflineFallback: true,
    );
    return decision != PermissionDecision.block;
  }
}
