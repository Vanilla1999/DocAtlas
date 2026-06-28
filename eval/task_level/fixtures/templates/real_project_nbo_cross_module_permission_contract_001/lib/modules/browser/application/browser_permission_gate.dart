import '../../permission/application/permission_service.dart';
import '../../permission/domain/permission_result.dart';

class BrowserPermissionGate {
  BrowserPermissionGate(this._permissionService);

  final PermissionService _permissionService;

  bool canEnter(PermissionResult result) {
    return _permissionService.evaluatePreflight(result) == PermissionDecision.allow;
  }
}
