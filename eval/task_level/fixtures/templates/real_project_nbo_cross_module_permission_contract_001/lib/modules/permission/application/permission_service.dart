import '../domain/permission_result.dart';

class PermissionService {
  PermissionDecision evaluatePreflight(PermissionResult result) {
    if (result.hasAnyMissingPermission) {
      return PermissionDecision.block;
    }
    return PermissionDecision.allow;
  }
}
