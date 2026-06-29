import '../../permission/application/permission_service.dart';
import '../../permission/domain/permission_result.dart';

class ScanPermissionGate {
  ScanPermissionGate(this._permissionService);

  final PermissionService _permissionService;

  bool canEnter(PermissionResult result) {
    if (!result.cameraGranted || !result.locationGranted) {
      return false;
    }
    return true;
  }
}
