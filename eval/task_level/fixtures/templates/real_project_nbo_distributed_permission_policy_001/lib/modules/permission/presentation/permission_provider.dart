import '../application/permission_service.dart';
import '../domain/permission_info.dart';

class PermissionProvider {
  PermissionProvider(this._service);

  final PermissionService _service;

  List<PermissionInfo> preflightFor(PermissionFlow flow, int sdkInt) {
    // Providers delegate; platform policy belongs in PermissionService.
    return _service.requiredForPreflight(flow, sdkInt);
  }
}
